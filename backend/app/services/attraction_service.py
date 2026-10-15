"""景点服务:高德 POI -> 契约结构。

职责划分:
- get_featured_attractions:默认 Top 10(只用 types=110000,不做关键词宽匹配);
- search_attractions:用户关键词搜索(types=110000 + keywords,最多 20 条/页);
- get_attraction_detail:单个 POI 详情;
- map_poi_to_summary / map_poi_to_detail:纯映射,缺失值一律 None(§36)。

本版本不让 DeepSeek 生成景点列表(§30.1)。
"""

from typing import Any, Mapping, Optional

from app.schemas.attraction import (
    AttractionDetail,
    AttractionLocation,
    AttractionSummary,
    PagedAttractionResponse,
    PhotoItem,
)
from app.services import amap_client

DEFAULT_PAGE_SIZE = 10
SEARCH_DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 20


def _clean_str(value: Any) -> Optional[str]:
    """高德缺失值是 None / "" / [],统一归一化成 None。"""
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _to_float(value: Any) -> Optional[float]:
    """高德数字字段(如 biz_ext.rating = "4.7")字符串转 float,失败返回 None。"""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _biz_ext(poi: Mapping[str, Any]) -> Mapping[str, Any]:
    """biz_ext 可能是 dict,也可能是空数组 []。"""
    biz = poi.get("biz_ext")
    return biz if isinstance(biz, Mapping) else {}


def _extract_cost(poi: Mapping[str, Any]) -> Optional[str]:
    """契约里 cost 是字符串;空数组 / 空串 -> None,数字则格式化成两位小数字符串。"""
    raw = _biz_ext(poi).get("cost")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return f"{float(raw):.2f}"
    return _clean_str(raw)


def _extract_photos(poi: Mapping[str, Any]) -> list[PhotoItem]:
    """photos: [{"title": ..., "url": ...}],title 常常是 [] -> None。"""
    photos = poi.get("photos")
    if not isinstance(photos, (list, tuple)):
        return []
    items: list[PhotoItem] = []
    for photo in photos:
        if not isinstance(photo, Mapping):
            continue
        url = _clean_str(photo.get("url"))
        if not url:
            continue
        items.append(PhotoItem(url=url, title=_clean_str(photo.get("title"))))
    return items


def _extract_tags(poi: Mapping[str, Any]) -> list[str]:
    """标签来自高德 tag / type("风景名胜;公园广场;公园"),按 ; 拆分去重。"""
    tags: list[str] = []
    for source in (_clean_str(poi.get("tag")), _clean_str(poi.get("type"))):
        if not source:
            continue
        for part in source.split(";"):
            cleaned = part.strip()
            if cleaned and cleaned not in tags:
                tags.append(cleaned)
    return tags


def _extract_location(poi: Mapping[str, Any]) -> Optional[AttractionLocation]:
    """location 是 "经度,纬度" 字符串。"""
    raw = _clean_str(poi.get("location"))
    if not raw:
        return None
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 2:
        return None
    lng, lat = _to_float(parts[0]), _to_float(parts[1])
    if lng is None or lat is None:
        return None
    return AttractionLocation(lng=lng, lat=lat)


def _valid_pois(payload: Any) -> list[Mapping[str, Any]]:
    """过滤掉没有 id / name 的脏数据,避免 Pydantic 校验炸掉整个响应。"""
    if not isinstance(payload, Mapping):
        return []
    pois = payload.get("pois")
    if not isinstance(pois, (list, tuple)):
        return []
    return [
        poi
        for poi in pois
        if isinstance(poi, Mapping) and _clean_str(poi.get("id")) and _clean_str(poi.get("name"))
    ]


def _total_count(payload: Any) -> Optional[int]:
    """高德 count 是字符串(总数上限),拿不到就 None。"""
    if not isinstance(payload, Mapping):
        return None
    count = payload.get("count")
    if isinstance(count, str) and count.strip().isdigit():
        return int(count.strip())
    if isinstance(count, int) and not isinstance(count, bool):
        return count
    return None


