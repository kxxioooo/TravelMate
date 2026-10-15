"""Message ORM 模型:会话里长期保存的最终对话消息(§13)。

v0.3 只长期保存 user / assistant 两种最终消息:
Agent 内部的 assistant tool_call 消息与 tool 结果消息只在本次请求内传给 DeepSeek,
绝不写入这张表(§13 / §43.9)。

会话隔离由 messages.conversation_id 严格保证:Chat A 的消息永远不会出现在 Chat B。
"""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    """统一的"不带时区的 UTC 现在"(MySQL DATETIME 不存 tzinfo)。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        # 取"某会话最近 N 条"走这个索引,永远按 id 倒序取再翻正。
        Index("ix_messages_conversation_id", "conversation_id", "id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    conversation_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("conversations.id"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Message conversation_id={self.conversation_id} role={self.role!r}>"
