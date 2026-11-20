"""Agent 的四个核心工具(§29 / §30 + 任务书 §3.3)。

铁律:
1. 工具只做"校验参数 + 复用 service + 返回结构化真实数据",绝不重写天气/景点/餐厅逻辑;
2. **城市是软上下文**(任务书 §0.1 / §3.3):会话标签只用于理解用户可能关注的目的地,
   **不是**查询白名单。用户明确问到的任何受支持中国城市都能查;
   未明确城市且只有一个标签时才用标签作默认;多个可能城市要求澄清;
3. `user_id` 只能来自服务端 context,工具 JSON Schema 里没有 user_id,
   模型就算硬传也会被参数白名单丢掉(§43.1 / §43.2);
4. `execute_tool` 是白名单 dispatcher,禁止 eval(§30.6 / §43.3)。

统一返回信封(便于 Agent 循环与 Activity 判断):
    {"ok": True,  "data": {...}, "error": None}
    {"ok": False, "data": None,  "error": "受控错误说明",
     "error_code": "CITY_REQUIRED" | "CITY_AMBIGUOUS" | "CITY_UNKNOWN" | ...,
     "candidates": [...]}

v0.3.1(契约 §8):工具的**名称与参数名不变**;英文 locale 下补 bilingual 字段,
英文搜索关键词先解析成中文再查高德。
"""

from collections.abc import Mapping, Sequence
from typing import Any, Optional

