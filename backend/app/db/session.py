"""数据库 engine 与 Session 的创建,以及 FastAPI 依赖 get_db。

engine 是懒连接:导入本模块不会立刻连 MySQL。
"""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import build_database_url, get_settings


def create_engine_and_session() -> tuple[Engine, sessionmaker[Session]]:
    """按配置创建 engine 与 SessionLocal。

    pool_pre_ping 让 MySQL 8 小时空闲断连后能自动重连,开发时少踩坑。
    """
    settings = get_settings()
    engine = create_engine(
        build_database_url(settings),
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
        future=True,
    )
    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    return engine, session_local


engine, SessionLocal = create_engine_and_session()


def get_db() -> Iterator[Session]:
    """FastAPI 依赖:每个请求一个 Session,结束时必定关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
