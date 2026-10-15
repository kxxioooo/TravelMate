"""高德开放平台 HTTP 客户端。

本文件只负责**第三方高德 HTTP 通信**,不含任何 UI / 业务拼装逻辑。

实测事实(务必保持):
1. `weatherInfo` 的实时与预报**不在同一个响应**里:
   - `extensions=base` -> `lives[0]`(weather / temperature / humidity / winddirection / windpower)
   - `extensions=all`  -> `forecasts[0].casts[0]`(daytemp / nighttemp ...),此时 `lives` 可能是空数组
   所以 get_weather() 内部请求两次,再交给 weather_service.normalize_weather() 合并。
2. 默认景点列表不能靠 keywords="景点" 宽匹配(第一条可能是写字楼),
   必须用类别码:`types=110000` 风景名胜、`types=050000` 餐饮。
3. 高德的"缺失值"常常是空数组 `[]`(不是 null),`biz_ext.cost` / `biz_ext.rating` 是**字符串**,
   `location` 是 "经度,纬度" 字符串,`tel` 可能是多号码用 `;` 连接的字符串。
   归一化统一在下层 service 的 map_* 函数里做,这里只保证不崩溃。
4. 这把 Key 有 QPS 限制:连续快速请求会返回 `status=0` + `count=None` + `pois=[]`
   (看起来像"没数据",其实是限流)。间隔重试后能拿到真实结果,
   所以 request_amap 内置最多 2 次重试 + 指数退避。

安全:任何失败都转成后端自定义异常,异常文本里绝不含 Key 或完整 URL。
"""

import asyncio
import logging
from typing import Any, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

AMAP_BASE_URL = "https://restapi.amap.com"
WEATHER_PATH = "/v3/weather/weatherInfo"
PLACE_TEXT_PATH = "/v3/place/text"
PLACE_DETAIL_PATH = "/v3/place/detail"

# 高德 POI 类别码:v0.2 只用这两类
ATTRACTION_TYPES = "110000"  # 风景名胜
RESTAURANT_TYPES = "050000"  # 餐饮服务

REQUEST_TIMEOUT_SECONDS = 10.0

#: 高德成功 infocode(10000 = OK)
SUCCESS_INFOCODE = "10000"

#: 限流 / 抖动重试:最多重试 2 次,退避 0.4s -> 1.0s
RETRY_DELAYS: tuple[float, ...] = (0.4, 1.0)

# 占位 / 空 Key 一律视为"未配置",绝不带着假 Key 发请求
PLACEHOLDER_API_KEYS = {"", "change_me"}

CONFIG_ERROR_MESSAGE = "外部数据服务未配置"
UNAVAILABLE_MESSAGE = "外部数据服务暂时不可用"
NOT_FOUND_MESSAGE = "未找到对应的地点信息"


class AmapError(RuntimeError):
    """高德调用失败(面向前端的可控异常)。"""

    #: 是否值得重试,供上层决定要不要提示用户稍后再试
    retryable = True


class AmapConfigError(AmapError):
    """AMAP_API_KEY 缺失或仍是占位符。"""

    retryable = False


class AmapNotFoundError(AmapError):
    """高德返回了成功状态但没有该 POI。"""

    retryable = False


def _is_api_key_configured(value: Optional[str]) -> bool:
    """Key 非空且不是 change_me 占位符才算配置好。"""
    return bool(value) and value.strip().lower() not in PLACEHOLDER_API_KEYS


def _is_success_payload(payload: Any) -> bool:
    """status == "1" 且 infocode 为 10000(缺失 infocode 时只看 status)。"""
    if not isinstance(payload, dict):
        return False
    if str(payload.get("status")) != "1":
        return False
    infocode = payload.get("infocode")
    if infocode is None:
        return True
    return str(infocode) == SUCCESS_INFOCODE


async def _send_request(path: str, params: dict[str, Any]) -> Any:
    """单次 HTTP 调用(POST 之外的部分都交给调用方处理)。"""
    api_key = get_settings().amap_api_key
    query: dict[str, Any] = {"key": api_key, "output": "JSON"}
    query.update({k: v for k, v in params.items() if v is not None})

    async with httpx.AsyncClient(
        base_url=AMAP_BASE_URL, timeout=REQUEST_TIMEOUT_SECONDS
    ) as client:
        response = await client.get(path, params=query)
        response.raise_for_status()
        return response.json()


async def request_amap(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """统一的高德请求:补 Key、发请求、校验 HTTP 与高德 status,失败带退避重试。

    限流时高德返回 status=0(而不是 HTTP 错误),所以这里按 payload 判断成功与否,
    最多尝试 1 + len(RETRY_DELAYS) 次;用尽后抛 AmapError,日志里也不打印完整 URL / Key。
    """
    if not _is_api_key_configured(get_settings().amap_api_key):
        raise AmapConfigError(CONFIG_ERROR_MESSAGE)

    last_reason = "unknown"
    for attempt in range(len(RETRY_DELAYS) + 1):
        payload: Any = None
        try:
            payload = await _send_request(path, params)
        except httpx.HTTPError as exc:
            last_reason = type(exc).__name__
        except ValueError:
            last_reason = "non-json"

        if _is_success_payload(payload):
            return payload

        if isinstance(payload, dict):
            last_reason = f"status={payload.get('status')} infocode={payload.get('infocode')}"
        if attempt < len(RETRY_DELAYS):
            logger.warning("amap retry %s for %s (%s)", attempt + 1, path, last_reason)
            await asyncio.sleep(RETRY_DELAYS[attempt])

    logger.warning("amap request failed after retries: %s (%s)", path, last_reason)
    raise AmapError(UNAVAILABLE_MESSAGE)


async def search_pois(
    city_name: str,
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """POI 关键字 / 类别搜索底层函数(景点默认、景点搜索、餐厅搜索都用它)。

    keyword 为空时**不带 keywords**,只按 category(types) 取该类别的默认排序结果。
    """
    params: dict[str, Any] = {
        "city": city_name,
        "citylimit": "true",
        "offset": page_size,
        "page": page,
        "extensions": "all",
    }
    cleaned_keyword = (keyword or "").strip()
    if cleaned_keyword:
        params["keywords"] = cleaned_keyword
    if category:
        params["types"] = category
    return await request_amap(PLACE_TEXT_PATH, params)


async def get_weather(adcode: str) -> dict[str, Any]:
    """按 adcode 取实时天气 + 今日预报,合并成一个原始结构。

    返回形如 {"lives": [...], "forecasts": [...]},具体字段归一化交给
    weather_service.normalize_weather(),这里只负责把两次请求都拿回来。
    """
    live_payload = await request_amap(WEATHER_PATH, {"city": adcode, "extensions": "base"})
    forecast_payload = await request_amap(WEATHER_PATH, {"city": adcode, "extensions": "all"})
    return {
        "lives": live_payload.get("lives") or [],
        "forecasts": forecast_payload.get("forecasts") or [],
    }


async def get_poi_detail(poi_id: str) -> dict[str, Any]:
    """取单个 POI 的详细信息;高德用 pois 数组返回,取第一条。"""
    payload = await request_amap(PLACE_DETAIL_PATH, {"id": poi_id, "extensions": "all"})
    pois = payload.get("pois") or []
    if not pois:
        raise AmapNotFoundError(NOT_FOUND_MESSAGE)
    return pois[0]
