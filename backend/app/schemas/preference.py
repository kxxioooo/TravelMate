"""偏好相关 Pydantic Schema。"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PreferenceUpsertRequest(BaseModel):
    """Save 偏好的入参;未选中的维度允许留空,不伪造用户意图。"""

    attraction_preferences: list[str] = Field(default_factory=list)
    food_preferences: list[str] = Field(default_factory=list)
    budget: Optional[str] = None
    travel_pace: Optional[str] = None


class PreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    user_id: int
    attraction_preferences: list[str] = Field(default_factory=list)
    food_preferences: list[str] = Field(default_factory=list)
    budget: Optional[str] = None
    travel_pace: Optional[str] = None
