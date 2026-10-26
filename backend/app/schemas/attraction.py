"""景点相关 Pydantic Schema。

高德的缺失值可能是空数组 `[]` / 空字符串,统一在 attraction_service 的
map_poi_to_summary / map_poi_to_detail 里归一化成 None(§36:没有就暂无信息)。

v0.3.1(契约 §2)只做**追加**:`name_en` / `address_en` / `tags_en` 及来源标记。
- 老字段一个都不删、语义不变;
- 新字段为 None 时通过 `exclude_if` 不参与序列化 -> 不带 locale 的老客户端
  拿到的响应与 v0.3 一模一样;
- `poi_id` / `location` / `rating` / `cost` / `photos` 永远不被翻译或改写。
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.localization import FieldSource, exclude_when_none


class PhotoItem(BaseModel):
    """高德 POI 照片:只存网络 URL,服务器不下载、不落盘(§37)。"""

    url: str
    title: Optional[str] = None


class AttractionSummary(BaseModel):
    """列表 / 卡片:前端 Card 需要的最小集合。"""

    poi_id: str
    name: str
    cover_photo: Optional[str] = None
    rating: Optional[float] = None
    tags: list[str] = Field(default_factory=list)
    # --- v0.3.1 双语展示字段(可选,向后兼容) ---
    name_en: Optional[str] = Field(default=None, exclude_if=exclude_when_none)
    name_en_source: Optional[FieldSource] = Field(default=None, exclude_if=exclude_when_none)


class AttractionLocation(BaseModel):
    """经纬度:后端允许返回,前端详情 Dialog 不展示。"""

    lng: float
    lat: float


class AttractionDetail(BaseModel):
    """详情:更多照片 / 地址 / 价格 / 标签(+ 前端不显示的 location)。"""

    poi_id: str
    name: str
    photos: list[PhotoItem] = Field(default_factory=list)
    address: Optional[str] = None
    cost: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    location: Optional[AttractionLocation] = None
    # --- v0.3.1 双语展示字段(可选,向后兼容) ---
    name_en: Optional[str] = Field(default=None, exclude_if=exclude_when_none)
    name_en_source: Optional[FieldSource] = Field(default=None, exclude_if=exclude_when_none)
    address_en: Optional[str] = Field(default=None, exclude_if=exclude_when_none)
    address_en_source: Optional[FieldSource] = Field(default=None, exclude_if=exclude_when_none)
    tags_en: Optional[list[str]] = Field(default=None, exclude_if=exclude_when_none)


class PagedAttractionResponse(BaseModel):
    """分页响应:total 取自高德 count,拿不到就是 None。"""

    items: list[AttractionSummary] = Field(default_factory=list)
    page: int
    page_size: int
    has_more: bool
    total: Optional[int] = None
