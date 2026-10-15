"""美食测试:10 种代表作 / 每种最多 2 家餐厅 / 搜索与分页 / 详情 / 缺失字段 / DeepSeek 解析。

DeepSeek 与高德调用全部 mock,测试不消耗真实 quota。
限流保护(重试 + Semaphore)也在 test_food_search_restaurants 里验证。
"""

import asyncio
import inspect
from types import SimpleNamespace

from app.schemas.food import RestaurantDetail
from app.services import amap_client, deepseek_food_client, food_service

API = "/api/v1"

# 模块级保存真实实现:monkeypatch 只替换 amap_client 上的属性,这里仍指向原函数
_REAL_SEARCH_POIS = amap_client.search_pois


def _register(client, payload):
    assert client.post(f"{API}/auth/register", json=payload).status_code == 201


def _restaurant(poi_id, name="陈麻婆豆腐", rating="4.7", cost="73.00", photos=True, tel="15328052249;18140097359"):
    return {
        "id": poi_id,
        "name": name,
        "type": "餐饮服务;中餐厅;中餐厅",
        "typecode": "050100",
        "address": "四川省成都市青羊区西玉龙街",
        "location": "104.077761,30.651100",
        "tel": tel,
        "biz_ext": {"rating": rating, "cost": cost},
        "photos": [{"title": [], "url": f"http://store.is.autonavi.com/{poi_id}.jpg"}]
        if photos
        else [],
    }


def _fake_foods(count=10):
    return [{"name": f"美食{i:02d}", "description": f"第 {i} 道当地代表性美食的简介。"} for i in range(1, count + 1)]


def _patch_deepseek(monkeypatch, foods=None):
    async def fake_generate(city_name):
        assert city_name
        return [dict(food) for food in (foods if foods is not None else _fake_foods())]

    monkeypatch.setattr(deepseek_food_client, "generate_representative_foods", fake_generate)
    # 测试里不需要真实等待,避免拖慢用例
    monkeypatch.setattr(food_service, "FOOD_REQUEST_INTERVAL_SECONDS", 0)


def _patch_restaurant_search(monkeypatch, handler):
    """handler 可以是同步或异步函数,统一被 await。"""

    async def fake_search_pois(city_name, keyword=None, category=None, page=1, page_size=10):
        result = handler(
            city_name=city_name, keyword=keyword, category=category, page=page, page_size=page_size
        )
        if inspect.isawaitable(result):
            result = await result
        return result

    monkeypatch.setattr(amap_client, "search_pois", fake_search_pois)


def test_featured_foods_target_10(monkeypatch, client_fixture, user_payload_fixture):
    calls = []
    concurrency = {"current": 0, "peak": 0}

    async def handler(**kwargs):
        calls.append(kwargs)
        concurrency["current"] += 1
        concurrency["peak"] = max(concurrency["peak"], concurrency["current"])
        try:
            await asyncio.sleep(0.01)  # 让并发真的重叠,用于验证 Semaphore 上限
        finally:
            concurrency["current"] -= 1
        return {"status": "1", "count": "63", "pois": [_restaurant(f"R{kwargs['keyword']}-{i}") for i in range(2)]}

    _patch_deepseek(monkeypatch)
    _patch_restaurant_search(monkeypatch, handler)
    _register(client_fixture, user_payload_fixture)

    response = client_fixture.get(f"{API}/food/featured", params={"city_name": "成都", "adcode": "510100"})

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 10
    assert [item["name"] for item in items] == [food["name"] for food in _fake_foods()]
    assert all(item["description"] for item in items)
    # 每种美食一次高德查询,菜名作为 keyword,类别码 050000
    assert len(calls) == 10
    assert {call["keyword"] for call in calls} == {food["name"] for food in _fake_foods()}
    assert all(call["category"] == "050000" for call in calls)
    # 并发是并发的,但受 Semaphore(3) 限制
    assert 1 < concurrency["peak"] <= food_service.MAX_CONCURRENT_AMAP_REQUESTS


def test_each_food_has_at_most_2_restaurants(monkeypatch, client_fixture, user_payload_fixture):
    def handler(**kwargs):
        if kwargs["keyword"] == "美食03":
            # 单个美食被限流/失败:只让这一项没有餐厅
            raise amap_client.AmapError(amap_client.UNAVAILABLE_MESSAGE)
        # 故意多返回,服务层必须自己截到 2 家
        return {"status": "1", "count": "88", "pois": [_restaurant(f"R{kwargs['keyword']}-{i}") for i in range(5)]}

    _patch_deepseek(monkeypatch)
    _patch_restaurant_search(monkeypatch, handler)
    _register(client_fixture, user_payload_fixture)

    items = client_fixture.get(f"{API}/food/featured", params={"city_name": "成都"}).json()["items"]

    assert len(items) == 10
    for item in items:
        assert len(item["representative_restaurants"]) <= 2
    failed = next(item for item in items if item["name"] == "美食03")
    assert failed["representative_restaurants"] == []
    others = [item for item in items if item["name"] != "美食03"]
    assert all(len(item["representative_restaurants"]) == 2 for item in others)
    # 餐厅列表只暴露 poi_id + name
    assert set(others[0]["representative_restaurants"][0]) == {"poi_id", "name"}


