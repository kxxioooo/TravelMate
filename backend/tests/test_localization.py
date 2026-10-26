"""v0.3.1 中英双语国际化测试(契约 §1 / §2 / §3 / §4 / §6.4 / §9)。

覆盖:
- locale 解析(请求头 / 显式 body / 非法值回落);
- 英文关键词经词典命中中文、词典未命中走受控翻译、翻译失败必须 422 而不是默认列表;
- 双语字段不伪造、缺失字段保持 None、事实字段(poi_id / rating / photos / location)不被改写;
- 翻译缓存命中不重复调模型、source_hash 变化后自然失效、批量大小受配置限制;
- 天气 / 穿衣 codes、Activity code+params、Agent 按 locale 组 prompt、历史消息不改写;
- 词典文件存在或不存在两种情况下都能通过。

DeepSeek 与高德调用全部 mock,绝不消耗真实 quota。
"""

import inspect
import json
from types import SimpleNamespace

import pytest

from app.core import errors
from app.core.locale import LOCALE_EN_US, LOCALE_ZH_CN, normalize_locale, resolve_request_locale
from app.models.entity_translation import EntityTranslation
from app.schemas.weather import WeatherInfo
from app.services import (
    agent_service,
    agent_tools,
    amap_client,
    deepseek_client,
    entity_localization_service,
    query_translation_service,
    translation_cache_service,
    weather_service,
)

API = "/api/v1"
EN_HEADERS = {"Accept-Language": "en-US,en;q=0.9"}
ZH_HEADERS = {"Accept-Language": "zh-CN,zh;q=0.9"}

CHENGDU = {"city_name": "成都", "adcode": "510100"}
HANGZHOU = {"city_name": "杭州", "adcode": "330100"}

#: 测试专用小词典(结构与契约 §8 完全一致)
TEST_LEXICON = {
    "version": "1",
    "search_aliases": {"ancient town": "古镇", "hot pot": "火锅", "museum": "博物馆", "park": "公园"},
    "places": {"西湖": {"en": "West Lake", "source": "verified"}},
    "dishes": {"麻婆豆腐": {"en": "Mapo Tofu", "source": "verified"}},
    "provinces": {"浙江": "Zhejiang"},
    "weather_codes": {"晴": "SUNNY", "小雨": "LIGHT_RAIN"},
    "tag_en": {"风景名胜": "Scenic spot", "公园广场": "Park & plaza"},
}


# --------------------------------------------------------------------------- #
# 公共夹具 / 工具
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def reset_lexicon_cache():
    """每个用例前后都清空词典缓存,避免用例之间互相污染。"""
    entity_localization_service.reset_lexicon_cache()
    yield
    entity_localization_service.reset_lexicon_cache()


