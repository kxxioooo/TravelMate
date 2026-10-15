"""ConversationCity ORM 模型:会话绑定的 0~N 个城市(§12)。

这张表决定 Agent 的"实时城市上下文"(§29.2 / §40):
天气 / 景点 / 美食工具只能查询这里存在的城市,模型无法凭空加入城市。

UNIQUE(conversation_id, adcode) 保证同一个会话里不会出现两遍"成都"。
"""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class ConversationCity(Base):
    __tablename__ = "conversation_cities"
    __table_args__ = (
        Index("uq_conversation_cities_conversation_adcode", "conversation_id", "adcode", unique=True),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    conversation_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("conversations.id"),
        nullable=False,
    )
    city_name: Mapped[str] = mapped_column(String(100), nullable=False)
    adcode: Mapped[str] = mapped_column(String(20), nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="cities")

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<ConversationCity conversation_id={self.conversation_id} adcode={self.adcode!r}>"
