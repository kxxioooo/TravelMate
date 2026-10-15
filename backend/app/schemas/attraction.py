"""景点相关 Pydantic Schema。

高德的缺失值可能是空数组 `[]` / 空字符串,统一在 attraction_service 的
map_poi_to_summary / map_poi_to_detail 里归一化成 None(§36:没有就暂无信息)。
"""

from typing import Optional

from pydantic import BaseModel, Field


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


class PagedAttractionResponse(BaseModel):
    """分页响应:total 取自高德 count,拿不到就是 None。"""

    items: list[AttractionSummary] = Field(default_factory=list)
    page: int
    page_size: int
    has_more: bool
    total: Optional[int] = None
