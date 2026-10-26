"""翻译缓存服务(契约 §9 / §6.3):按原文哈希命中的多语言缓存。

三条硬规则:
1. `source_hash` = 原文 SHA-256 -> 同一 POI 连续查看不会重复调模型,原文变了自动失效;
2. 缓存**只**保存公开的 POI / 菜品 / 地址译文,绝不写入用户聊天内容;
3. 缓存读写失败只能降级(返回 None / 静默跳过),绝不能让整页 500。

数据库会话由调用方注入(`db` 可能是 None:例如纯函数测试或没有请求上下文时,
此时直接当作"没有缓存",不影响翻译本身)。
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.entity_translation import EntityTranslation, TRANSLATION_VERSION

logger = logging.getLogger(__name__)

#: 空原文的哈希(None 与空串在缓存层等价于"没有可缓存内容")
EMPTY_SOURCE_HASH = ""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clean_str(value: Any) -> Optional[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def make_source_hash(source_text: Any) -> str:
    """原文 -> SHA-256(hex,64 位);非字符串 / 空串返回空串。

    用哈希而不是原文做键,好处是:原文一变键就变 -> 旧译文自然失效,不用删数据。
    """
    text = _clean_str(source_text)
    if not text:
        return EMPTY_SOURCE_HASH
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_cached_translation(
    db: Optional[Session],
    provider: str,
    entity_key: str,
    field_name: str,
    target_locale: str,
    source_hash: str,
    translation_version: str = TRANSLATION_VERSION,
) -> Optional[EntityTranslation]:
    """按唯一键取一条缓存;未命中 / 参数不全 / 数据库异常都返回 None。"""
    if db is None:
        return None
    if not all(
        _clean_str(value)
        for value in (provider, entity_key, field_name, target_locale, source_hash, translation_version)
    ):
        return None

    try:
        return db.scalar(
            select(EntityTranslation).where(
                EntityTranslation.provider == provider,
                EntityTranslation.entity_key == entity_key,
                EntityTranslation.field_name == field_name,
                EntityTranslation.target_locale == target_locale,
                EntityTranslation.source_hash == source_hash,
                EntityTranslation.translation_version == translation_version,
            )
        )
    except SQLAlchemyError:
        # 缓存不可用绝不能影响业务:记一条 warning 就当作未命中
        logger.warning("translation cache read failed")
        return None


def save_translation(
    db: Optional[Session],
    provider: str,
    entity_key: str,
    field_name: str,
    target_locale: str,
    translation_text: str,
    translation_source: str = "model",
    translation_version: str = TRANSLATION_VERSION,
    source_hash: Optional[str] = None,
    source_text: Optional[str] = None,
) -> Optional[EntityTranslation]:
    """写入一条译文;同一唯一键已存在时更新文本,不产生重复行。

    `source_hash` 与 `source_text` 二选一:给了 source_text 就自己算哈希。
    失败(包括唯一键并发冲突)只记 warning,返回 None —— 调用方照常返回译文。
    """
    if db is None:
        return None

    text = _clean_str(translation_text)
    resolved_hash = _clean_str(source_hash) or make_source_hash(source_text)
    if not text or not resolved_hash:
        return None
    if not all(_clean_str(value) for value in (provider, entity_key, field_name, target_locale)):
        return None

    existing = get_cached_translation(
        db, provider, entity_key, field_name, target_locale, resolved_hash, translation_version
    )
    try:
        if existing is not None:
            if existing.translation_text != text:
                existing.translation_text = text
                existing.translation_source = translation_source or "model"
                existing.updated_at = _utcnow()
                db.commit()
            return existing

        record = EntityTranslation(
            provider=provider,
            entity_key=entity_key,
            field_name=field_name,
            target_locale=target_locale,
            source_hash=resolved_hash,
            translation_text=text,
            translation_source=translation_source or "model",
            translation_version=translation_version,
        )
        db.add(record)
        db.commit()
        return record
    except IntegrityError:
        # 并发写同一条:回滚后以已有记录为准(绝不因此让请求失败)
        db.rollback()
        return get_cached_translation(
            db, provider, entity_key, field_name, target_locale, resolved_hash, translation_version
        )
    except SQLAlchemyError:
        logger.warning("translation cache write failed")
        db.rollback()
        return None