from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import AppError
from app.core.locale import DEFAULT_LOCALE, LOCALE_EN_US
from app.services import (
    attraction_service,
    city_catalog_service,
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

#: 城市解析的稳定错误码(任务书 §3.3)
ERROR_CITY_REQUIRED = "CITY_REQUIRED"
ERROR_CITY_AMBIGUOUS = "CITY_AMBIGUOUS"
ERROR_CITY_UNKNOWN = "CITY_UNKNOWN"

UNKNOWN_TOOL_MESSAGE = "未知工具:{name}"
TOOL_FAILED_MESSAGE = "工具 {name} 执行失败"
INVALID_ARGUMENTS_MESSAGE = "工具参数不是合法的 JSON 对象"
PREFERENCES_FAILED_MESSAGE = "偏好读取失败"
WEATHER_FAILED_MESSAGE = "天气查询失败"
ATTRACTION_FAILED_MESSAGE = "景点查询失败"
FOOD_FAILED_MESSAGE = "美食查询失败"
KEYWORD_UNRECOGNIZED_MESSAGE = "无法可靠识别该搜索词,请换一个中文或英文关键词"

#: 城市没解析出来时的说明(不再有"未选择该城市"的拒绝语义)
CITY_REQUIRED_MESSAGE = "还无法确定要查哪个城市,请告诉用户补充城市名"
CITY_AMBIGUOUS_MESSAGE = "这个城市名对应多个城市,需要用户确认是哪一个"
CITY_UNKNOWN_MESSAGE = "当前目录里没有这个城市,请让用户确认城市名"

#: 每个工具允许模型提供的参数名;多余参数(例如伪造的 user_id)一律丢弃
_TOOL_PARAMETERS: dict[str, tuple[str, ...]] = {
    TOOL_GET_USER_PREFERENCES: (),
    TOOL_GET_WEATHER: ("city_name",),
    TOOL_SEARCH_ATTRACTIONS: ("city_name", "keyword"),
    TOOL_SEARCH_FOOD: ("city_name", "keyword"),
}


def _ok(data: Mapping[str, Any]) -> dict[str, Any]:
    return {"ok": True, "data": dict(data), "error": None}


def _fail(
    message: str,
    *,
    error_code: Optional[str] = None,
    candidates: Optional[Sequence[Mapping[str, Any]]] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "data": None, "error": message}
    if error_code:
        payload["error_code"] = error_code
    if candidates:
        payload["candidates"] = [dict(item) for item in candidates]
    return payload


def _clean_str(value: Any) -> Optional[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _selected_cities(context: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cities = context.get("cities") if isinstance(context, Mapping) else None
    return [city for city in cities or [] if isinstance(city, Mapping)]


def _context_locale(context: Mapping[str, Any]) -> str:
    """本次请求的 locale(缺省 zh-CN):只影响展示字段,不影响任何事实字段。"""
    if isinstance(context, Mapping) and isinstance(context.get("locale"), str):
        return context.get("locale") or DEFAULT_LOCALE
    return DEFAULT_LOCALE


def _resolve_city_for_tool(
    context: Mapping[str, Any], city_name: Any
) -> tuple[Optional[city_catalog_service.CityRecord], Optional[dict[str, Any]]]:
    """把工具收到的 city_name 解析成目录里的规范城市(任务书 §3.2 / §3.3)。

    显式城市从**全目录**解析;没给城市时,只有会话只有一个标签才用它作默认。
    返回 ``(city, failure)``,二者恰有一个非空。
    """
    resolution = city_catalog_service.resolve_city(city_name, _selected_cities(context))

    if resolution.resolved:
        return resolution.city, None

    candidates = [c.to_payload() for c in resolution.candidates]

    if resolution.status == "ambiguous":
        return None, _fail(
            CITY_AMBIGUOUS_MESSAGE, error_code=ERROR_CITY_AMBIGUOUS, candidates=candidates
        )
    if resolution.status == "unknown":
        return None, _fail(
            CITY_UNKNOWN_MESSAGE, error_code=ERROR_CITY_UNKNOWN, candidates=candidates
        )
    return None, _fail(CITY_REQUIRED_MESSAGE, error_code=ERROR_CITY_REQUIRED, candidates=candidates)


def _city_payload(city: city_catalog_service.CityRecord) -> dict[str, Any]:
    """给模型的城市信息:中文原名 + adcode + 审核过的英文名(如果有)。"""
    payload: dict[str, Any] = {
        "city_name": city.city_name,
        "adcode": city.adcode,
    }
    if city.province:
        payload["province"] = city.province
    city_name_en = city.city_name_en or entity_localization_service.lookup_city_translation(
        city.city_name
    )
    if city_name_en:
        payload["city_name_en"] = city_name_en
    if city.province_en:
        payload["province_en"] = city.province_en
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

    城市工具的描述强调"任意受支持城市 + 标签只是默认值 + 多候选需澄清";
    ``city_name`` 改为**可选**(会话只有一个标签时可省略)。
    所有 schema 里都没有 user_id —— 用户身份属于服务端上下文。
    """
    city_param = {
        "type": "string",
        "description": (
            "用户问题里提到的中国城市名(中文或英文均可,如 成都 / Chengdu / 610100)。"
            "用户没明确说城市时可以省略,系统会用会话唯一的城市标签作默认。"
        ),
    }
    city_description = (
        "查询用户提及的任意受支持中国城市;未明确城市时可使用唯一会话城市标签;"
        "多个可能城市需要先澄清。"
    )

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
                "description": f"查询指定城市的实时天气与穿衣建议。{city_description}",
                "parameters": {
                    "type": "object",
                    "properties": {"city_name": city_param},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": TOOL_SEARCH_ATTRACTIONS,
                "description": (
                    f"查询指定城市的景点事实数据(名称、评分、标签、封面图)。{city_description}"
                    "keyword 为空时返回该城市热门景点,非空时按关键词搜索景点。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city_name": city_param,
                        "keyword": {
                            "type": "string",
                            "description": "可选关键词,如 自然风景 / 博物馆;不需要就省略",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": TOOL_SEARCH_FOOD,
                "description": (
                    f"查询指定城市的美食与餐厅事实数据。{city_description}"
                    "keyword 为空时返回该城市代表性美食,非空时按美食关键词搜索餐厅(如 火锅)。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city_name": city_param,
                        "keyword": {
                            "type": "string",
                            "description": "可选美食关键词,如 火锅 / 小吃;不需要就省略",
                        },
                    },
                    "required": [],
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
    """查询任意受支持城市的实时天气,数据来自 v0.2 的 weather_service。"""
    city, failure = _resolve_city_for_tool(context, city_name)
    if city is None:
        return failure or _fail(CITY_REQUIRED_MESSAGE, error_code=ERROR_CITY_REQUIRED)

    try:
        weather = await weather_service.get_city_weather(city.adcode)
    except AmapError:
        return _fail(WEATHER_FAILED_MESSAGE)

    payload = _city_payload(city)
    payload.update(weather.model_dump(mode="json"))
    payload["city_name"] = city.city_name
    payload["adcode"] = city.adcode
    return _ok(payload)


async def search_attractions_tool(
    context: Mapping[str, Any], city_name: Optional[str] = None, keyword: Optional[str] = None
) -> dict[str, Any]:
    """查询指定城市的景点:keyword 为空走默认 Top 10,非空走搜索。"""
    city, failure = _resolve_city_for_tool(context, city_name)
    if city is None:
        return failure or _fail(CITY_REQUIRED_MESSAGE, error_code=ERROR_CITY_REQUIRED)

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
                city_name=city.city_name,
                adcode=city.adcode,
                keyword=resolved_keyword,
                page=1,
                page_size=ATTRACTION_PAGE_SIZE,
            )
        else:
            paged = await attraction_service.get_featured_attractions(
                city_name=city.city_name, adcode=city.adcode
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
    """查询指定城市的美食 / 餐厅,数据来自 v0.2 的 food_service。"""
    city, failure = _resolve_city_for_tool(context, city_name)
    if city is None:
        return failure or _fail(CITY_REQUIRED_MESSAGE, error_code=ERROR_CITY_REQUIRED)

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
                city_name=city.city_name,
                keyword=resolved_keyword,
                page=1,
                page_size=FOOD_PAGE_SIZE,
                adcode=city.adcode,
            )
            localized = await _localize_restaurant_items(context, paged.items)
            items = [item.model_dump(mode="json") for item in localized]
            total: Optional[int] = paged.total
            has_more: Optional[bool] = paged.has_more
            mode = "restaurants"
        else:
            featured = await food_service.get_featured_foods(
                city_name=city.city_name, adcode=city.adcode
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
    - 城市缺席不再在此处拦截:交给工具按"软上下文"规则解析(任务书 §3.3);
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
            return await get_weather_tool(context, **kwargs)
        if tool_name == TOOL_SEARCH_ATTRACTIONS:
            return await search_attractions_tool(context, **kwargs)
        if tool_name == TOOL_SEARCH_FOOD:
            return await search_food_tool(context, **kwargs)
    except Exception:  # noqa: BLE001 - 单个工具失败绝不能中断整轮工具循环
        return _fail(TOOL_FAILED_MESSAGE.format(name=tool_name))

    return _fail(UNKNOWN_TOOL_MESSAGE.format(name=tool_name))
