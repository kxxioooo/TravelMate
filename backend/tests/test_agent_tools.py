"""Agent Tool 测试(§41.3,8 个):

偏好工具、天气工具(已选城市 / 未选城市)、景点工具、美食工具(默认 / 关键词)、
未知工具被拒、工具结果绝不编造缺失的餐厅字段。

DeepSeek 与高德调用全部 mock,测试不消耗真实 quota。
这些测试直接对着 `agent_tools.execute_tool()`(Agent 唯一的工具入口)跑,
因此"模型只能拿到白名单参数 + 城市只能来自当前 Conversation"这两条规则一并被验证。
"""

import asyncio
import json

import pytest

from app.models.conversation_city import ConversationCity
from app.models.preference import UserPreference
from app.models.user import User
from app.schemas.attraction import AttractionSummary, PagedAttractionResponse
from app.schemas.food import (
    FeaturedFoodItem,
    FeaturedFoodResponse,
    PagedRestaurantResponse,
    RestaurantSummary,
)
from app.schemas.weather import WeatherInfo, WeatherResponse
from app.services import (
    agent_service,
    agent_tools,
    amap_client,
    attraction_service,
    conversation_service,
    deepseek_client,
    food_service,
    weather_service,
)

CHENGDU = {"city_name": "成都", "adcode": "510100"}
CHONGQING = {"city_name": "重庆", "adcode": "500000"}


@pytest.fixture
def db_session(override_test_db):
    """内存 SQLite 上的真实 Session(Agent 工具需要 db + user_id 上下文)。"""
    session = next(override_test_db())
    try:
        yield session
    finally:
        session.close()


def _make_context(db, cities=None):
    """造一个用户 + 一个会话,并构造 Agent 上下文。"""
    user = User(username="agent", email="agent@example.com", password_hash="not-a-real-hash")
    db.add(user)
    db.commit()
    db.refresh(user)

    conversation = conversation_service.create_conversation(db, user.id, cities or [])
    context = agent_service.build_agent_context(db, user.id, conversation)
    return user, conversation, context


def _run(tool_name, arguments, context):
    return asyncio.run(agent_tools.execute_tool(tool_name, arguments, context))


def _weather_response():
    return WeatherResponse(
        weather=WeatherInfo(
            weather="多云",
            temperature=18.0,
            min_temperature=15.0,
            max_temperature=22.0,
            humidity=60.0,
            wind_direction="北",
            wind_power="2",
        ),
        clothing_advice="薄外套",
    )


def test_get_user_preferences_tool(db_session):
    user, conversation, context = _make_context(db_session, [CHENGDU])

    # 新用户没有偏好记录:返回统一空结构,不伪造任何偏好
    empty = _run("get_user_preferences", {}, context)
    assert empty == {
        "ok": True,
        "data": {
            "attraction_preferences": [],
            "food_preferences": [],
            "budget": None,
            "travel_pace": None,
        },
        "error": None,
    }

    db_session.add(
        UserPreference(
            user_id=user.id,
            attraction_preferences=["自然风景"],
            food_preferences=["辣"],
            budget="普通",
            travel_pace="悠闲",
        )
    )
    db_session.commit()

    # 模型硬塞 user_id 也没用:参数被白名单丢掉,身份只来自服务端 context
    result = _run("get_user_preferences", {"user_id": 987654}, context)
    assert result["ok"] is True
    assert result["data"] == {
        "attraction_preferences": ["自然风景"],
        "food_preferences": ["辣"],
        "budget": "普通",
        "travel_pace": "悠闲",
    }

    # 四个工具就是四个,而且参数 JSON Schema 里绝不出现 user_id
    definitions = agent_tools.build_tool_definitions()
    assert [item["function"]["name"] for item in definitions] == list(agent_tools.AGENT_TOOL_NAMES)
    parameters = [item["function"]["parameters"] for item in definitions]
    assert "user_id" not in json.dumps(parameters, ensure_ascii=False)
    assert [sorted(item["properties"]) for item in parameters] == [
        [],
        ["city_name"],
        ["city_name", "keyword"],
        ["city_name", "keyword"],
    ]


