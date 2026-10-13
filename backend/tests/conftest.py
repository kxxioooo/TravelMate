"""pytest 公共夹具。

测试跑在内存 SQLite 上,完全不碰本机 MySQL:
create_all 只针对测试 engine,生产 SessionLocal 被依赖覆盖替换掉。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app


@pytest.fixture
def override_test_db():
    """提供替换生产 get_db 的测试依赖;夹具结束时销毁 engine。"""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )

    def _override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    yield _override_get_db
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def create_test_app(override_test_db):
    """创建不建生产表的测试 FastAPI,并装好依赖覆盖。"""
    app = create_app(init_database=False)
    app.dependency_overrides[get_db] = override_test_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client_fixture(create_test_app):
    """带 Cookie jar 的 TestClient,因此注册 / 登录后的登录态会自然保持。"""
    with TestClient(create_test_app) as client:
        yield client


@pytest.fixture
def user_payload_fixture():
    """统一的测试用户数据。"""
    return {
        "username": "traveler",
        "email": "traveler@example.com",
        "password": "travel1234",
    }
