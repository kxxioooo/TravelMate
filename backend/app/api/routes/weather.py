"""天气路由:GET /api/v1/weather?adcode=510100,必须登录。

外部高德失败时返回 502 + 中文人话,绝不把 Key / 完整 URL / 原始异常抛给前端。

v0.3.1(契约 §3):解析 locale 后原样返回中文事实字段,并**追加**
`weather.weather_code` 与 `clothing_advice_codes` 两个语言无关的枚举,
让英文界面用 `t('weather.' + code)` 显示,不会残留中文。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import get_current_user
from app.core.locale import resolve_request_locale
from app.models.user import User
from app.schemas.weather import WeatherResponse
from app.services import weather_service
from app.services.amap_client import AmapError

router = APIRouter(tags=["weather"])

WEATHER_UNAVAILABLE_DETAIL = "天气服务暂时不可用"


@router.get("/weather", response_model=WeatherResponse)
async def get_weather_endpoint(
    request: Request,
    adcode: str = Query(..., min_length=1, max_length=20, description="城市 adcode,如 510100"),
    current_user: User = Depends(get_current_user),
) -> WeatherResponse:
    """按 adcode 取实时天气 + 预报,并给出规则化穿衣建议(+ codes)。"""
    locale = resolve_request_locale(request)
    try:
        return await weather_service.get_city_weather(adcode, locale=locale)
    except AmapError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=WEATHER_UNAVAILABLE_DETAIL
        ) from exc
