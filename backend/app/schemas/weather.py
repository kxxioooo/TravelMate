"""天气相关 Pydantic Schema。

高德原始字段(温度 / 湿度都是字符串,min/max 来自 forecasts.casts)在
weather_service.normalize_weather() 里归一化成这里的稳定结构。
没有的字段一律 None,由前端显示"暂无信息",后端不填假数据。

v0.3.1(契约 §3)只做**追加**:
- `weather.weather_code`:语言无关的天气枚举(未知 -> `UNKNOWN`);
- `clothing_advice_codes`:语言无关的穿衣建议枚举数组(旧 `clothing_advice` 原样保留)。
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.localization import exclude_when_none


class WeatherInfo(BaseModel):
    """前端顶部城市栏需要的天气字段。"""

    weather: Optional[str] = None
    temperature: Optional[float] = None
    min_temperature: Optional[float] = None
    max_temperature: Optional[float] = None
    humidity: Optional[float] = None
    wind_direction: Optional[str] = None
    wind_power: Optional[str] = None
    # --- v0.3.1:语言无关的天气 code(契约 §3),未知 -> UNKNOWN ---
    weather_code: Optional[str] = Field(default=None, exclude_if=exclude_when_none)


class WeatherResponse(BaseModel):
    """GET /weather 响应:天气 + 后端规则生成的穿衣建议(不调用 DeepSeek)。"""

    weather: WeatherInfo
    clothing_advice: str
    # --- v0.3.1:语言无关的穿衣建议 codes(契约 §3);旧字段语义完全不变 ---
    clothing_advice_codes: list[str] = Field(default_factory=list)
