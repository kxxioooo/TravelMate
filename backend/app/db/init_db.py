"""开发阶段建表入口。

v0.1 只做 Base.metadata.create_all(),等表结构开始演进再引入 Alembic。

用法:
    python -m app.db.init_db
"""

from app.db.base import Base
from app.db.session import engine
from app.models import (  # noqa: F401  导入即注册到 Base.metadata
    city_history,
    conversation,
    conversation_city,
    entity_translation,
    message,
    preference,
    user,
)


def init_db() -> None:
    """按 ORM Model 创建全部业务表(已存在的表不会被改动)。"""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print(f"created tables: {', '.join(sorted(Base.metadata.tables))}")
