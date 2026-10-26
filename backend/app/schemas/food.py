"""美食 / 餐厅相关 Pydantic Schema。

约定:
- 餐厅列表只需要 poi_id + name(详情按钮另外拉 /food/restaurants/{poi_id});
- 美食封面一律来自真实餐厅 POI 照片,拿不到就是 None,前端用占位图(§37);
- 缺失字段一律 None,绝不编造(§36)。

v0.3.1(契约 §2)只做**追加**:`name_en` / `address_en` / `description_en`
及来源标记;None 时不参与序列化,老客户端行为不变。
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.attraction import PhotoItem
from app.schemas.localization import FieldSource, exclude_when_none


class RestaurantSummary(BaseModel):
    """默认美食卡片里的代表餐厅:只显示名字 + 详情按钮。"""

    poi_id: str
    name: str
    # --- v0.3.1 双语展示字段(可选,向后兼容) ---
    name_en: Optional[str] = Field(default=None, exclude_if=exclude_when_none)
    name_en_source: Optional[FieldSource] = Field(default=None, exclude_if=exclude_when_none)


class RestaurantDetail(BaseModel):
    """餐厅详情:价格 / 地址 / 评分 / 电话 / 照片。"""

    poi_id: str
    name: str
    cost: Optional[str] = None
    address: Optional[str] = None
    rating: Optional[float] = None
    telephone: Optional[str] = None
    photos: list[PhotoItem] = Field(default_factory=list)
    # --- v0.3.1 双语展示字段(可选,向后兼容;数字/电话/照片保持原值) ---
    name_en: Optional[str] = Field(default=None, exclude_if=exclude_when_none)
    name_en_source: Optional[FieldSource] = Field(default=None, exclude_if=exclude_when_none)
    address_en: Optional[str] = Field(default=None, exclude_if=exclude_when_none)
    address_en_source: Optional[FieldSource] = Field(default=None, exclude_if=exclude_when_none)


class FeaturedFoodItem(BaseModel):
    """DeepSeek 只提供 name + description,其余全部来自高德。"""

    name: str
    description: str
    cover_photo: Optional[str] = None
    representative_restaurants: list[RestaurantSummary] = Field(default_factory=list)
    # --- v0.3.1 双语展示字段(可选,向后兼容) ---
    name_en: Optional[str] = Field(default=None, exclude_if=exclude_when_none)
    description_en: Optional[str] = Field(default=None, exclude_if=exclude_when_none)


class FeaturedFoodResponse(BaseModel):
    """目标 10 种当地代表性美食;不足 10 个也如实返回。"""

    items: list[FeaturedFoodItem] = Field(default_factory=list)


class PagedRestaurantResponse(BaseModel):
    """用户主动搜索某种美食时的餐厅分页结果。"""

    items: list[RestaurantSummary] = Field(default_factory=list)
    page: int
    page_size: int
    has_more: bool
    total: Optional[int] = None
