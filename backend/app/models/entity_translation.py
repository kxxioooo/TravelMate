"""翻译缓存表 ORM 模型(契约 §9 / §6.3)。

只缓存**公开**的 POI / 菜品 / 地址译文,绝不写入用户聊天内容。

唯一键 `(provider, entity_key, field_name, target_locale, source_hash, translation_version)`:
- `source_hash` 是原文的 SHA-256 -> 中文原文一变,缓存自然失效(不需要手工清);
- `entity_key` 用高德 poi_id(或菜品 canonical key)-> 译文不会跨实体错误复用;
- `translation_version` 允许将来整体提升译文质量等级而不删数据。
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: provider 取值:高德 POI / 人工词典 / DeepSeek 模型
PROVIDER_AMAP = "amap"
PROVIDER_CURATED = "curated"
PROVIDER_DEEPSEEK = "deepseek"

TRANSLATION_VERSION = "1"


def _utcnow() -> datetime:
    """统一的"不带时区的 UTC 现在"(MySQL DATETIME 不存 tzinfo)。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EntityTranslation(Base):
    __tablename__ = "entity_translations"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "entity_key",
            "field_name",
            "target_locale",
            "source_hash",
            "translation_version",
            name="uq_entity_translation_lookup",
        ),
    )

    # BigInteger 在 MySQL 上是 BIGINT;SQLite 需要 INTEGER 才能自增,故加 variant。
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_key: Mapped[str] = mapped_column(String(128), nullable=False)
    field_name: Mapped[str] = mapped_column(String(32), nullable=False)
    target_locale: Mapped[str] = mapped_column(String(16), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    translation_text: Mapped[str] = mapped_column(Text, nullable=False)
    translation_source: Mapped[str] = mapped_column(String(32), nullable=False, default="model")
    translation_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TRANSLATION_VERSION
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return (
            f"<EntityTranslation {self.provider}:{self.entity_key}:{self.field_name}"
            f"->{self.target_locale}>"
        )
