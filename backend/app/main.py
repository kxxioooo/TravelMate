"""FastAPI 应用入口。

以工厂模式暴露应用,导入本模块不会连接数据库:

    uvicorn app.main:create_app --factory --reload --port 8000

首次运行前先建表:

    python -m app.db.init_db
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import build_api_router
from app.core.config import get_settings
from app.db.init_db import init_db


def create_app(init_database: bool = True) -> FastAPI:
    """组装 FastAPI 应用:CORS + 统一路由 + 统一异常处理(+ 可选建表)。

    参数 init_database 供测试关闭建表,生产 / 开发保持默认 True。
    """
    settings = get_settings()
    app = FastAPI(
        title="TravelMate AI API",
        version="0.1.0",
        description="v0.1:账户系统、用户偏好、城市索引基础层。",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_routers(app)

    # 数据库异常统一降级为 500 + 人话,绝不把 SQLAlchemyError / traceback 抛给前端
    app.add_exception_handler(
        SQLAlchemyError,
        lambda request, exc: JSONResponse(
            status_code=500, content={"detail": "服务器暂时不可用"}
        ),
    )

    if init_database:
        init_db()

    return app


def register_routers(app: FastAPI) -> None:
    """注册统一 API Router 与系统级 /health。"""
    app.include_router(build_api_router())
    app.add_api_route("/health", health_check, methods=["GET"], tags=["system"], summary="健康检查")


def health_check() -> dict[str, str]:
    """进程存活探针,不查数据库。"""
    return {"status": "ok"}