def _has_more(page: int, page_size: int, total: Optional[int], item_count: int) -> bool:
    """能拿到总数用总数判断,否则退化成"这一页装满了就还有下一页"。"""
    if total is not None:
        return page * page_size < total
    return item_count >= page_size


def map_poi_to_summary(poi: Mapping[str, Any]) -> AttractionSummary:
    """列表卡片:只抽 id / name / 第一张照片 / 评分 / 标签。"""
    photos = _extract_photos(poi)
    return AttractionSummary(
        poi_id=_clean_str(poi.get("id")) or "",
        name=_clean_str(poi.get("name")) or "",
        cover_photo=photos[0].url if photos else None,
        rating=_to_float(_biz_ext(poi).get("rating")),
        tags=_extract_tags(poi),
    )


def map_poi_to_detail(poi: Mapping[str, Any]) -> AttractionDetail:
    """详情:id / name / photos / address / cost / tags / location。"""
    return AttractionDetail(
        poi_id=_clean_str(poi.get("id")) or "",
        name=_clean_str(poi.get("name")) or "",
        photos=_extract_photos(poi),
        address=_clean_str(poi.get("address")),
        cost=_extract_cost(poi),
        tags=_extract_tags(poi),
        location=_extract_location(poi),
    )


def _resolve_city(city_name: Optional[str], adcode: Optional[str]) -> str:
    """高德 city 参数既能收城市名也能收 adcode,两者都给时优先城市名。"""
    return _clean_str(city_name) or _clean_str(adcode) or ""


async def get_featured_attractions(
    city_name: str, adcode: Optional[str] = None
) -> PagedAttractionResponse:
    """默认模式:该城市 10 个常见景点,使用高德默认排序(不带 keywords)。"""
    page, page_size = 1, DEFAULT_PAGE_SIZE
    payload = await amap_client.search_pois(
        city_name=_resolve_city(city_name, adcode),
        keyword=None,
        category=amap_client.ATTRACTION_TYPES,
        page=page,
        page_size=page_size,
    )
    items = [map_poi_to_summary(poi) for poi in _valid_pois(payload)][:page_size]
    total = _total_count(payload)
    return PagedAttractionResponse(
        items=items,
        page=page,
        page_size=page_size,
        has_more=_has_more(page, page_size, total, len(items)),
        total=total,
    )


async def search_attractions(
    city_name: str,
    adcode: Optional[str] = None,
    keyword: str = "",
    page: int = 1,
    page_size: int = SEARCH_DEFAULT_PAGE_SIZE,
) -> PagedAttractionResponse:
    """搜索模式:keyword 必填,城市范围内分页,page_size 上限 20。"""
    safe_keyword = _clean_str(keyword) or ""
    if not safe_keyword:
        raise ValueError("搜索关键词不能为空")
    safe_page = max(int(page or 1), 1)
    safe_page_size = min(max(int(page_size or SEARCH_DEFAULT_PAGE_SIZE), 1), MAX_PAGE_SIZE)

    payload = await amap_client.search_pois(
        city_name=_resolve_city(city_name, adcode),
        keyword=safe_keyword,
        category=amap_client.ATTRACTION_TYPES,
        page=safe_page,
        page_size=safe_page_size,
    )
    items = [map_poi_to_summary(poi) for poi in _valid_pois(payload)][:safe_page_size]
    total = _total_count(payload)
    return PagedAttractionResponse(
        items=items,
        page=safe_page,
        page_size=safe_page_size,
        has_more=_has_more(safe_page, safe_page_size, total, len(items)),
        total=total,
    )


async def get_attraction_detail(poi_id: str) -> AttractionDetail:
    """详情:取高德 POI detail 后映射成契约结构。"""
    poi = await amap_client.get_poi_detail(poi_id)
    return map_poi_to_detail(poi)
