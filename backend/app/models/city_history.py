"""城市浏览历史 ORM 模型。

v0.2 关系:User 1:N CityViewHistory。

UNIQUE(user_id, adcode) 是这张表的业务核心:
同一用户再次打开同一座城市时只更新 viewed_at,不新增重复记录,
这样顶部搜索框的 Recent Searches 永远不会出现两遍"成都"。
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


def _utcnow() -> datetime:
    """统一的"不带时区的 UTC 现在"(MySQL DATETIME 不存 tzinfo)。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CityViewHistory(Base):
    __tablename__ = "city_view_history"
    __table_args__ = (
        # 最近浏览列表按 user + viewed_at 倒序取,唯一键保证同城不重复。
        Index("ix_city_view_history_user_viewed", "user_id", "viewed_at"),
        Index("uq_city_view_history_user_adcode", "user_id", "adcode", unique=True),
    )

    # BigInteger 在 MySQL 上是 BIGINT;SQLite 需要 INTEGER 才能自增,故加 variant。
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id"),
        # 索引 / 唯一键已单独声明,这里不再重复 index=True。
        nullable=False,
    )
    city_name: Mapped[str] = mapped_column(String(100), nullable=False)
    province: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    adcode: Mapped[str] = mapped_column(String(20), nullable=False)
    viewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<CityViewHistory user_id={self.user_id} adcode={self.adcode!r}>"
