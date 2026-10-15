"""Chat 路由(§36):

    GET  /api/v1/conversations/{id}/messages   该会话的全部最终消息
    POST /api/v1/conversations/{id}/messages   发一条用户消息,跑一次 Agent,拿回问答结果

Route 不自己写 Agent 逻辑:全部委托 agent_service.handle_user_message()。
两个接口都要求登录,并且先做会话所有权校验(不属于当前用户 -> 404)。
v0.3 使用普通 HTTP Request/Response,不做流式输出(§22)。
"""

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.conversations import _require_owned_conversation
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import ChatMessageResponse, ChatSendRequest, ChatSendResponse
from app.services import agent_service, conversation_service
from app.services.deepseek_client import DeepSeekError

router = APIRouter(prefix="/conversations", tags=["chat"])

EMPTY_CONTENT_DETAIL = "消息内容不能为空"
AGENT_UNAVAILABLE_DETAIL = "AI 助手暂时不可用,请稍后重试"


@router.get("/{conversation_id}/messages", response_model=list[ChatMessageResponse])
def get_messages_endpoint(
    conversation_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatMessageResponse]:
    """读取会话消息(时间正序):先验证会话属于当前用户,再查 messages。"""
    conversation = _require_owned_conversation(db, current_user.id, conversation_id)
    messages = conversation_service.get_conversation_messages(db, conversation.id)
    return [ChatMessageResponse.model_validate(message) for message in messages]


@router.post("/{conversation_id}/messages", response_model=ChatSendResponse)
async def send_message_endpoint(
    payload: ChatSendRequest,
    conversation_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSendResponse:
    """发送一条用户消息:Agent 可能调用多个工具,最后返回最终回答 + Activity。

    整体失败时:用户消息保留,绝不返回虚假的 assistant 成功消息,只给可重试错误。
    """
    conversation = _require_owned_conversation(db, current_user.id, conversation_id)

    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=EMPTY_CONTENT_DETAIL
        )

    try:
        result = await agent_service.handle_user_message(db, current_user, conversation, content)
    except (DeepSeekError, agent_service.AgentError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=AGENT_UNAVAILABLE_DETAIL
        ) from exc

    return ChatSendResponse(
        user_message=ChatMessageResponse.model_validate(result["user_message"]),
        assistant_message=ChatMessageResponse.model_validate(result["assistant_message"]),
        activities=result["activities"],
    )
