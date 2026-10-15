"""城市浏览历史相关 Pydantic Schema。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CityHistoryCreate(BaseModel):
    """POST /cities/history 入参:前端选中城市时提交的身份字段。"""

    city_name: str = Field(min_length=1, max_length=100)
    province: Optional[str] = Field(default=None, max_length=100)
    adcode: str = Field(min_length=1, max_length=20)


class CityHistoryResponse(BaseModel):
    """Recent Searches 单条记录。"""

    model_config = ConfigDict(from_attributes=True)

    city_name: str
    province: Optional[str] = None
    adcode: str
    viewed_at: datetime
