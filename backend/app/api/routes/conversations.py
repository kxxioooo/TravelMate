"""Conversation 路由(§16):

    GET    /api/v1/conversations                 我的会话列表(updated_at DESC)
    POST   /api/v1/conversations                 新建会话(0~N 个城市)
    GET    /api/v1/conversations/{id}             会话详情
    PUT    /api/v1/conversations/{id}/cities      整组替换会话城市

四个接口全部要求登录;每个查询都带当前 user_id,不属于当前用户一律 404(§43.1)。
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.conversation import (
    ConversationCityResponse,
    ConversationCreateRequest,
    ConversationDetail,
    ConversationSummary,
    ConversationUpdateCitiesRequest,
)
from app.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])

NOT_FOUND_DETAIL = "未找到该会话"


def _conversation_payload(conversation: Conversation) -> dict[str, Any]:
    """ORM -> 响应字段:cities 按 id 升序,保证前端城市 Chip 顺序稳定。"""
    cities = [
        ConversationCityResponse(city_name=city.city_name, adcode=city.adcode)
        for city in sorted(conversation.cities, key=lambda item: item.id or 0)
    ]
    return {
        "id": conversation.id,
        "title": conversation.title,
        "cities": cities,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
    }


def _to_summary(conversation: Conversation) -> ConversationSummary:
    return ConversationSummary(**_conversation_payload(conversation))


def _to_detail(conversation: Conversation) -> ConversationDetail:
    return ConversationDetail(**_conversation_payload(conversation))


def _require_owned_conversation(
    db: Session, user_id: int, conversation_id: int
) -> Conversation:
    """会话隔离的唯一入口:查不到 / 不是自己的,统一 404,减少资源枚举。"""
    conversation = conversation_service.get_owned_conversation(db, user_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_DETAIL)
    return conversation


@router.get("", response_model=list[ConversationSummary])
def list_conversations_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationSummary]:
    """只返回当前登录用户的会话,按最近活跃倒序。"""
    return [
        _to_summary(conversation)
        for conversation in conversation_service.list_user_conversations(db, current_user.id)
    ]


@router.post("", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
def create_conversation_endpoint(
    payload: Optional[ConversationCreateRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    """新建会话:cities 允许为空(带 `{"cities": []}` 或干脆不带 body 都可以),
    标题先固定为"新对话",第一条消息后自动更新。"""
    cities = payload.cities if payload is not None else []
    conversation = conversation_service.create_conversation(db, current_user.id, cities)
    return _to_detail(conversation)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation_endpoint(
    conversation_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    """会话详情:不属于当前用户 -> 404。"""
    conversation = _require_owned_conversation(db, current_user.id, conversation_id)
    return _to_detail(conversation)


@router.put("/{conversation_id}/cities", response_model=ConversationDetail)
def update_conversation_cities_endpoint(
    conversation_id: int = Path(..., ge=1),
    payload: Optional[ConversationUpdateCitiesRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    """整组替换会话城市:先删原城市再写入新的 0~N 个(按 adcode 去重)。

    不带 body(或 `{"cities": []}`)表示清空该会话的城市。
    """
    conversation = _require_owned_conversation(db, current_user.id, conversation_id)
    cities = payload.cities if payload is not None else []
    conversation = conversation_service.replace_conversation_cities(db, conversation, cities)
    return _to_detail(conversation)
