"""Chat 相关 Pydantic Schema(§23)。

契约:
- ChatMessageResponse : id / role / content / created_at,role ∈ {"user", "assistant"}
- ChatSendRequest     : content(+ v0.3.1 可选的 locale)
- AgentActivityResponse: type / status / code / params / text
- ChatSendResponse    : user_message / assistant_message / activities

v0.3.1(契约 §4 / §8):
- `ChatSendRequest.locale` 只影响**本次新生成**的回答,历史消息 `content` 永远不改写;
- Activity 增加机器可读的 `code` + `params`,旧的 `text` 原样保留(向后兼容)。
"""

from datetime import datetime
from typing import Any, Literal, Optional

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
    """发送一条用户消息;空白内容由路由层再挡一次(422)。

    `locale` 是可选字段:传了就按它回答,不传就看 `Accept-Language`,
    再没有就是 zh-CN(契约 §1 的优先级)。它**不落库、不影响历史消息**。
    """

    content: str = Field(..., min_length=1, max_length=4000)
    locale: Optional[str] = Field(default=None, max_length=16)


class AgentActivityResponse(BaseModel):
    """Agent Activity:只描述真实执行过的工具,不含任何思维链(§34 / §43.8)。

    `code` + `params` 是 v0.3.1 前端本地化的唯一来源;`text` 仅为向后兼容保留。
    """

    type: str
    status: ActivityStatus
    code: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    text: str


class ChatCitationResponse(BaseModel):
    """一条引用来源(任务书《RAG》§9.5)。

    `id` 与回答正文里的 ``[n]`` 严格对应;`url` 只对联网来源有意义;
    `snippet` 是截断后的证据片段,便于前端卡片展示。
    """

    id: int
    source_type: str
    source_id: str
    title: str = ""
    url: Optional[str] = None
    snippet: Optional[str] = None
    published_at: Optional[datetime] = None
    retrieved_at: Optional[datetime] = None
    page_number: Optional[int] = None
    is_current: bool = False


class ChatSendResponse(BaseModel):
    """一次问答的完整结果:落库的两条消息 + 本次真实发生的工具活动。

    ``citations`` 是新增字段(有默认值,老客户端不受影响):
    只有真正检索到证据时才会非空,且编号一定能在本次请求里找到对应来源。
    """

    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    activities: list[AgentActivityResponse] = Field(default_factory=list)
    citations: list[ChatCitationResponse] = Field(default_factory=list)
