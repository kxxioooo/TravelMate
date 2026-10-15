"""天气服务:高德原始数据 -> 契约字段 + 穿衣建议。

穿衣建议是纯规则计算,不调用 DeepSeek(§27.3)。
缺字段一律 None,绝不填假数据。
"""

from typing import Any, Mapping, Optional

from app.schemas.weather import WeatherInfo, WeatherResponse
from app.services import amap_client

RAIN_KEYWORDS = ("雨",)

ADVICE_FREEZING = "厚外套"
ADVICE_COLD = "外套 / 毛衣"
ADVICE_MILD = "薄外套"
ADVICE_WARM = "短袖"
ADVICE_HOT = "轻薄透气衣物"
ADVICE_RAIN = "建议携带雨具"
ADVICE_UNKNOWN = "暂无信息"


def _clean_str(value: Any) -> Optional[str]:
    """高德缺失值可能是 None / "" / [],统一归一化成 None。"""
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _to_float(value: Any) -> Optional[float]:
    """高德数字字段是字符串(如 "22");转换失败(含 [])返回 None。"""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _first_mapping(value: Any) -> Mapping[str, Any]:
    """取数组里第一个 dict(高德的 lives / photos 等都是数组)。"""
    if isinstance(value, Mapping):
        return value
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], Mapping):
        return value[0]
    return {}


def _first_cast(value: Any) -> Mapping[str, Any]:
    """forecasts[0].casts[0]:今日预报(daytemp / nighttemp ...)。"""
    forecast = _first_mapping(value)
    return _first_mapping(forecast.get("casts"))


async def get_city_weather(adcode: str) -> WeatherResponse:
    """取天气 + 生成穿衣建议,返回前端稳定结构。"""
    raw = await amap_client.get_weather(adcode)
    weather = normalize_weather(raw)
    return WeatherResponse(weather=weather, clothing_advice=build_clothing_advice(weather))


def normalize_weather(raw: Any) -> WeatherInfo:
    """把高德原始响应(实时 + 预报)合并成契约字段。

    兼容两种入参:
    - {"lives": [...], "forecasts": [...]}:amap_client.get_weather() 的原始输出
    - 扁平 dict:已经合并好的字段(便于单测直接喂数据)
    """
    payload: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
    live = _first_mapping(payload.get("lives"))
    cast = _first_cast(payload.get("forecasts"))
    if not live and not cast:
        # 扁平结构:同一份 dict 既当实时又当预报
        live = payload
        cast = payload

    min_temperature = _to_float(cast.get("nighttemp_float"))
    if min_temperature is None:
        min_temperature = _to_float(cast.get("nighttemp"))
    max_temperature = _to_float(cast.get("daytemp_float"))
    if max_temperature is None:
        max_temperature = _to_float(cast.get("daytemp"))

    return WeatherInfo(
        weather=_clean_str(live.get("weather")) or _clean_str(cast.get("dayweather")),
        temperature=_to_float(live.get("temperature")),
        min_temperature=min_temperature,
        max_temperature=max_temperature,
        humidity=_to_float(live.get("humidity")),
        wind_direction=_clean_str(live.get("winddirection")) or _clean_str(live.get("wind_direction")),
        wind_power=_clean_str(live.get("windpower")) or _clean_str(live.get("wind_power")),
    )


def build_clothing_advice(weather: WeatherInfo) -> str:
    """按冻结的简单温度规则给穿衣建议,雨雪天气追加雨具提示。"""
    temperature = weather.temperature
    if temperature is None and weather.min_temperature is not None and weather.max_temperature is not None:
        temperature = (weather.min_temperature + weather.max_temperature) / 2

    parts: list[str] = []
    if temperature is not None:
        if temperature <= 5:
            parts.append(ADVICE_FREEZING)
        elif temperature <= 15:
            parts.append(ADVICE_COLD)
        elif temperature <= 23:
            parts.append(ADVICE_MILD)
        elif temperature <= 30:
            parts.append(ADVICE_WARM)
        else:
            parts.append(ADVICE_HOT)

    weather_text = weather.weather or ""
    if any(keyword in weather_text for keyword in RAIN_KEYWORDS):
        parts.append(ADVICE_RAIN)

    if not parts:
        return ADVICE_UNKNOWN
    return " / ".join(parts)
