"""统一 API Router:所有版本化接口都挂在 /api/v1 下。

v0.2 在这里 include city / weather / attractions / food,
v0.3 在这里 include conversations / chat(chat 与 conversations 共用 /conversations 前缀),
任务书《长期画像与跨会话记忆》在这里加 memory(授权、画像、来源管理),
任务书《RAG》在这里加 rag(状态 / 检索 / 引用)。

注意:``/rag/admin/*`` 刻意没有挂载 —— 当前用户模型没有管理员角色,
把"登录=管理员"当权限会直接越权。资料导入走服务器 CLI。
"""

from fastapi import APIRouter

from app.api.routes import (
    attractions,
    auth,
    chat,
    city,
    conversations,
    food,
    memory,
    preferences,
    rag,
    weather,
)

API_PREFIX = "/api/v1"


def build_api_router() -> APIRouter:
    """创建带统一前缀的 APIRouter,并挂载各版本的全部路由。"""
    router = APIRouter(prefix=API_PREFIX)
    router.include_router(auth.router)
    router.include_router(preferences.router)
    router.include_router(city.router)
    router.include_router(weather.router)
    router.include_router(attractions.router)
    router.include_router(food.router)
    router.include_router(conversations.router)
    router.include_router(chat.router)
    router.include_router(memory.router)
    router.include_router(rag.router)
    return router
