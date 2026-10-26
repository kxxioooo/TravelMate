"""Agent 的四个核心工具(§29 / §30)。不多不少,就是这四个。

铁律:
1. 工具只做"校验参数 + 复用 v0.2 service + 返回结构化真实数据",
   绝不重写天气 / 景点 / 餐厅的 API 逻辑(§45);
2. 城市上下文只能来自当前 Conversation 的 cities:找不到就返回受控提示,
   绝不偷偷把城市加进会话(§29.2 / §38);
3. `user_id` 只能来自服务端 context,工具 JSON Schema 里没有 user_id,
   模型就算硬传也会被参数白名单丢掉(§43.1 / §43.2);
4. `execute_tool` 是白名单 dispatcher,禁止 eval(§30.6 / §43.3)。

统一返回信封(便于 Agent 循环与 Activity 判断):
    {"ok": True,  "data": {...}, "error": None}
    {"ok": False, "data": None,  "error": "受控错误说明"}

v0.3.1(契约 §8):工具的**名称、参数与调用方式完全不变**;
- 英文 locale 下给模型返回一致的 bilingual 实体信息(name_en / name_en_source 等),
  由 `entity_localization_service` 后置补齐,模型据此组成 `English (中文)`;
- 英文搜索关键词先解析成中文再查高德(解析不出来就是受控工具失败,不悄悄丢关键字)。
"""

from collections.abc import Mapping, Sequence
from typing import Any, Optional

from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import AppError
from app.core.locale import DEFAULT_LOCALE, LOCALE_EN_US
from app.services import (
    attraction_service,
    entity_localization_service,
    food_service,
    preference_service,
    query_translation_service,
    weather_service,
)
from app.services.amap_client import AmapError
from app.services.deepseek_client import DeepSeekError

TOOL_GET_USER_PREFERENCES = "get_user_preferences"
TOOL_GET_WEATHER = "get_weather"
TOOL_SEARCH_ATTRACTIONS = "search_attractions"
TOOL_SEARCH_FOOD = "search_food"

#: 只注册这四个工具(§29)
AGENT_TOOL_NAMES = (
    TOOL_GET_USER_PREFERENCES,
    TOOL_GET_WEATHER,
    TOOL_SEARCH_ATTRACTIONS,
    TOOL_SEARCH_FOOD,
)

#: 给 Agent 不需要一次返回几十条 POI(§29.3 / §29.4)
ATTRACTION_PAGE_SIZE = 10
FOOD_PAGE_SIZE = 10

UNSELECTED_CITY_MESSAGE = "当前对话未选择该城市,请先选择城市或明确调整会话城市。"
UNKNOWN_TOOL_MESSAGE = "未知工具:{name}"
TOOL_FAILED_MESSAGE = "工具 {name} 执行失败"
INVALID_ARGUMENTS_MESSAGE = "工具参数不是合法的 JSON 对象"
MISSING_CITY_MESSAGE = "缺少城市参数 city_name"
PREFERENCES_FAILED_MESSAGE = "偏好读取失败"
WEATHER_FAILED_MESSAGE = "天气查询失败"
ATTRACTION_FAILED_MESSAGE = "景点查询失败"
FOOD_FAILED_MESSAGE = "美食查询失败"
KEYWORD_UNRECOGNIZED_MESSAGE = "无法可靠识别该搜索词,请换一个中文或英文关键词"

#: 每个工具允许模型提供的参数名;多余参数(例如伪造的 user_id)一律丢弃
_TOOL_PARAMETERS: dict[str, tuple[str, ...]] = {
    TOOL_GET_USER_PREFERENCES: (),
    TOOL_GET_WEATHER: ("city_name",),
    TOOL_SEARCH_ATTRACTIONS: ("city_name", "keyword"),
    TOOL_SEARCH_FOOD: ("city_name", "keyword"),
}


def _ok(data: Mapping[str, Any]) -> dict[str, Any]:
    return {"ok": True, "data": dict(data), "error": None}


def _fail(message: str) -> dict[str, Any]:
    return {"ok": False, "data": None, "error": message}


