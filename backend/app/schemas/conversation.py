"""Conversation 相关 Pydantic Schema(§14)。

前端契约(§14 / §15):
- ConversationSummary = id / title / cities / created_at / updated_at
- ConversationDetail  = 与 Summary 同字段(需要时可扩展 messages,本次不返回)
- 创建 / 修改城市都允许 {"cities": []},即 0 个城市也能开会话。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCityInput(BaseModel):
    """新建会话 / 修改会话城市时的单个城市。"""

    city_name: str = Field(..., min_length=1, max_length=100)
    adcode: str = Field(..., min_length=1, max_length=20)


class ConversationCityResponse(BaseModel):
    """返回给前端的会话城市(name 给 UI 显示,adcode 给工具查真实数据)。"""

    model_config = ConfigDict(from_attributes=True)

    city_name: str
    adcode: str


class ConversationCreateRequest(BaseModel):
    """POST /conversations 的入参;cities 允许为空数组。"""

    cities: list[ConversationCityInput] = Field(default_factory=list)


class ConversationUpdateCitiesRequest(BaseModel):
    """PUT /conversations/{id}/cities 的入参:整组替换,允许替换成空数组。"""

    cities: list[ConversationCityInput] = Field(default_factory=list)


class ConversationSummary(BaseModel):
    """会话列表项(AI Drawer 用)。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    cities: list[ConversationCityResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    """会话详情:字段与列表项一致,前端切会话时用它刷新城市绑定。"""
