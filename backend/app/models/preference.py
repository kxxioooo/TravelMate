"""用户偏好 ORM 模型:每个用户只保存一份当前偏好。

attraction_preferences / food_preferences 用 JSON 列存字符串数组,
budget / travel_pace 是单选字符串。
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
    )
    attraction_preferences: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    food_preferences: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    budget: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    travel_pace: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    user: Mapped["User"] = relationship(back_populates="preference")

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<UserPreference user_id={self.user_id}>"
