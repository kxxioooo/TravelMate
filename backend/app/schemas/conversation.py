"""Conversation 相关 Pydantic Schema(§14 + 任务书 §3.1)。

前端契约(§14 / §15):
- ConversationSummary = id / title / cities / created_at / updated_at
- ConversationDetail  = 与 Summary 同字段
- 创建 / 修改城市都允许 `{"cities": []}`,即 0 个城市也能开会话。

任务书 §3.1 的强化:
- 字段 trim;`adcode` 按服务端城市目录验证;
- 城市名称**以目录为准**,不信任客户端传的 `city_name`;
- 按 adcode 去重、保留用户顺序、限制上限(`CONVERSATION_CITY_MAX_COUNT`);
- 非法输入**整组失败**(Pydantic 报 422),绝不部分写入、绝不默默丢弃;
- `PUT /conversations/{id}/cities` 要求**显式**带 `cities` 字段,漏传即 422,避免误清空。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import get_settings
from app.services import city_catalog_service


class ConversationCityInput(BaseModel):
    """新建会话 / 修改会话城市时的单个城市。"""

    city_name: str = Field(..., min_length=1, max_length=100)
    adcode: str = Field(..., min_length=1, max_length=20)

    @field_validator("city_name", "adcode", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        """前后空白一律去掉;纯空白会变成空串,交给 min_length 拒绝。"""
        if isinstance(value, str):
            return value.strip()
        return value


def _normalize_city_list(cities: list[ConversationCityInput]) -> list[ConversationCityInput]:
    """校验 + 规范化:以目录为准、去重、保序、限上限;非法则整组失败。"""
    max_count = get_settings().conversation_city_max_count

    if len(cities) > max_count:
        raise ValueError(f"最多只能绑定 {max_count} 个城市")

    normalized = city_catalog_service.validate_and_normalize_cities(
        [city.model_dump() for city in cities], max_count=max_count
    )
    return [ConversationCityInput(**item) for item in normalized]


class ConversationCityResponse(BaseModel):
    """返回给前端的会话城市(name 给 UI 显示,adcode 给工具查真实数据)。"""

    model_config = ConfigDict(from_attributes=True)

    city_name: str
    adcode: str


class ConversationCreateRequest(BaseModel):
    """POST /conversations 的入参;`cities` 允许省略或为空数组。"""

    cities: list[ConversationCityInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize(self) -> "ConversationCreateRequest":
        self.cities = _normalize_city_list(self.cities)
        return self


class ConversationUpdateCitiesRequest(BaseModel):
    """PUT /conversations/{id}/cities 的入参:整组替换。

    `cities` **必填**(空数组表示清空);漏传字段直接 422,
    这样"忘记带 body"不会被误解读成"清空城市"。
    """

    cities: list[ConversationCityInput] = Field(...)

    @model_validator(mode="after")
    def _normalize(self) -> "ConversationUpdateCitiesRequest":
        self.cities = _normalize_city_list(self.cities)
        return self


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