def _clean_str(value: Any) -> Optional[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _selected_cities(context: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cities = context.get("cities") if isinstance(context, Mapping) else None
    return [city for city in cities or [] if isinstance(city, Mapping)]


def _find_city(context: Mapping[str, Any], city_name: Any) -> Optional[Mapping[str, Any]]:
    """在当前 Conversation 的 cities 里按 city_name 找城市(§29.2)。

    先精确匹配 city_name;再退一步允许模型直接给 adcode。两者都找不到就是
    "未选择该城市",由调用方返回受控提示,绝不新增城市。
    """
    wanted = _clean_str(city_name)
    if not wanted:
        return None
    for city in _selected_cities(context):
        if _clean_str(city.get("city_name")) == wanted:
            return city
    for city in _selected_cities(context):
        if _clean_str(city.get("adcode")) == wanted:
            return city
    return None


def _context_locale(context: Mapping[str, Any]) -> str:
    """本次请求的 locale(缺省 zh-CN):只影响展示字段,不影响任何事实字段。"""
    if isinstance(context, Mapping) and isinstance(context.get("locale"), str):
        return context.get("locale") or DEFAULT_LOCALE
    return DEFAULT_LOCALE


def _city_payload(city: Mapping[str, Any]) -> dict[str, Any]:
    """给模型的城市信息:中文原名 + adcode(+ 词典里的英文名,如果有)。"""
    payload: dict[str, Any] = {
        "city_name": city.get("city_name"),
        "adcode": city.get("adcode"),
    }
    city_name_en = entity_localization_service.lookup_city_translation(city.get("city_name"))
    if city_name_en:
        payload["city_name_en"] = city_name_en
    return payload


async def _resolve_tool_keyword(
    context: Mapping[str, Any], keyword: str, locale: str
) -> Optional[str]:
    """工具里的关键词同样要落到中文检索词;解析不出来返回 None(受控失败)。"""
    try:
        return await query_translation_service.resolve_search_keyword(
            context.get("db"), keyword, locale
        )
    except AppError:
        return None


async def _localize_attraction_items(
    context: Mapping[str, Any], items: Sequence[Any]
) -> Sequence[Any]:
    """英文 locale 下给模型补 name_en / name_en_source;失败就退回中文(绝不 500)。"""
    locale = _context_locale(context)
    if locale != LOCALE_EN_US or not items:
        return items
    try:
        return await entity_localization_service.localize_attraction_summaries(
            context.get("db"), list(items), locale
        )
    except Exception:  # noqa: BLE001 - 双语化失败不能影响工具结果
        return items


async def _localize_restaurant_items(
    context: Mapping[str, Any], items: Sequence[Any]
) -> Sequence[Any]:
    locale = _context_locale(context)
    if locale != LOCALE_EN_US or not items:
        return items
    try:
        return await entity_localization_service.localize_restaurant_summaries(
            context.get("db"), list(items), locale
        )
    except Exception:  # noqa: BLE001
        return items


async def _localize_featured_food_items(
    context: Mapping[str, Any], items: Sequence[Any]
) -> Sequence[Any]:
    locale = _context_locale(context)
    if locale != LOCALE_EN_US or not items:
        return items
    try:
        return await entity_localization_service.localize_featured_foods(
            context.get("db"), list(items), locale
        )
    except Exception:  # noqa: BLE001
        return items


def build_tool_definitions() -> list[dict[str, Any]]:
    """返回 DeepSeek Tool Calling 需要的 JSON Schema,只注册四个工具(§30.1)。

    注意:所有 schema 里都没有 user_id —— 用户身份属于服务端上下文。
    """
    return [
        {
            "type": "function",
            "function": {
                "name": TOOL_GET_USER_PREFERENCES,
                "description": (
                    "读取当前登录用户的旅行偏好(景点偏好、美食偏好、预算、旅行节奏)。"
                    "用户身份由服务端自动识别,本工具不需要任何参数。"
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": TOOL_GET_WEATHER,
                "description": (
                    "查询当前会话已选择城市的实时天气与穿衣建议。"
                    "city_name 必须是当前会话已选择的城市名,否则工具会返回受控提示。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city_name": {"type": "string", "description": "城市名,如 成都"},
                    },
                    "required": ["city_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": TOOL_SEARCH_ATTRACTIONS,
                "description": (
                    "查询当前会话已选择城市的景点事实数据(名称、评分、标签、封面图)。"
                    "keyword 为空时返回该城市热门景点,非空时按关键词搜索景点。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city_name": {"type": "string", "description": "城市名,如 成都"},
                        "keyword": {
                            "type": "string",
                            "description": "可选关键词,如 自然风景 / 博物馆;不需要就省略",
                        },
                    },
                    "required": ["city_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": TOOL_SEARCH_FOOD,
                "description": (
                    "查询当前会话已选择城市的美食与餐厅事实数据。"
                    "keyword 为空时返回该城市代表性美食,非空时按美食关键词搜索餐厅"
                    "(如 火锅)。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city_name": {"type": "string", "description": "城市名,如 成都"},
                        "keyword": {
                            "type": "string",
                            "description": "可选美食关键词,如 火锅 / 小吃;不需要就省略",
                        },
                    },
                    "required": ["city_name"],
                },
            },
        },
    ]


async def get_user_preferences_tool(context: Mapping[str, Any]) -> dict[str, Any]:
    """读取用户偏好(§29.1):user_id 由服务端注入,模型无法决定。"""
    db = context.get("db")
    user_id = context.get("user_id")
    if db is None or user_id is None:
        return _fail(PREFERENCES_FAILED_MESSAGE)

    try:
        preference = preference_service.get_preferences_by_user_id(db, user_id)
    except SQLAlchemyError:
        return _fail(PREFERENCES_FAILED_MESSAGE)

    if preference is None:
        # 新用户没有偏好记录:如实返回空结构,不伪造任何偏好
        return _ok(
            {
                "attraction_preferences": [],
                "food_preferences": [],
                "budget": None,
                "travel_pace": None,
            }
        )
    return _ok(
        {
            "attraction_preferences": list(preference.attraction_preferences or []),
            "food_preferences": list(preference.food_preferences or []),
            "budget": preference.budget,
            "travel_pace": preference.travel_pace,
        }
    )


async def get_weather_tool(context: Mapping[str, Any], city_name: Optional[str] = None) -> dict[str, Any]:
    """查询会话已选城市的实时天气(§29.2),数据来自 v0.2 的 weather_service。"""
    city = _find_city(context, city_name)
    if city is None:
        return _fail(UNSELECTED_CITY_MESSAGE)

    try:
        weather = await weather_service.get_city_weather(city.get("adcode") or "")
    except AmapError:
        return _fail(WEATHER_FAILED_MESSAGE)

    payload = _city_payload(city)
    payload.update(weather.model_dump(mode="json"))
    payload["city_name"] = city.get("city_name")
    payload["adcode"] = city.get("adcode")
    return _ok(payload)


async def search_attractions_tool(
    context: Mapping[str, Any], city_name: Optional[str] = None, keyword: Optional[str] = None
) -> dict[str, Any]:
    """查询会话已选城市的景点(§29.3):keyword 为空走默认 Top 10,非空走搜索。"""
    city = _find_city(context, city_name)
    if city is None:
        return _fail(UNSELECTED_CITY_MESSAGE)

    locale = _context_locale(context)
    safe_keyword = _clean_str(keyword)
    resolved_keyword: Optional[str] = None
    if safe_keyword:
        # 英文关键词先转成中文再查高德(解析不出来就是受控失败,不丢关键字)
        resolved_keyword = await _resolve_tool_keyword(context, safe_keyword, locale)
        if not resolved_keyword:
            return _fail(KEYWORD_UNRECOGNIZED_MESSAGE)

    try:
        if resolved_keyword:
            paged = await attraction_service.search_attractions(
                city_name=city.get("city_name") or "",
                adcode=city.get("adcode"),
                keyword=resolved_keyword,
                page=1,
                page_size=ATTRACTION_PAGE_SIZE,
            )
        else:
            paged = await attraction_service.get_featured_attractions(
                city_name=city.get("city_name") or "", adcode=city.get("adcode")
            )
    except AmapError:
        return _fail(ATTRACTION_FAILED_MESSAGE)

    items = await _localize_attraction_items(context, paged.items)
    payload = _city_payload(city)
    payload.update(
        {
            "keyword": resolved_keyword,
            "items": [item.model_dump(mode="json") for item in items],
            "total": paged.total,
            "has_more": paged.has_more,
        }
    )
    return _ok(payload)


async def search_food_tool(
    context: Mapping[str, Any], city_name: Optional[str] = None, keyword: Optional[str] = None
) -> dict[str, Any]:
    """查询会话已选城市的美食 / 餐厅(§29.4),数据来自 v0.2 的 food_service。"""
    city = _find_city(context, city_name)
    if city is None:
        return _fail(UNSELECTED_CITY_MESSAGE)

    locale = _context_locale(context)
    safe_keyword = _clean_str(keyword)
    resolved_keyword: Optional[str] = None
    if safe_keyword:
        resolved_keyword = await _resolve_tool_keyword(context, safe_keyword, locale)
        if not resolved_keyword:
            return _fail(KEYWORD_UNRECOGNIZED_MESSAGE)

    try:
        if resolved_keyword:
            paged = await food_service.search_food_restaurants(
                city_name=city.get("city_name") or "",
                keyword=resolved_keyword,
                page=1,
                page_size=FOOD_PAGE_SIZE,
                adcode=city.get("adcode"),
            )
            localized = await _localize_restaurant_items(context, paged.items)
            items = [item.model_dump(mode="json") for item in localized]
            total: Optional[int] = paged.total
            has_more: Optional[bool] = paged.has_more
            mode = "restaurants"
        else:
            featured = await food_service.get_featured_foods(
                city_name=city.get("city_name") or "", adcode=city.get("adcode")
            )
            localized_foods = await _localize_featured_food_items(context, featured.items)
            items = [item.model_dump(mode="json") for item in localized_foods]
            total = len(items)
            has_more = False
            mode = "featured"
    except (AmapError, DeepSeekError, SQLAlchemyError):
        return _fail(FOOD_FAILED_MESSAGE)

    payload = _city_payload(city)
    payload.update(
        {
            "keyword": resolved_keyword,
            "mode": mode,
            "items": items,
            "total": total,
            "has_more": has_more,
        }
    )
    return _ok(payload)


async def execute_tool(
    name: Any, arguments: Optional[Mapping[str, Any]], context: Mapping[str, Any]
) -> dict[str, Any]:
    """白名单 dispatcher(§30.6):按 name 找到工具函数并执行,绝不 eval。

    - 未知 name -> 受控错误;
    - arguments 为 None(模型给了坏 JSON)-> 受控错误;
    - 只把白名单里的参数名透传给工具函数,模型伪造的 user_id 等一律丢弃;
    - 任何工具异常都被兜住,这一轮的其它 tool_call 不受影响(§33)。
    """
    tool_name = _clean_str(name) or ""
    if tool_name not in _TOOL_PARAMETERS:
        return _fail(UNKNOWN_TOOL_MESSAGE.format(name=tool_name or "unknown"))

    if arguments is None:
        return _fail(INVALID_ARGUMENTS_MESSAGE)
    if not isinstance(arguments, Mapping):
        return _fail(INVALID_ARGUMENTS_MESSAGE)

    allowed = _TOOL_PARAMETERS[tool_name]
    kwargs = {key: arguments[key] for key in allowed if key in arguments}

    try:
        if tool_name == TOOL_GET_USER_PREFERENCES:
            return await get_user_preferences_tool(context)
        if tool_name == TOOL_GET_WEATHER:
            if not _clean_str(kwargs.get("city_name")):
                return _fail(MISSING_CITY_MESSAGE)
            return await get_weather_tool(context, **kwargs)
        if tool_name == TOOL_SEARCH_ATTRACTIONS:
            if not _clean_str(kwargs.get("city_name")):
                return _fail(MISSING_CITY_MESSAGE)
            return await search_attractions_tool(context, **kwargs)
        if tool_name == TOOL_SEARCH_FOOD:
            if not _clean_str(kwargs.get("city_name")):
                return _fail(MISSING_CITY_MESSAGE)
            return await search_food_tool(context, **kwargs)
    except Exception:  # noqa: BLE001 - 单个工具失败绝不能中断整轮工具循环
        return _fail(TOOL_FAILED_MESSAGE.format(name=tool_name))

    return _fail(UNKNOWN_TOOL_MESSAGE.format(name=tool_name))