def test_food_search_restaurants(monkeypatch, client_fixture, user_payload_fixture):
    calls = []

    def handler(**kwargs):
        calls.append(kwargs)
        return {"status": "1", "count": "120", "pois": [_restaurant("R001", name="蜀大侠火锅")]}

    _patch_restaurant_search(monkeypatch, handler)
    _register(client_fixture, user_payload_fixture)

    response = client_fixture.get(
        f"{API}/food/restaurants", params={"city_name": "成都", "adcode": "510100", "keyword": "火锅"}
    )

    assert response.status_code == 200
    body = response.json()
    assert calls[0]["keyword"] == "火锅"
    assert calls[0]["category"] == "050000"
    assert calls[0]["city_name"] == "成都"
    assert body["items"] == [{"poi_id": "R001", "name": "蜀大侠火锅"}]
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total"] == 120
    assert body["has_more"] is True

    # 限流重试:第一次 status=0,第二次成功 -> 服务层仍拿到真实结果
    attempts = []

    async def fake_send_request(path, params):
        attempts.append(params)
        if len(attempts) == 1:
            return {"status": "0", "infocode": "10021", "info": "CUQPS_HAS_EXCEEDED_THE_LIMIT", "count": None, "pois": []}
        return {"status": "1", "infocode": "10000", "count": "63", "pois": [_restaurant("R001")]}

    monkeypatch.setattr(amap_client, "_send_request", fake_send_request)
    monkeypatch.setattr(amap_client, "RETRY_DELAYS", (0.0, 0.0))
    monkeypatch.setattr(
        amap_client, "get_settings", lambda: SimpleNamespace(amap_api_key="test_key")
    )

    payload = asyncio.run(
        _REAL_SEARCH_POIS(
            city_name="成都", keyword="火锅", category=amap_client.RESTAURANT_TYPES, page=1, page_size=5
        )
    )

    assert len(attempts) == 2
    assert payload["count"] == "63"
    assert payload["pois"][0]["name"] == "陈麻婆豆腐"


def test_food_search_pagination(monkeypatch, client_fixture, user_payload_fixture):
    calls = []
    total = {"value": "600"}

    def handler(**kwargs):
        calls.append((kwargs["page"], kwargs["page_size"]))
        return {
            "status": "1",
            "count": total["value"],
            "pois": [_restaurant(f"R{kwargs['page']}-{i}") for i in range(kwargs["page_size"])],
        }

    _patch_restaurant_search(monkeypatch, handler)
    _register(client_fixture, user_payload_fixture)

    body = client_fixture.get(
        f"{API}/food/restaurants",
        params={"city_name": "成都", "keyword": "火锅", "page": 3, "page_size": 20},
    ).json()

    assert (body["page"], body["page_size"]) == (3, 20)
    assert len(body["items"]) == 20
    assert body["total"] == 600
    assert body["has_more"] is True
    assert calls[0] == (3, 20)

    total["value"] = "30"
    last_page = client_fixture.get(
        f"{API}/food/restaurants",
        params={"city_name": "成都", "keyword": "火锅", "page": 2, "page_size": 20},
    ).json()
    assert last_page["has_more"] is False

    # 关键词必填
    assert client_fixture.get(f"{API}/food/restaurants", params={"city_name": "成都"}).status_code == 422
    # page_size 上限 20
    assert (
        client_fixture.get(
            f"{API}/food/restaurants",
            params={"city_name": "成都", "keyword": "火锅", "page_size": 100},
        ).status_code
        == 422
    )

    # 空结果:该城市搜不到相关餐厅 -> 空列表 + total 0
    _patch_restaurant_search(monkeypatch, lambda **kwargs: {"status": "1", "count": "0", "pois": []})
    empty = client_fixture.get(
        f"{API}/food/restaurants", params={"city_name": "不存在的城市", "keyword": "火锅"}
    ).json()
    assert empty["items"] == []
    assert empty["total"] == 0
    assert empty["has_more"] is False
    assert empty["page"] == 1


def test_restaurant_detail(monkeypatch, client_fixture, user_payload_fixture):
    async def fake_get_poi_detail(poi_id):
        return _restaurant(poi_id, name="陈麻婆豆腐(骡马市店)")

    monkeypatch.setattr(amap_client, "get_poi_detail", fake_get_poi_detail)
    _register(client_fixture, user_payload_fixture)

    response = client_fixture.get(f"{API}/food/restaurants/R001")

    assert response.status_code == 200
    body = response.json()
    assert body["poi_id"] == "R001"
    assert body["name"] == "陈麻婆豆腐(骡马市店)"
    assert body["cost"] == "73.00"
    assert body["address"] == "四川省成都市青羊区西玉龙街"
    assert body["rating"] == 4.7  # 字符串 "4.7" -> float
    assert body["telephone"] == "15328052249;18140097359"  # 多号码保持原样
    assert body["photos"] == [{"url": "http://store.is.autonavi.com/R001.jpg", "title": None}]