def test_get_weather_tool_for_selected_city(monkeypatch, db_session):
    user, conversation, context = _make_context(db_session, [CHENGDU, CHONGQING])
    calls = []

    async def fake_get_city_weather(adcode):
        calls.append(adcode)
        return _weather_response()

    monkeypatch.setattr(weather_service, "get_city_weather", fake_get_city_weather)

    result = _run("get_weather", {"city_name": "重庆"}, context)

    assert result["ok"] is True
    # 用的是 Conversation 里那个城市的 adcode,而不是城市名
    assert calls == ["500000"]
    assert result["data"]["city_name"] == "重庆"
    assert result["data"]["adcode"] == "500000"
    assert result["data"]["weather"]["weather"] == "多云"
    assert result["data"]["weather"]["temperature"] == 18.0
    assert result["data"]["clothing_advice"] == "薄外套"


def test_get_weather_rejects_unselected_city(monkeypatch, db_session):
    user, conversation, context = _make_context(db_session, [CHENGDU])

    async def should_not_be_called(adcode):
        raise AssertionError("未选择城市时绝不能调用天气服务")

    monkeypatch.setattr(weather_service, "get_city_weather", should_not_be_called)

    rejected = _run("get_weather", {"city_name": "上海"}, context)

    assert rejected == {
        "ok": False,
        "data": None,
        "error": "当前对话未选择该城市,请先选择城市或明确调整会话城市。",
    }
    # 绝不偷偷把城市加进会话
    refreshed = conversation_service.get_owned_conversation(db_session, user.id, conversation.id)
    assert [city.city_name for city in refreshed.cities] == ["成都"]
    assert db_session.query(ConversationCity).count() == 1

    # 缺少城市参数是另一个受控错误
    assert _run("get_weather", {}, context)["error"] == agent_tools.MISSING_CITY_MESSAGE

    # 景点 / 美食工具同样遵守"城市必须已在会话里"
    assert _run("search_attractions", {"city_name": "上海"}, context)["error"] == (
        agent_tools.UNSELECTED_CITY_MESSAGE
    )
    assert _run("search_food", {"city_name": "上海", "keyword": "火锅"}, context)["error"] == (
        agent_tools.UNSELECTED_CITY_MESSAGE
    )


def test_search_attractions_tool(monkeypatch, db_session):
    user, conversation, context = _make_context(db_session, [CHENGDU])
    calls = []

    async def fake_get_featured_attractions(city_name, adcode=None):
        calls.append(("featured", city_name, adcode))
        return PagedAttractionResponse(
            items=[
                AttractionSummary(
                    poi_id="B001", name="宽窄巷子", cover_photo=None, rating=4.5, tags=["风景名胜"]
                )
            ],
            page=1,
            page_size=10,
            has_more=False,
            total=1,
        )

    async def fake_search_attractions(city_name, adcode=None, keyword="", page=1, page_size=20):
        calls.append(("search", city_name, adcode, keyword, page, page_size))
        return PagedAttractionResponse(
            items=[
                AttractionSummary(
                    poi_id="B002", name="青城山", cover_photo=None, rating=4.7, tags=["自然风景"]
                )
            ],
            page=page,
            page_size=page_size,
            has_more=False,
            total=1,
        )

    monkeypatch.setattr(attraction_service, "get_featured_attractions", fake_get_featured_attractions)
    monkeypatch.setattr(attraction_service, "search_attractions", fake_search_attractions)

    featured = _run("search_attractions", {"city_name": "成都"}, context)
    searched = _run("search_attractions", {"city_name": "成都", "keyword": "自然风景"}, context)

    assert calls[0] == ("featured", "成都", "510100")
    assert calls[1] == ("search", "成都", "510100", "自然风景", 1, 10)
    assert featured["ok"] is True
    assert featured["data"]["keyword"] is None
    assert featured["data"]["items"][0]["name"] == "宽窄巷子"
    assert searched["data"]["items"][0]["name"] == "青城山"
    # 给 Agent 不要一次返回几十条
    assert len(searched["data"]["items"]) <= 10


def test_search_food_featured_mode(monkeypatch, db_session):
    user, conversation, context = _make_context(db_session, [CHENGDU])
    calls = []

    async def fake_get_featured_foods(city_name, adcode=None):
        calls.append((city_name, adcode))
        return FeaturedFoodResponse(
            items=[
                FeaturedFoodItem(
                    name="火锅",
                    description="麻辣鲜香。",
                    cover_photo="http://store.is.autonavi.com/R1.jpg",
                    representative_restaurants=[
                        RestaurantSummary(poi_id="R1", name="蜀大侠火锅")
                    ],
                )
            ]
        )

    monkeypatch.setattr(food_service, "get_featured_foods", fake_get_featured_foods)

    result = _run("search_food", {"city_name": "成都"}, context)

    assert result["ok"] is True
    assert calls == [("成都", "510100")]
    assert result["data"]["mode"] == "featured"
    assert result["data"]["keyword"] is None
    assert result["data"]["items"][0]["name"] == "火锅"
    assert result["data"]["items"][0]["representative_restaurants"] == [
        {"poi_id": "R1", "name": "蜀大侠火锅"}
    ]


