"""Conversation ORM 模型:一个用户拥有 N 个彼此隔离的 AI 会话(§11)。

关系:User 1:N Conversation,v0.3 起 Conversation 1:N ConversationCity / 1:N Message。

INDEX(user_id, updated_at) 是这张表的业务核心:
"我的会话列表"永远按 (当前用户, 最近活跃) 取,既不会扫到别人的会话,
AI Drawer 里的排序也永远稳定(排序键相同再用 id 兜底)。
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation_city import ConversationCity
    from app.models.user import User

#: 未产生第一条用户消息前的默认标题(§11)
DEFAULT_CONVERSATION_TITLE = "新对话"


def _utcnow() -> datetime:
    """统一的"不带时区的 UTC 现在"(MySQL DATETIME 不存 tzinfo)。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_updated", "user_id", "updated_at"),
    )

    # BigInteger 在 MySQL 上是 BIGINT;SQLite 需要 INTEGER 才能自增,故加 variant。
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id"),
        # 索引已单独声明,这里不再重复 index=True。
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, default=DEFAULT_CONVERSATION_TITLE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    user: Mapped["User"] = relationship()
    # 会话城市随会话一起删除;整组替换时由服务层显式 delete + insert(§17.4)。
    cities: Mapped[list["ConversationCity"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationCity.id",
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Conversation id={self.id} user_id={self.user_id} title={self.title!r}>"