def test_missing_restaurant_fields_not_fabricated(monkeypatch, client_fixture, user_payload_fixture):
    dirty = {
        "id": "R404",
        "name": "信息缺失小吃店",
        "address": [],
        "tel": [],
        "biz_ext": {"rating": [], "cost": []},
        "photos": [],
    }

    detail = food_service.map_restaurant_detail(dirty)
    assert detail == RestaurantDetail(
        poi_id="R404",
        name="信息缺失小吃店",
        cost=None,
        address=None,
        rating=None,
        telephone=None,
        photos=[],
    )

    async def fake_get_poi_detail(poi_id):
        return dirty

    monkeypatch.setattr(amap_client, "get_poi_detail", fake_get_poi_detail)
    _register(client_fixture, user_payload_fixture)

    body = client_fixture.get(f"{API}/food/restaurants/R404").json()
    assert body["cost"] is None
    assert body["address"] is None
    assert body["rating"] is None
    assert body["telephone"] is None
    assert body["photos"] == []
    # 也绝不编造餐厅名字以外的信息
    assert body["name"] == "信息缺失小吃店"


def test_food_cover_uses_real_poi_photo_or_none(monkeypatch, client_fixture, user_payload_fixture):
    # 纯函数层面
    assert food_service.select_food_cover_photo([]) is None
    assert food_service.select_food_cover_photo([_restaurant("R1", photos=False)]) is None
    assert (
        food_service.select_food_cover_photo(
            [_restaurant("R1", photos=False), _restaurant("R2")]
        )
        == "http://store.is.autonavi.com/R2.jpg"
    )
    # build_food_response 在没有显式封面时会自己去餐厅 POI 里找
    built = food_service.build_food_response(
        {"name": "火锅", "description": "麻辣鲜香。"}, [_restaurant("R9")]
    )
    assert built.cover_photo == "http://store.is.autonavi.com/R9.jpg"

    # 接口层面:有真实照片用照片,一张都没有就是 None
    def handler(**kwargs):
        photos = kwargs["keyword"] != "美食02"
        return {"status": "1", "count": "5", "pois": [_restaurant(f"R-{kwargs['keyword']}", photos=photos)]}

    _patch_deepseek(monkeypatch, foods=_fake_foods(2))
    _patch_restaurant_search(monkeypatch, handler)
    _register(client_fixture, user_payload_fixture)

    items = client_fixture.get(f"{API}/food/featured", params={"city_name": "成都"}).json()["items"]

    assert items[0]["cover_photo"] == "http://store.is.autonavi.com/R-美食01.jpg"
    assert items[1]["cover_photo"] is None


def test_deepseek_food_json_parse_failure(monkeypatch, client_fixture, user_payload_fixture):
    # 三种形态都要能解析:裸数组 / {"foods": [...]} / ```json 代码块
    bare = '[{"name": "麻婆豆腐", "description": "麻辣鲜香。"}]'
    wrapped = '{"foods": [{"name": "钟水饺", "description": "皮薄馅嫩。"}]}'
    fenced = '```json\n[{"name": "龙抄手", "description": "汤鲜味美。"}]\n```'

    assert deepseek_food_client.parse_food_json(bare)[0]["name"] == "麻婆豆腐"
    assert deepseek_food_client.parse_food_json(wrapped) == [
        {"name": "钟水饺", "description": "皮薄馅嫩。"}
    ]
    assert deepseek_food_client.parse_food_json(fenced) == [
        {"name": "龙抄手", "description": "汤鲜味美。"}
    ]

    # 去重 + 丢弃脏数据
    validated = deepseek_food_client.validate_food_items(
        [
            {"name": "冒菜", "description": "一人食火锅。"},
            {"name": "冒菜", "description": "重复项。"},
            {"name": "", "description": "没有名字。"},
            "不是对象",
        ]
    )
    assert validated == [{"name": "冒菜", "description": "一人食火锅。"}]

    # 解析失败 -> 可重试业务异常
    for bad in ["这不是 JSON", "", "```json\n{不是合法 json}\n```", "[]"]:
        try:
            items = deepseek_food_client.parse_food_json(bad)
        except deepseek_food_client.FoodDataError as exc:
            assert exc.retryable is True
            continue
        # 只有 "[]" 是合法 JSON,但其中没有有效美食,校验阶段必须报错
        assert bad == "[]"
        try:
            deepseek_food_client.validate_food_items(items)
        except deepseek_food_client.FoodDataError as exc:
            assert exc.retryable is True

    # 接口层:DeepSeek 失败 -> 502 + 中文人话,不泄露内部细节
    async def broken_generate(city_name):
        raise deepseek_food_client.FoodDataError(deepseek_food_client.PARSE_ERROR_MESSAGE)

    monkeypatch.setattr(deepseek_food_client, "generate_representative_foods", broken_generate)
    _register(client_fixture, user_payload_fixture)

    response = client_fixture.get(f"{API}/food/featured", params={"city_name": "成都"})

    assert response.status_code == 502
    assert response.json()["detail"] == "美食推荐服务暂时不可用"
    assert "FoodDataError" not in response.text
    assert "api.deepseek.com" not in response.text