def test_search_food_keyword_mode(monkeypatch, db_session):
    user, conversation, context = _make_context(db_session, [CHENGDU])
    calls = []

    async def fake_search_food_restaurants(city_name, keyword, page=1, page_size=20, adcode=None):
        calls.append(
            {
                "city_name": city_name,
                "keyword": keyword,
                "page": page,
                "page_size": page_size,
                "adcode": adcode,
            }
        )
        return PagedRestaurantResponse(
            items=[RestaurantSummary(poi_id="R1", name="蜀大侠火锅")],
            page=page,
            page_size=page_size,
            has_more=False,
            total=1,
        )

    monkeypatch.setattr(food_service, "search_food_restaurants", fake_search_food_restaurants)

    result = _run("search_food", {"city_name": "成都", "keyword": "火锅"}, context)

    assert result["ok"] is True
    assert calls == [
        {
            "city_name": "成都",
            "keyword": "火锅",
            "page": 1,
            "page_size": 10,
            "adcode": "510100",
        }
    ]
    assert result["data"]["mode"] == "restaurants"
    assert result["data"]["keyword"] == "火锅"
    assert result["data"]["items"] == [{"poi_id": "R1", "name": "蜀大侠火锅"}]

    # Activity 文案按 §34 的规则生成
    activity = agent_service.build_activity("search_food", {"city_name": "成都", "keyword": "火锅"}, result)
    assert activity == {"type": "food", "status": "success", "text": "已找到成都“火锅”相关餐厅"}


def test_unknown_tool_rejected(db_session):
    user, conversation, context = _make_context(db_session, [CHENGDU])

    unknown = _run("delete_all_conversations", {}, context)
    assert unknown["ok"] is False
    assert unknown["data"] is None
    assert "未知工具" in unknown["error"]

    # 白名单之外的名字绝不执行(没有 eval / 没有动态导入)
    assert _run("__import__", {"name": "os"}, context)["ok"] is False
    assert _run("eval", {"code": "1+1"}, context)["ok"] is False
    assert _run("get_weather_tool", {"city_name": "成都"}, context)["ok"] is False

    # 模型给了坏 JSON:normalize_tool_calls 容错成 None,dispatcher 给受控错误(绝不 500)
    response = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_bad",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"city_name": "成都"',
                            },
                        }
                    ]
                }
            }
        ]
    }
    normalized = deepseek_client.normalize_tool_calls(response)
    assert normalized == [{"id": "call_bad", "name": "get_weather", "arguments": None}]
    assert _run("get_weather", normalized[0]["arguments"], context) == {
        "ok": False,
        "data": None,
        "error": agent_tools.INVALID_ARGUMENTS_MESSAGE,
    }

    # 正常形态仍然解析成 dict
    good = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_ok",
                            "type": "function",
                            "function": {
                                "name": "search_food",
                                "arguments": '{"city_name": "成都", "keyword": "火锅"}',
                            },
                        }
                    ]
                }
            }
        ]
    }
    assert deepseek_client.normalize_tool_calls(good)[0]["arguments"] == {
        "city_name": "成都",
        "keyword": "火锅",
    }


def test_tool_result_never_fabricates_missing_restaurant_fields(monkeypatch, db_session):
    user, conversation, context = _make_context(db_session, [CHENGDU])

    dirty_poi = {
        "id": "R404",
        "name": "信息缺失小吃店",
        "address": [],
        "tel": [],
        "biz_ext": {"rating": [], "cost": []},
        "photos": [],
    }

    async def fake_search_pois(city_name, keyword=None, category=None, page=1, page_size=10):
        return {"status": "1", "count": "1", "pois": [dirty_poi]}

    monkeypatch.setattr(amap_client, "search_pois", fake_search_pois)

    result = _run("search_food", {"city_name": "成都", "keyword": "小吃"}, context)

    assert result["ok"] is True
    # 只有高德真实给到的 poi_id / name:缺失的价格 / 地址 / 评分 / 电话保持缺失
    assert result["data"]["items"] == [{"poi_id": "R404", "name": "信息缺失小吃店"}]

    serialized = json.dumps(result, ensure_ascii=False)
    for fabricated in ("cost", "rating", "address", "telephone", "tel", "人均", "评分", "营业时间"):
        assert fabricated not in serialized
