"""Conversation 服务层:会话、会话城市、消息的全部数据库操作(§17)。

三条不可动摇的规则:
1. 任何会话查询都必须同时带 `id` 和 `user_id`(§17.3 / §43.1);
2. 会话城市是"整组替换"语义,先按 adcode 去重再写库(§17.4 / §16.4);
3. `messages` 表只写最终 user / assistant 消息,工具临时消息永不落库(§13 / §43.9)。
"""

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.conversation import DEFAULT_CONVERSATION_TITLE, Conversation
from app.models.conversation_city import ConversationCity
from app.models.message import Message

MESSAGE_ROLE_USER = "user"
MESSAGE_ROLE_ASSISTANT = "assistant"
#: 数据库只长期保存这两种最终消息
ALLOWED_MESSAGE_ROLES = (MESSAGE_ROLE_USER, MESSAGE_ROLE_ASSISTANT)

#: 标题截断长度(§17.7:截取前 20~30 个字符)
TITLE_MAX_LENGTH = 20


def _utcnow() -> datetime:
    """统一的"不带时区的 UTC 现在"(MySQL DATETIME 不存 tzinfo)。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clean_str(value: Any) -> Optional[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _city_pair(city: Any) -> Optional[tuple[str, str]]:
    """把一个城市入参(Pydantic / dict / ORM / 二元组)归一化成 (city_name, adcode)。"""
    if isinstance(city, Mapping):
        city_name, adcode = city.get("city_name"), city.get("adcode")
    elif isinstance(city, (tuple, list)) and len(city) == 2:
        city_name, adcode = city[0], city[1]
    else:
        city_name = getattr(city, "city_name", None)
        adcode = getattr(city, "adcode", None)

    name = _clean_str(city_name)
    code = _clean_str(adcode)
    if not name or not code:
        return None
    return name, code


def _dedupe_city_pairs(cities: Optional[Iterable[Any]]) -> list[tuple[str, str]]:
    """按 adcode 去重(保留第一次出现的顺序),顺带丢掉缺字段的脏输入。"""
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for city in cities or []:
        pair = _city_pair(city)
        if pair is None:
            continue
        _, adcode = pair
        if adcode in seen:
            continue
        seen.add(adcode)
        pairs.append(pair)
    return pairs


def create_conversation(db: Session, user_id: int, cities: Optional[Iterable[Any]] = None) -> Conversation:
    """创建会话主记录 + 0~N 条城市关联(§17.1)。

    事务一致性:任何一个 city insert 失败都整体 rollback,绝不留半个会话。
    """
    conversation = Conversation(user_id=user_id, title=DEFAULT_CONVERSATION_TITLE)
    try:
        db.add(conversation)
        db.flush()  # 先拿到 conversation.id,城市行才有外键可用
        for city_name, adcode in _dedupe_city_pairs(cities):
            db.add(
                ConversationCity(
                    conversation_id=conversation.id, city_name=city_name, adcode=adcode
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(conversation)
    return conversation


def list_user_conversations(db: Session, user_id: int) -> list[Conversation]:
    """只返回当前登录用户的会话,按最近活跃倒序(§16.1 / §17.2)。"""
    statement = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .options(selectinload(Conversation.cities))
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
    )
    return list(db.scalars(statement))


def get_owned_conversation(db: Session, user_id: int, conversation_id: Optional[int]) -> Optional[Conversation]:
    """按 (id, user_id) 查会话;查不到或不属于该用户都返回 None(§17.3)。

    这是会话隔离的第一层保障:查询条件里永远同时包含 id 与 user_id,
    路由层把 None 统一转成 404,避免通过 403 枚举别人的会话 id。
    """
    if conversation_id is None:
        return None
    statement = (
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .options(selectinload(Conversation.cities))
    )
    return db.scalar(statement)


def replace_conversation_cities(
    db: Session, conversation: Conversation, cities: Optional[Iterable[Any]] = None
) -> Conversation:
    """整组替换该会话的城市(§16.4 / §17.4)。

    先删除旧城市并 flush,再插入新城市:这样即使新旧集合含同一个 adcode,
    也不会撞上 UNIQUE(conversation_id, adcode)。
    """
    pairs = _dedupe_city_pairs(cities)
    try:
        db.execute(
            delete(ConversationCity).where(ConversationCity.conversation_id == conversation.id)
        )
        db.flush()
        for city_name, adcode in pairs:
            db.add(
                ConversationCity(
                    conversation_id=conversation.id, city_name=city_name, adcode=adcode
                )
            )
        # 改了会话城市就算一次活跃,列表排序随之上升
        conversation.updated_at = _utcnow()
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.expire(conversation, ["cities"])
    db.refresh(conversation)
    return conversation


def get_conversation_messages(
    db: Session, conversation_id: int, limit: Optional[int] = None
) -> list[Message]:
    """取某个会话的消息,按时间正序返回(§17.5)。

    数据库保存全部消息;limit 只用于给 Agent 控制单次上下文长度(默认最近 30 条),
    因此实现是"按 id 倒序取 limit 条,再翻回正序"。
    """
    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
    )
    if limit is not None and limit > 0:
        statement = statement.limit(int(limit))
    messages = list(db.scalars(statement))
    messages.reverse()
    return messages


def append_message(db: Session, conversation_id: int, role: str, content: str) -> Message:
    """统一创建一条最终消息并立即提交(§17.6)。

    立即提交是有意为之:即使随后 Agent 调用整体失败,用户消息也已经留下,
    而 assistant 绝不会写入虚假的成功消息(§35)。
    """
    if role not in ALLOWED_MESSAGE_ROLES:
        raise ValueError(f"不支持的消息角色: {role}")

    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content if isinstance(content, str) else str(content),
        created_at=_utcnow(),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def build_conversation_title(first_user_message: str) -> str:
    """用第一条用户消息生成确定性标题(§17.7):trim、去换行、截前 20 个字。

    刻意不调用 DeepSeek:标题不值得多花一次 API 请求。
    """
    text = _clean_str(first_user_message) or ""
    flattened = " ".join(text.split())
    if not flattened:
        return DEFAULT_CONVERSATION_TITLE
    return flattened[:TITLE_MAX_LENGTH]