@pytest.fixture
def lexicon(tmp_path, monkeypatch):
    """写入测试词典并让服务只读它(与真实词典是否存在无关)。"""
    path = tmp_path / "localization_lexicon.json"
    path.write_text(json.dumps(TEST_LEXICON, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(entity_localization_service, "LEXICON_PATH", path)
    entity_localization_service.reset_lexicon_cache()
    return path


@pytest.fixture
def no_lexicon(tmp_path, monkeypatch):
    """词典文件缺失:所有词典查询必须返回空,且整条链路不崩。"""
    monkeypatch.setattr(entity_localization_service, "LEXICON_PATH", tmp_path / "missing.json")
    entity_localization_service.reset_lexicon_cache()
    return tmp_path / "missing.json"


def _register(client, payload):
    assert client.post(f"{API}/auth/register", json=payload).status_code == 201


def _poi(
    poi_id="B001",
    name="雷峰塔",
    address="浙江省杭州市西湖区南山路15号",
    rating="4.7",
    cost="60.00",
    tags="风景名胜;公园广场",
    location="120.148977,30.231271",
):
    return {
        "id": poi_id,
        "name": name,
        "type": tags,
        "typecode": "110000",
        "address": address,
        "location": location,
        "tel": [],
        "biz_ext": {"rating": rating, "cost": cost},
        "photos": [{"title": [], "url": f"http://store.is.autonavi.com/{poi_id}.jpg"}],
    }


def _patch_amap_search(monkeypatch, handler):
    """替换 amap_client.search_pois,并记录底层收到的参数。"""
    calls = []

    async def fake_search_pois(city_name, keyword=None, category=None, page=1, page_size=10):
        calls.append(
            {
                "city_name": city_name,
                "keyword": keyword,
                "category": category,
                "page": page,
                "page_size": page_size,
            }
        )
        result = handler(**calls[-1])
        if inspect.isawaitable(result):
            result = await result
        return result

    monkeypatch.setattr(amap_client, "search_pois", fake_search_pois)
    return calls


def _patch_poi_detail(monkeypatch, poi):
    async def fake_get_poi_detail(poi_id):
        return dict(poi, id=poi_id)

    monkeypatch.setattr(amap_client, "get_poi_detail", fake_get_poi_detail)


def _prompt_items(user_prompt):
    """从实体翻译 prompt 的"输入:"后面取出请求条目。"""
    marker = "输入:"
    index = user_prompt.rfind(marker)
    assert index >= 0, "实体翻译 prompt 必须包含输入段落"
    return json.loads(user_prompt[index + len(marker) :].strip())["items"]


class DeepSeekRecorder:
    """一个 generate_json 替身,同时处理 entity 翻译 / 搜索词翻译 / 美食生成三条 prompt。"""

    def __init__(
        self,
        translator=None,
        entity_fail=False,
        query_keyword="庙会",
        query_fail=False,
        entity_extra_item=False,
        entity_drop_last=False,
    ):
        self.translator = translator
        self.entity_fail = entity_fail
        self.query_keyword = query_keyword
        self.query_fail = query_fail
        self.entity_extra_item = entity_extra_item
        self.entity_drop_last = entity_drop_last
        self.entity_calls = []
        self.query_calls = []
        self.food_calls = []
        self.all_calls = []

    async def __call__(self, system_prompt, user_prompt, **kwargs):
        assert system_prompt
        assert kwargs.get("temperature") is None or isinstance(kwargs["temperature"], float)
        self.all_calls.append(user_prompt)

        if "输入:" in user_prompt:
            self.entity_calls.append(user_prompt)
            if self.entity_fail:
                raise deepseek_client.DeepSeekError(deepseek_client.UNAVAILABLE_MESSAGE)
            items = _prompt_items(user_prompt)
            output = []
            for item in items:
                if self.entity_drop_last and item is items[-1]:
                    continue
                text = (
                    self.translator(item["text"], item.get("field"))
                    if self.translator is not None
                    else f"EN {item['text']}"
                )
                if text is None:
                    continue
                output.append({"id": item["id"], "text": text})
            if self.entity_extra_item:
                output.append({"id": "UNKNOWN|name", "text": "Fabricated Place"})
            return {"items": output}

        if "高德地图检索" in user_prompt:
            self.query_calls.append(user_prompt)
            if self.query_fail:
                raise deepseek_client.DeepSeekError(deepseek_client.UNAVAILABLE_MESSAGE)
            return {"keyword_zh": self.query_keyword}

        # 美食名单生成(food_service 的 prompt)
        self.food_calls.append(user_prompt)
        return {"foods": [{"name": "麻婆豆腐", "description": "麻辣鲜香的经典川菜。"}]}


def _install_deepseek(monkeypatch, **options) -> DeepSeekRecorder:
    """安装统一的 DeepSeek 替身并返回调用记录器。"""
    recorder = DeepSeekRecorder(**options)
    monkeypatch.setattr(deepseek_client, "generate_json", recorder)
    return recorder


def _final_text_response(text):
    return {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": text}}]}


def _tool_call(call_id, name, arguments):
    return {
        "index": 0,
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
    }


def _tool_call_response(*tool_calls):
    return {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {"role": "assistant", "content": None, "tool_calls": list(tool_calls)},
            }
        ]
    }


def _patch_chat_completion(monkeypatch, responses):
    seen = []

    async def fake_chat_completion(messages, tools=None, response_format=None, temperature=None):
        seen.append([dict(message) for message in messages])
        index = min(len(seen) - 1, len(responses) - 1)
        return responses[index]

    monkeypatch.setattr(deepseek_client, "chat_completion", fake_chat_completion)
    return seen


def _patch_city_weather(monkeypatch):
    async def fake_get_city_weather(adcode):
        assert adcode
        return weather_service.WeatherResponse(
            weather=weather_service.WeatherInfo(weather="多云", temperature=18.0),
            clothing_advice="薄外套",
            clothing_advice_codes=["LIGHT_JACKET"],
        )

    monkeypatch.setattr(weather_service, "get_city_weather", fake_get_city_weather)


# --------------------------------------------------------------------------- #
# 1. locale 解析(契约 §1)
# --------------------------------------------------------------------------- #
def test_normalize_locale_accepts_tags_and_accept_language():
    assert normalize_locale("en-US") == LOCALE_EN_US
    assert normalize_locale("en") == LOCALE_EN_US
    assert normalize_locale("EN_us") == LOCALE_EN_US
    assert normalize_locale("zh-CN") == LOCALE_ZH_CN
    assert normalize_locale("zh-Hans") == LOCALE_ZH_CN
    assert normalize_locale("zh-TW") == LOCALE_ZH_CN
    # 整条 Accept-Language:按 q 值挑第一个受支持语言
    assert normalize_locale("en-US,en;q=0.9") == LOCALE_EN_US
    assert normalize_locale("zh-CN,zh;q=0.9,en;q=0.8") == LOCALE_ZH_CN
    assert normalize_locale("fr-FR,en;q=0.7") == LOCALE_EN_US
    # 非法 / 空 / 非字符串一律回落默认 zh-CN
    assert normalize_locale("fr-FR") == LOCALE_ZH_CN
    assert normalize_locale("") == LOCALE_ZH_CN
    assert normalize_locale(None) == LOCALE_ZH_CN
    assert normalize_locale(123) == LOCALE_ZH_CN


def test_resolve_request_locale_priority():
    en_request = SimpleNamespace(headers={"accept-language": "en-US,en;q=0.9"})
    zh_request = SimpleNamespace(headers={"accept-language": "zh-CN,zh;q=0.9"})
    bare_request = SimpleNamespace(headers={})

    # body 的 locale 优先于请求头
    assert resolve_request_locale(en_request, explicit="zh-CN") == LOCALE_ZH_CN
    assert resolve_request_locale(zh_request, explicit="en-US") == LOCALE_EN_US
    # 没有显式值就用请求头
    assert resolve_request_locale(en_request) == LOCALE_EN_US
    # 头缺失 / 非法 -> zh-CN
    assert resolve_request_locale(bare_request) == LOCALE_ZH_CN
    assert resolve_request_locale(SimpleNamespace(headers={"accept-language": "de-DE"})) == LOCALE_ZH_CN
    # 显式值非法也回落 zh-CN(不再混着看请求头)
    assert resolve_request_locale(en_request, explicit="fr-FR") == LOCALE_ZH_CN


# --------------------------------------------------------------------------- #
# 2. 英文关键词 -> 中文检索词(契约 §6.4 / §8)
# --------------------------------------------------------------------------- #
def test_english_alias_from_lexicon_reaches_amap(
    monkeypatch, lexicon, client_fixture, user_payload_fixture
):
    calls = _patch_amap_search(
        monkeypatch, lambda **kwargs: {"status": "1", "count": "3", "pois": [_poi("B010", name="黄龙溪古镇")]}
    )
    # 词典命中时绝不应调用模型
    recorder = _install_deepseek(monkeypatch)
    _register(client_fixture, user_payload_fixture)

    response = client_fixture.get(
        f"{API}/attractions", params={"city_name": "成都", "keyword": "ancient town"}, headers=EN_HEADERS
    )

    assert response.status_code == 200
    # 高德收到的是中文关键词 + 原有类型过滤
    assert calls[0]["keyword"] == "古镇"
    assert calls[0]["category"] == "110000"
    assert calls[0]["city_name"] == "成都"
    assert recorder.query_calls == []  # 词典命中时绝不需要翻译搜索词


def test_english_place_name_from_lexicon_resolves_to_chinese(
    monkeypatch, lexicon, client_fixture, user_payload_fixture
):
    calls = _patch_amap_search(
        monkeypatch, lambda **kwargs: {"status": "1", "count": "1", "pois": [_poi("B011", name="西湖")]}
    )
    _register(client_fixture, user_payload_fixture)

    body = client_fixture.get(
        f"{API}/attractions", params={"city_name": "杭州", "keyword": "West Lake"}, headers=EN_HEADERS
    ).json()

    assert calls[0]["keyword"] == "西湖"
    assert body["items"][0]["name"] == "西湖"


def test_low_level_amap_params_stay_chinese_and_citylimited(monkeypatch, lexicon):
    """高德底层参数:types=110000 + keywords(中文) + citylimit=true,与 v0.2 一致。"""
    captured = []

    async def fake_request_amap(path, params):
        captured.append(params)
        return {"status": "1", "count": "0", "pois": []}

    monkeypatch.setattr(amap_client, "request_amap", fake_request_amap)

    import asyncio

    asyncio.run(
        amap_client.search_pois(
            city_name="成都", keyword="古镇", category=amap_client.ATTRACTION_TYPES, page=1, page_size=20
        )
    )

    assert captured[0]["keywords"] == "古镇"
    assert captured[0]["types"] == "110000"
    assert captured[0]["citylimit"] == "true"


def test_unknown_english_keyword_uses_one_controlled_translation(
    monkeypatch, no_lexicon, client_fixture, user_payload_fixture
):
    calls = _patch_amap_search(
        monkeypatch, lambda **kwargs: {"status": "1", "count": "1", "pois": [_poi("B012", name="文殊院庙会")]}
    )
    recorder = _install_deepseek(monkeypatch, query_keyword="庙会")
    _register(client_fixture, user_payload_fixture)

    body = client_fixture.get(
        f"{API}/attractions", params={"city_name": "成都", "keyword": "temple fair"}, headers=EN_HEADERS
    ).json()

    assert len(recorder.query_calls) == 1  # 单次受控翻译
    assert calls[0]["keyword"] == "庙会"
    assert calls[0]["category"] == "110000"
    assert body["items"][0]["name"] == "文殊院庙会"


def test_translation_failure_returns_query_unrecognized_not_default_list(
    monkeypatch, no_lexicon, client_fixture, user_payload_fixture
):
    calls = _patch_amap_search(monkeypatch, lambda **kwargs: {"status": "1", "count": "0", "pois": []})
    _install_deepseek(monkeypatch, query_fail=True)
    _register(client_fixture, user_payload_fixture)

    response = client_fixture.get(
        f"{API}/attractions", params={"city_name": "成都", "keyword": "temple fair"}, headers=EN_HEADERS
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "query.unrecognized"
    assert body["message_key"] == "error.query.unrecognized"
    # detail 仍是中文字符串(v0.3 前端兜底)
    assert isinstance(body["detail"], str) and body["detail"]
    # 关键:绝不能悄悄丢掉关键词去返回默认 Top 10
    assert calls == []


def test_food_english_keyword_translated_before_amap(
    monkeypatch, lexicon, client_fixture, user_payload_fixture
):
    calls = _patch_amap_search(
        monkeypatch,
        lambda **kwargs: {"status": "1", "count": "2", "pois": [dict(_poi("R001", name="蜀大侠火锅"), typecode="050100")]},
    )
    _register(client_fixture, user_payload_fixture)

    body = client_fixture.get(
        f"{API}/food/restaurants",
        params={"city_name": "成都", "keyword": "hot pot"},
        headers=EN_HEADERS,
    ).json()

    assert body["items"][0]["poi_id"] == "R001"
    # 高德收到的仍是中文 + types=050000
    assert calls[0]["keyword"] == "火锅"
    assert calls[0]["category"] == "050000"


def test_chinese_keyword_never_calls_model(monkeypatch, no_lexicon, client_fixture, user_payload_fixture):
    calls = _patch_amap_search(monkeypatch, lambda **kwargs: {"status": "1", "count": "1", "pois": [_poi("B013")]})
    recorder = _install_deepseek(monkeypatch, query_keyword="不该被调用")
    _register(client_fixture, user_payload_fixture)

    # 中文输入:中文界面与英文界面都必须直接当中文关键词用
    for headers in (EN_HEADERS, ZH_HEADERS):
        assert (
            client_fixture.get(
                f"{API}/attractions", params={"city_name": "成都", "keyword": "西湖"}, headers=headers
            ).status_code
            == 200
        )
    assert [call["keyword"] for call in calls] == ["西湖", "西湖"]
    assert recorder.query_calls == []


# --------------------------------------------------------------------------- #
# 3. 双语字段:优先词典、其次模型、失败降级、绝不伪造(契约 §2 / §6.2)
# --------------------------------------------------------------------------- #
def test_detail_bilingual_fields_keep_facts_untouched(
    monkeypatch, lexicon, client_fixture, user_payload_fixture
):
    poi = _poi("B020", name="西湖", tags="风景名胜;公园广场")
    _patch_poi_detail(monkeypatch, poi)
    recorder = _install_deepseek(monkeypatch)
    _register(client_fixture, user_payload_fixture)

    body = client_fixture.get(f"{API}/attractions/B020", headers=EN_HEADERS).json()

    # 词典命中:verified
    assert body["name_en"] == "West Lake"
    assert body["name_en_source"] == "verified"
    # 地址没有词典,走结构化翻译 -> model
    assert body["address_en"] == "EN 浙江省杭州市西湖区南山路15号"
    assert body["address_en_source"] == "model"
    # 标签全部命中词典 -> 英文列表
    assert body["tags_en"] == ["Scenic spot", "Park & plaza"]
    # 事实字段一个都没被改写
    assert body["poi_id"] == "B020"
    assert body["name"] == "西湖"
    assert body["address"] == "浙江省杭州市西湖区南山路15号"
    assert body["cost"] == "60.00"
    assert body["location"] == {"lng": 120.148977, "lat": 30.231271}
    assert body["photos"] == [{"url": "http://store.is.autonavi.com/B020.jpg", "title": None}]
    assert len(recorder.entity_calls) == 1


def test_untranslatable_name_is_fallback_not_fabricated(
    monkeypatch, no_lexicon, client_fixture, user_payload_fixture
):
    poi = _poi("B021", name="张记小吃")
    _patch_poi_detail(monkeypatch, poi)
    _install_deepseek(monkeypatch, entity_fail=True)
    _register(client_fixture, user_payload_fixture)

    response = client_fixture.get(f"{API}/attractions/B021", headers=EN_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert "name_en" not in body  # None 不参与序列化 = 明确没有可信英文名
    assert body["name_en_source"] == "fallback"
    assert body["address_en_source"] == "fallback"
    assert body["name"] == "张记小吃"  # 中文原名照旧返回
    assert body["poi_id"] == "B021"


def test_missing_fields_stay_none_in_english_mode(
    monkeypatch, no_lexicon, client_fixture, user_payload_fixture
):
    dirty = {
        "id": "B404",
        "name": "信息缺失景点",
        "type": [],
        "address": [],
        "tel": [],
        "location": [],
        "biz_ext": {"rating": [], "cost": []},
        "photos": [],
    }
    _patch_poi_detail(monkeypatch, dirty)
    _install_deepseek(monkeypatch)
    _register(client_fixture, user_payload_fixture)

    body = client_fixture.get(f"{API}/attractions/B404", headers=EN_HEADERS).json()

    assert body["address"] is None
    assert body["cost"] is None
    assert body["tags"] == []
    assert body["photos"] == []
    assert body["location"] is None
    assert "address_en" not in body  # 没有原文就不产生"译文"
    assert body["poi_id"] == "B404"


def test_chinese_locale_response_has_no_bilingual_fields(
    monkeypatch, lexicon, client_fixture, user_payload_fixture
):
    _patch_poi_detail(monkeypatch, _poi("B030", name="西湖"))
    recorder = _install_deepseek(monkeypatch)
    _register(client_fixture, user_payload_fixture)

    # 不带任何 locale 头:必须与 v0.3 完全一致(不翻译、不加字段)
    body = client_fixture.get(f"{API}/attractions/B030").json()

    assert set(body) == {"poi_id", "name", "photos", "address", "cost", "tags", "location"}
    assert recorder.entity_calls == []


# --------------------------------------------------------------------------- #
# 4. 缓存与批量翻译(契约 §6.3 / §9)
# --------------------------------------------------------------------------- #
def test_cache_hit_avoids_duplicate_model_calls(
    monkeypatch, no_lexicon, client_fixture, user_payload_fixture
):
    poi = _poi("B040", name="雷峰塔")
    _patch_poi_detail(monkeypatch, poi)
    recorder = _install_deepseek(monkeypatch)
    _register(client_fixture, user_payload_fixture)

    first = client_fixture.get(f"{API}/attractions/B040", headers=EN_HEADERS)
    second = client_fixture.get(f"{API}/attractions/B040", headers=EN_HEADERS)

    assert first.status_code == second.status_code == 200
    assert first.json()["name_en"] == second.json()["name_en"] == "EN 雷峰塔"
    # 同名同地址只请求一次模型:第二批请求全部命中缓存
    assert len(recorder.entity_calls) == 1


def test_source_hash_change_invalidates_cache(override_test_db):
    session = next(override_test_db())
    try:
        old_source = "雷峰塔"
        new_source = "雷峰塔(重建)"

        translation_cache_service.save_translation(
            session,
            "amap",
            "B050",
            "name",
            LOCALE_EN_US,
            "Leifeng Pagoda",
            "model",
            source_text=old_source,
        )

        old_hash = translation_cache_service.make_source_hash(old_source)
        new_hash = translation_cache_service.make_source_hash(new_source)
        assert old_hash != new_hash

        hit = translation_cache_service.get_cached_translation(
            session, "amap", "B050", "name", LOCALE_EN_US, old_hash
        )
        assert hit is not None and hit.translation_text == "Leifeng Pagoda"
        # 原文变了 -> 旧哈希不再命中(自然失效,不需要手工清缓存)
        assert (
            translation_cache_service.get_cached_translation(
                session, "amap", "B050", "name", LOCALE_EN_US, new_hash
            )
            is None
        )

        # 同一唯一键重复写入只更新,不新增行
        translation_cache_service.save_translation(
            session,
            "amap",
            "B050",
            "name",
            LOCALE_EN_US,
            "Leifeng Pagoda (rebuilt)",
            "model",
            source_text=old_source,
        )
        assert session.query(EntityTranslation).count() == 1
    finally:
        session.close()


def test_batch_size_limit_and_id_mapping(monkeypatch, no_lexicon):
    """每批 ≤ translation_batch_size;输出多出来的 id 丢弃,缺失的保持原值。"""
    records = [{"poi_id": f"P{i:02d}", "name": f"景点{i:02d}"} for i in range(7)]
    prompts = []

    async def fake_generate_json(system_prompt, user_prompt, **kwargs):
        items = _prompt_items(user_prompt)
        prompts.append(items)
        output = [{"id": item["id"], "text": f"EN {item['text']}"} for item in items[:-1]]
        # 故意多给一个不存在的 id:调用方必须丢弃
        output.append({"id": "P99|name", "text": "Fabricated Place"})
        return {"items": output}

    monkeypatch.setattr(deepseek_client, "generate_json", fake_generate_json)
    monkeypatch.setattr(
        entity_localization_service,
        "get_settings",
        lambda: SimpleNamespace(
            translation_cache_enabled=False,
            translation_batch_size=3,
            translation_timeout_seconds=5,
            translation_max_retries=0,
        ),
    )

    import asyncio

    localized = asyncio.run(
        entity_localization_service.localize_poi_batch(None, records, LOCALE_EN_US, ("name",))
    )

    assert [len(batch) for batch in prompts] == [3, 3, 1]
    assert all(len(batch) <= 3 for batch in prompts)
    # 多出来的 id 不产生任何结果
    assert "P99" not in localized
    assert set(localized) == {record["poi_id"] for record in records}
    # 每批最后一个缺失 -> 不编造,只标 fallback
    assert localized["P02"]["name_en_source"] == "fallback"
    assert "name_en" not in localized["P02"]
    assert localized["P00"]["name_en"] == "EN 景点00"


def test_lexicon_missing_is_tolerated(monkeypatch, no_lexicon):
    assert entity_localization_service.load_lexicon() == {}
    assert entity_localization_service.get_lexicon_section("places") == {}
    assert entity_localization_service.lookup_search_alias("ancient town") is None
    assert entity_localization_service.lookup_entity_by_english("West Lake") is None
    assert entity_localization_service.lookup_verified_name("西湖") is None
    assert entity_localization_service.lookup_tag_translation("风景名胜") is None
    # 天气 code 有内置映射兜底,词典缺失也必须有明确值
    assert weather_service.map_weather_code("小雨") == "LIGHT_RAIN"
    assert weather_service.map_weather_code("不存在的天气") == "UNKNOWN"


def test_lexicon_invalid_json_is_tolerated(tmp_path, monkeypatch):
    path = tmp_path / "localization_lexicon.json"
    path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(entity_localization_service, "LEXICON_PATH", path)
    entity_localization_service.reset_lexicon_cache()

    assert entity_localization_service.load_lexicon() == {}
    assert entity_localization_service.lookup_search_alias("hot pot") is None


# --------------------------------------------------------------------------- #
# 5. 天气 / 穿衣 codes(契约 §3)
# --------------------------------------------------------------------------- #
def test_weather_and_clothing_codes(monkeypatch, no_lexicon, client_fixture, user_payload_fixture):
    # 判定逻辑不变:旧的中文建议原样保留
    assert weather_service.build_clothing_advice(WeatherInfo(weather="中雨", temperature=20.0)) == (
        "薄外套 / 建议携带雨具"
    )
    assert weather_service.build_clothing_advice_codes(WeatherInfo(weather="中雨", temperature=20.0)) == [
        "LIGHT_JACKET",
        "UMBRELLA",
    ]
    assert weather_service.build_clothing_advice_codes(WeatherInfo(weather="晴", temperature=35.0)) == [
        "LIGHT_BREATHABLE"
    ]
    assert weather_service.build_clothing_advice_codes(WeatherInfo()) == ["UNKNOWN"]
    # 天气文本 -> code(含未知)
    assert weather_service.map_weather_code("多云") == "CLOUDY"
    assert weather_service.map_weather_code("雷阵雨") == "THUNDERSTORM"
    assert weather_service.map_weather_code("雨夹雪") == "SLEET"
    assert weather_service.map_weather_code("霾") == "HAZE"
    assert weather_service.map_weather_code(None) == "UNKNOWN"

    async def fake_get_weather(adcode):
        return {
            "lives": [{"weather": "小雨", "temperature": "8"}],
            "forecasts": [],
        }

    monkeypatch.setattr(amap_client, "get_weather", fake_get_weather)
    _register(client_fixture, user_payload_fixture)

    body = client_fixture.get(f"{API}/weather", params={"adcode": "510100"}, headers=EN_HEADERS).json()

    assert body["weather"]["weather"] == "小雨"
    assert body["weather"]["weather_code"] == "LIGHT_RAIN"
    assert body["clothing_advice"] == "外套 / 毛衣 / 建议携带雨具"
    assert body["clothing_advice_codes"] == ["COAT_SWEATER", "UMBRELLA"]


# --------------------------------------------------------------------------- #
# 6. Agent:Activity code+params / 按 locale 组 prompt / 历史消息不改写(契约 §4 / §8)
# --------------------------------------------------------------------------- #
def test_activity_code_and_params_in_english_mode(
    monkeypatch, no_lexicon, client_fixture, user_payload_fixture
):
    _register(client_fixture, user_payload_fixture)
    conversation = client_fixture.post(f"{API}/conversations", json={"cities": [CHENGDU]}).json()

    responses = [
        _tool_call_response(
            _tool_call("call_weather", "get_weather", {"city_name": "成都"}),
            _tool_call("call_unknown_city", "get_weather", {"city_name": "上海"}),
        ),
        _final_text_response("It is cloudy in Chengdu (成都), around 18°C."),
    ]
    seen = _patch_chat_completion(monkeypatch, responses)
    _patch_city_weather(monkeypatch)

    body = client_fixture.post(
        f"{API}/conversations/{conversation['id']}/messages",
        json={"content": "What is the weather like in Chengdu?", "locale": "en-US"},
    ).json()

    activities = body["activities"]
    assert activities[0] == {
        "type": "weather",
        "status": "success",
        "code": "agent.weather_found",
        "params": {"city_name": "成都", "city_adcode": "510100"},
        "text": "已查询成都天气",  # v0.3 中文原文仅作向后兼容
    }
    # 未选城市 -> 受控拒绝,而不是伪造成功;params 里的城市仍是原始中文
    assert activities[1]["code"] == "agent.tool_rejected"
    assert activities[1]["status"] == "error"
    assert activities[1]["params"] == {"city_name": "上海"}

    # 英文 locale 用的是英文 system prompt,并要求 English (中文) 形式与双语字段
    system_prompt = seen[0][0]["content"]
    assert "natural, idiomatic English" in system_prompt
    assert "English name (中文名称)" in system_prompt
    assert "name_en" in system_prompt
    # 用户原文与历史消息绝不翻译
    assert seen[0][-1]["content"] == "What is the weather like in Chengdu?"
    messages = client_fixture.get(f"{API}/conversations/{conversation['id']}/messages").json()
    assert messages[0]["content"] == "What is the weather like in Chengdu?"


def test_default_locale_keeps_chinese_prompt(monkeypatch, no_lexicon, client_fixture, user_payload_fixture):
    _register(client_fixture, user_payload_fixture)
    conversation = client_fixture.post(f"{API}/conversations", json={"cities": [CHENGDU]}).json()
    seen = _patch_chat_completion(monkeypatch, [_final_text_response("好的,成都适合秋天去。")])

    response = client_fixture.post(
        f"{API}/conversations/{conversation['id']}/messages", json={"content": "成都什么时候去最好?"}
    )

    assert response.status_code == 200
    assert "用简洁、友好的中文回答" in seen[0][0]["content"]
    assert "natural, idiomatic English" not in seen[0][0]["content"]


def test_history_messages_are_never_rewritten(
    monkeypatch, no_lexicon, client_fixture, user_payload_fixture
):
    _register(client_fixture, user_payload_fixture)
    conversation = client_fixture.post(f"{API}/conversations", json={"cities": [CHENGDU]}).json()
    _patch_chat_completion(monkeypatch, [_final_text_response("成都今天多云。")])

    assert (
        client_fixture.post(
            f"{API}/conversations/{conversation['id']}/messages", json={"content": "成都天气怎么样?"}
        ).status_code
        == 200
    )

    # 切成英文再问一句:新回答用当前语言,历史原文一个字都不动
    _patch_chat_completion(monkeypatch, [_final_text_response("Chengdu (成都) is lovely in autumn.")])
    assert (
        client_fixture.post(
            f"{API}/conversations/{conversation['id']}/messages",
            json={"content": "When should I visit?", "locale": "en-US"},
        ).status_code
        == 200
    )

    messages = client_fixture.get(f"{API}/conversations/{conversation['id']}/messages").json()
    assert [message["content"] for message in messages] == [
        "成都天气怎么样?",
        "成都今天多云。",
        "When should I visit?",
        "Chengdu (成都) is lovely in autumn.",
    ]


def test_agent_tools_return_bilingual_entities_for_english(override_test_db, monkeypatch, lexicon):
    """英文 locale 下工具给模型的双语字段来自词典/缓存,事实字段不变。"""
    session = next(override_test_db())
    try:
        from app.models.user import User
        from app.services import conversation_service
        from app.services.amap_client import RESTAURANT_TYPES

        user = User(username="i18n", email="i18n@example.com", password_hash="not-a-real-hash")
        session.add(user)
        session.commit()
        session.refresh(user)
        conversation = conversation_service.create_conversation(session, user.id, [HANGZHOU])
        context = agent_service.build_agent_context(session, user.id, conversation, LOCALE_EN_US)

        _install_deepseek(monkeypatch)

        async def fake_search_pois(city_name, keyword=None, category=None, page=1, page_size=10):
            assert category == RESTAURANT_TYPES
            return {
                "status": "1",
                "count": "1",
                "pois": [
                    dict(_poi("R900", name="楼外楼"), typecode="050100", type="餐饮服务;中餐厅")
                ],
            }

        monkeypatch.setattr(amap_client, "search_pois", fake_search_pois)

        import asyncio

        result = asyncio.run(
            agent_tools.execute_tool("search_food", {"city_name": "杭州", "keyword": "西湖醋鱼"}, context)
        )

        assert result["ok"] is True
        item = result["data"]["items"][0]
        assert item["name"] == "楼外楼"
        assert item["name_en"] == "EN 楼外楼"
        assert item["poi_id"] == "R900"
        # params/keyword 保持原始中文
        assert result["data"]["keyword"] == "西湖醋鱼"
    finally:
        session.close()


# --------------------------------------------------------------------------- #
# 7. 错误码基座(契约 §5)
# --------------------------------------------------------------------------- #
def test_app_error_carries_detail_error_code_and_message_key():
    error = errors.AppError(errors.QUERY_UNRECOGNIZED)
    assert error.status_code == 422
    assert error.to_response_body() == {
        "detail": errors.ERROR_CODE_DETAILS["query.unrecognized"],
        "error_code": "query.unrecognized",
        "message_key": "error.query.unrecognized",
    }
    # 未登记的 code 也能用,但状态码给通用 400
    custom = errors.AppError("custom.unknown_code", detail="自定义文案")
    assert custom.status_code == 400
    assert custom.message_key == "error.custom.unknown_code"
    assert custom.detail == "自定义文案"


def test_query_translation_service_order_is_contract_order(monkeypatch, lexicon):
    """resolve_search_keyword 的顺序:alias -> 实体英文名 -> 中文字面 -> 受控翻译。"""
    import asyncio

    assert asyncio.run(query_translation_service.resolve_search_keyword(None, "ancient town")) == "古镇"
    assert asyncio.run(query_translation_service.resolve_search_keyword(None, "West Lake")) == "西湖"
    assert asyncio.run(query_translation_service.resolve_search_keyword(None, " 火锅 ")) == "火锅"

    # 词典未命中 -> 受控翻译
    _install_deepseek(monkeypatch, query_keyword="庙会")
    assert asyncio.run(query_translation_service.resolve_search_keyword(None, "temple fair")) == "庙会"

    # 翻译失败 -> AppError(query.unrecognized)
    _install_deepseek(monkeypatch, query_fail=True)
    with pytest.raises(errors.AppError) as excinfo:
        asyncio.run(query_translation_service.resolve_search_keyword(None, "temple fair"))
    assert excinfo.value.code == "query.unrecognized"
    assert excinfo.value.status_code == 422
