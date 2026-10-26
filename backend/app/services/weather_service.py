"""天气服务:高德原始数据 -> 契约字段 + 穿衣建议 + 语言无关 codes。

穿衣建议是纯规则计算,不调用 DeepSeek(§27.3)。
缺字段一律 None,绝不填假数据。

v0.3.1(契约 §3):**判定逻辑一个字都不改**,只额外输出机器可读枚举:
- `weather.weather_code`:中文天气文本 -> 枚举(未知 -> `UNKNOWN`);
- `clothing_advice_codes`:与 `clothing_advice` 同一套温度/雨雪规则 -> 枚举数组。
前端用 `t('weather.' + code)` / `t('clothing.' + code)` 显示,英文模式不会再残留中文。
"""

from typing import Any, Mapping, Optional

from app.schemas.weather import WeatherInfo, WeatherResponse
from app.services import amap_client, entity_localization_service

RAIN_KEYWORDS = ("雨",)

ADVICE_FREEZING = "厚外套"
ADVICE_COLD = "外套 / 毛衣"
ADVICE_MILD = "薄外套"
ADVICE_WARM = "短袖"
ADVICE_HOT = "轻薄透气衣物"
ADVICE_RAIN = "建议携带雨具"
ADVICE_UNKNOWN = "暂无信息"

# --- v0.3.1 codes(契约 §3 枚举,前端 i18n key 一一对应) ---------------------
WEATHER_CODE_UNKNOWN = "UNKNOWN"

CLOTHING_HEAVY_COAT = "HEAVY_COAT"
CLOTHING_COAT_SWEATER = "COAT_SWEATER"
CLOTHING_LIGHT_JACKET = "LIGHT_JACKET"
CLOTHING_SHORT_SLEEVE = "SHORT_SLEEVE"
CLOTHING_LIGHT_BREATHABLE = "LIGHT_BREATHABLE"
CLOTHING_UNKNOWN = "UNKNOWN"
CLOTHING_UMBRELLA = "UMBRELLA"

#: 内置天气文本 -> code 映射(词典文件缺失时也能工作)
DEFAULT_WEATHER_CODES: dict[str, str] = {
    "晴": "SUNNY",
    "多云": "CLOUDY",
    "阴": "OVERCAST",
    "小雨": "LIGHT_RAIN",
    "中雨": "MODERATE_RAIN",
    "大雨": "HEAVY_RAIN",
    "暴雨": "HEAVY_RAIN",
    "雷阵雨": "THUNDERSTORM",
    "雷雨": "THUNDERSTORM",
    "雪": "SNOW",
    "小雪": "SNOW",
    "中雪": "SNOW",
    "大雪": "SNOW",
    "雨夹雪": "SLEET",
    "雾": "FOG",
    "霾": "HAZE",
    "大风": "WINDY",
    "风": "WINDY",
}

#: 精确匹配不到时的子串匹配顺序(先长词/更具体的词,避免"小雨"被"雨"抢先)
WEATHER_CODE_SUBSTRING_ORDER: tuple[tuple[str, str], ...] = (
    ("雷阵雨", "THUNDERSTORM"),
    ("雷雨", "THUNDERSTORM"),
    ("暴雨", "HEAVY_RAIN"),
    ("大雨", "HEAVY_RAIN"),
    ("中雨", "MODERATE_RAIN"),
    ("小雨", "LIGHT_RAIN"),
    ("阵雨", "LIGHT_RAIN"),
    ("雨夹雪", "SLEET"),
    ("雨", "LIGHT_RAIN"),
    ("大雪", "SNOW"),
    ("中雪", "SNOW"),
    ("小雪", "SNOW"),
    ("雪", "SNOW"),
    ("多云", "CLOUDY"),
    ("晴", "SUNNY"),
    ("阴", "OVERCAST"),
    ("雾", "FOG"),
    ("霾", "HAZE"),
    ("风", "WINDY"),
)


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


