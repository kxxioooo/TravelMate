"""统一 API Router:所有版本化接口都挂在 /api/v1 下。

v0.2 在这里 include city / weather / attractions / food,
v0.3 在这里 include conversations / chat(chat 与 conversations 共用 /conversations 前缀)。
"""

from fastapi import APIRouter

from app.api.routes import (
    attractions,
    auth,
    chat,
    city,
    conversations,
    food,
    preferences,
    weather,
)

API_PREFIX = "/api/v1"


def build_api_router() -> APIRouter:
    """创建带统一前缀的 APIRouter,并挂载 v0.1 + v0.2 + v0.3 的全部路由。"""
    router = APIRouter(prefix=API_PREFIX)
    router.include_router(auth.router)
    router.include_router(preferences.router)
    router.include_router(city.router)
    router.include_router(weather.router)
    router.include_router(attractions.router)
    router.include_router(food.router)
    router.include_router(conversations.router)
    router.include_router(chat.router)
    return router
