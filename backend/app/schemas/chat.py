"""Chat 相关 Pydantic Schema(§23)。

契约:
- ChatMessageResponse : id / role / content / created_at,role ∈ {"user", "assistant"}
- ChatSendRequest     : content
- AgentActivityResponse: type / status / text(status ∈ {"success", "error"})
- ChatSendResponse    : user_message / assistant_message / activities
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChatRole = Literal["user", "assistant"]
ActivityStatus = Literal["success", "error"]


class ChatMessageResponse(BaseModel):
    """持久化在 messages 表里的最终消息(user / assistant)。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: ChatRole
    content: str
    created_at: datetime


class ChatSendRequest(BaseModel):
    """发送一条用户消息;空白内容由路由层再挡一次(422)。"""

    content: str = Field(..., min_length=1, max_length=4000)


class AgentActivityResponse(BaseModel):
    """Agent Activity:只描述真实执行过的工具,不含任何思维链(§34 / §43.8)。"""

    type: str
    status: ActivityStatus
    text: str


class ChatSendResponse(BaseModel):
    """一次问答的完整结果:落库的两条消息 + 本次真实发生的工具活动。"""

    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    activities: list[AgentActivityResponse] = Field(default_factory=list)