def map_weather_code(weather_text: Any) -> str:
    """中文天气文本 -> 契约 §3 的 weather_code 枚举;未知一律 `UNKNOWN`。

    优先用词典 `weather_codes`(人工审核),其次内置映射,最后按子串兜底。
    词典文件不存在时完全依赖内置映射,所以这里不会因为缺词典而失败。
    """
    text = _clean_str(weather_text)
    if not text:
        return WEATHER_CODE_UNKNOWN

    lexicon_codes = entity_localization_service.get_lexicon_section("weather_codes")
    for source_map in (lexicon_codes, DEFAULT_WEATHER_CODES):
        for key, code in source_map.items():
            if isinstance(key, str) and key.strip() and key.strip() == text and isinstance(code, str):
                return code

    for keyword, code in WEATHER_CODE_SUBSTRING_ORDER:
        if keyword in text:
            return code
    return WEATHER_CODE_UNKNOWN


async def get_city_weather(adcode: str, locale: str = "zh-CN") -> WeatherResponse:
    """取天气 + 生成穿衣建议(+ v0.3.1 codes),返回前端稳定结构。

    `locale` 目前不改变任何数值字段:天气文本是事实来源,多语言由前端按 code 渲染。
    """
    raw = await amap_client.get_weather(adcode)
    weather = normalize_weather(raw)
    return WeatherResponse(
        weather=weather,
        clothing_advice=build_clothing_advice(weather),
        clothing_advice_codes=build_clothing_advice_codes(weather),
    )


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

    weather_text = _clean_str(live.get("weather")) or _clean_str(cast.get("dayweather"))

    return WeatherInfo(
        weather=weather_text,
        temperature=_to_float(live.get("temperature")),
        min_temperature=min_temperature,
        max_temperature=max_temperature,
        humidity=_to_float(live.get("humidity")),
        wind_direction=_clean_str(live.get("winddirection")) or _clean_str(live.get("wind_direction")),
        wind_power=_clean_str(live.get("windpower")) or _clean_str(live.get("wind_power")),
        weather_code=map_weather_code(weather_text),
    )


def _effective_temperature(weather: WeatherInfo) -> Optional[float]:
    """实时温度;没有就用 (min + max) / 2(v0.3 的老规则,原样保留)。"""
    temperature = weather.temperature
    if temperature is None and weather.min_temperature is not None and weather.max_temperature is not None:
        temperature = (weather.min_temperature + weather.max_temperature) / 2
    return temperature


def _temperature_code(temperature: Optional[float]) -> Optional[str]:
    """温度 -> 穿衣 code;阈值与 build_clothing_advice 完全一致(契约 §3)。"""
    if temperature is None:
        return None
    if temperature <= 5:
        return CLOTHING_HEAVY_COAT
    if temperature <= 15:
        return CLOTHING_COAT_SWEATER
    if temperature <= 23:
        return CLOTHING_LIGHT_JACKET
    if temperature <= 30:
        return CLOTHING_SHORT_SLEEVE
    return CLOTHING_LIGHT_BREATHABLE


def has_rain(weather: WeatherInfo) -> bool:
    """天气文本是否含雨(v0.3 的 RAIN_KEYWORDS 判定,原样保留)。"""
    weather_text = weather.weather or ""
    return any(keyword in weather_text for keyword in RAIN_KEYWORDS)


def build_clothing_advice(weather: WeatherInfo) -> str:
    """按冻结的简单温度规则给穿衣建议,雨雪天气追加雨具提示。

    **v0.3.1 不改判定逻辑**,只让 codes 版本复用同一套阈值。
    """
    temperature = _effective_temperature(weather)

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

    if has_rain(weather):
        parts.append(ADVICE_RAIN)

    if not parts:
        return ADVICE_UNKNOWN
    return " / ".join(parts)


def build_clothing_advice_codes(weather: WeatherInfo) -> list[str]:
    """语言无关的穿衣建议 codes(契约 §3):温度档 + 雨具;未知 -> `UNKNOWN`。

    与 build_clothing_advice 同源同阈值,保证中英文界面显示的是同一个判断。
    """
    codes: list[str] = []
    temperature_code = _temperature_code(_effective_temperature(weather))
    codes.append(temperature_code or CLOTHING_UNKNOWN)
    if has_rain(weather):
        codes.append(CLOTHING_UMBRELLA)
    return codes
