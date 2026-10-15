"""美食 / 餐厅服务:受限 DeepSeek 出"美食名单",高德出"真实餐厅事实"。

关键约束:
- 10 种美食的餐厅查询必须并发(asyncio.gather + Semaphore(3)),
  并在每次调用前拉开一点间隔 —— 这把高德 Key 在 3 个并发附近就开始限流(§33.1);
- 单个美食查不到餐厅只让那一项 representative_restaurants = [],不影响其它美食;
- 封面图只取代表餐厅的真实 POI 照片,拿不到就是 None(§37),不调 AI 生图;
- 价格 / 地址 / 评分 / 电话全部来自高德,缺失一律 None,不编造(§36)。

v0.3 变更(§9):DeepSeek 调用从专用 `deepseek_food_client` 换成通用
`deepseek_client.generate_json()`;对外行为与函数数量(8 个)完全不变。
"""

import asyncio
import logging
from collections.abc import Mapping, Sequence
from typing import Any, Optional

from app.schemas.attraction import PhotoItem
from app.schemas.food import (
    FeaturedFoodItem,
    FeaturedFoodResponse,
    PagedRestaurantResponse,
    RestaurantDetail,
    RestaurantSummary,
)
from app.services import amap_client, deepseek_client
from app.services.deepseek_client import DeepSeekDataError

#: 并发上限:实测这把 Key 在 3 个并发附近开始限流,所以取 3
MAX_CONCURRENT_AMAP_REQUESTS = 3
#: 每次餐厅查询前的间隔,进一步降低限流概率
FOOD_REQUEST_INTERVAL_SECONDS = 0.2

#: 每种美食最多展示 2 家代表餐厅
REPRESENTATIVE_RESTAURANT_LIMIT = 2
#: 为挑出 2 家有效餐厅,每次多取一点
REPRESENTATIVE_SEARCH_SIZE = 5

DEFAULT_RESTAURANT_PAGE_SIZE = 20
MAX_RESTAURANT_PAGE_SIZE = 20

#: 目标美食数量
FOOD_TARGET_COUNT = 10

#: 受限 DeepSeek Prompt:只允许返回美食 name + description,
#: 且因为 response_format=json_object 只接受 JSON 对象,必须用 {"foods": [...]} 包装。
FOOD_SYSTEM_PROMPT = "你是一位中国地方美食专家。你只输出 JSON,不输出任何解释性文字。"

FOOD_USER_PROMPT_TEMPLATE = """请列出「{city}」最有代表性的 {count} 种当地美食。

只输出一个 JSON 对象,格式必须严格如下:
{{"foods": [{{"name": "美食名称", "description": "1~2 句简介"}}]}}

硬性要求:
1. foods 数组必须恰好 {count} 项,不多不少;
2. name 只能是美食名称本身(如"麻婆豆腐"),不要带城市名、不要带任何修饰;
3. description 用 1~2 句中文说明这道美食的特点,不要写地址、不要写餐厅名;
4. 绝对禁止输出任何餐厅的地址、电话、人均价格、评分、营业时间;
5. 绝对禁止编造具体餐厅信息,餐厅信息由其它系统查询;
6. 不要输出 Markdown 代码块,不要输出 JSON 以外的任何内容。"""

PARSE_ERROR_MESSAGE = "美食数据解析失败,请稍后重试"
EMPTY_ERROR_MESSAGE = "美食数据为空,请稍后重试"

logger = logging.getLogger(__name__)


def _clean_str(value: Any) -> Optional[str]:
    """高德缺失值是 None / "" / [],统一归一化成 None。"""
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _to_float(value: Any) -> Optional[float]:
    """高德 biz_ext.rating 是字符串(如 "4.7"),str -> float,失败返回 None。"""
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
    """契约里 cost 是字符串("73.00");空数组 / 空串 -> None,数字格式化成两位小数。"""
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


def _valid_restaurants(payload: Any) -> list[Mapping[str, Any]]:
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
    if total is not None:
        return page * page_size < total
    return item_count >= page_size


def _extract_food_items(data: Any) -> list[Any]:
    """容忍三种形态:裸数组 / {"foods": [...]} / 其它单列表字段(v0.2 容错逻辑保留)。"""
    if isinstance(data, (list, tuple)):
        return list(data)
    if isinstance(data, Mapping):
        for key in ("foods", "items", "data", "result", "list"):
            value = data.get(key)
            if isinstance(value, (list, tuple)):
                return list(value)
        list_values = [value for value in data.values() if isinstance(value, (list, tuple))]
        if len(list_values) == 1:
            return list(list_values[0])
    raise DeepSeekDataError(PARSE_ERROR_MESSAGE)


def _validate_food_items(items: Any) -> list[dict[str, str]]:
    """校验并清洗:必须是 list、name / description 非空、按 name 去重,最多取 10 个。"""
    if not isinstance(items, (list, tuple)):
        raise DeepSeekDataError(PARSE_ERROR_MESSAGE)

    validated: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        name = _clean_str(item.get("name"))
        description = _clean_str(item.get("description"))
        if not name or not description or name in seen_names:
            continue
        seen_names.add(name)
        validated.append({"name": name, "description": description})
        if len(validated) >= FOOD_TARGET_COUNT:
            break

    if not validated:
        raise DeepSeekDataError(EMPTY_ERROR_MESSAGE)
    return validated


def _resolve_city(city_name: Optional[str], adcode: Optional[str]) -> str:
    """高德 city 参数既能收城市名也能收 adcode,两者都给时优先城市名。"""
    return _clean_str(city_name) or _clean_str(adcode) or ""


def map_restaurant_summary(poi: Mapping[str, Any]) -> RestaurantSummary:
    """默认美食卡片里的餐厅只显示名字 + 详情按钮。"""
    return RestaurantSummary(
        poi_id=_clean_str(poi.get("id")) or "",
        name=_clean_str(poi.get("name")) or "",
    )


def map_restaurant_detail(poi: Mapping[str, Any]) -> RestaurantDetail:
    """餐厅详情:价格 / 地址 / 评分 / 电话 / 照片;电话保留高德原样(可能 ";" 分隔多号)。"""
    return RestaurantDetail(
        poi_id=_clean_str(poi.get("id")) or "",
        name=_clean_str(poi.get("name")) or "",
        cost=_extract_cost(poi),
        address=_clean_str(poi.get("address")),
        rating=_to_float(_biz_ext(poi).get("rating")),
        telephone=_clean_str(poi.get("tel")),
        photos=_extract_photos(poi),
    )


def select_food_cover_photo(restaurants: Optional[Sequence[Mapping[str, Any]]]) -> Optional[str]:
    """按顺序找代表餐厅的第一张真实 POI 照片;一张都没有就 None。"""
    for poi in restaurants or []:
        if not isinstance(poi, Mapping):
            continue
        photos = _extract_photos(poi)
        if photos:
            return photos[0].url
    return None


def build_food_response(
    food: Mapping[str, Any],
    restaurants: Optional[Sequence[Mapping[str, Any]]],
    cover_photo: Optional[str] = None,
) -> FeaturedFoodItem:
    """组合一道美食:name / description(来自 DeepSeek)+ 封面 + 最多 2 家真实餐厅。"""
    valid_restaurants = [
        poi
        for poi in (restaurants or [])
        if isinstance(poi, Mapping) and _clean_str(poi.get("id")) and _clean_str(poi.get("name"))
    ][:REPRESENTATIVE_RESTAURANT_LIMIT]
    return FeaturedFoodItem(
        name=_clean_str(food.get("name")) or "",
        description=_clean_str(food.get("description")) or "",
        cover_photo=cover_photo or select_food_cover_photo(valid_restaurants),
        representative_restaurants=[map_restaurant_summary(poi) for poi in valid_restaurants],
    )


async def search_representative_restaurants(
    city_name: str,
    food_name: str,
    limit: int = REPRESENTATIVE_RESTAURANT_LIMIT,
) -> list[Mapping[str, Any]]:
    """用菜名在城市范围内搜餐饮 POI,取前 limit 个有效结果(返回原始 POI,便于取照片)。"""
    payload = await amap_client.search_pois(
        city_name=_resolve_city(city_name, None),
        keyword=food_name,
        category=amap_client.RESTAURANT_TYPES,
        page=1,
        page_size=max(limit, REPRESENTATIVE_SEARCH_SIZE),
    )
    return _valid_restaurants(payload)[:limit]


async def get_featured_foods(
    city_name: str, adcode: Optional[str] = None
) -> FeaturedFoodResponse:
    """默认美食模式:DeepSeek 出 10 种美食,并发(限流保护)查各自的代表餐厅。"""
    city = _resolve_city(city_name, adcode)
    if not city:
        raise ValueError("缺少城市参数")

    foods = _validate_food_items(
        _extract_food_items(
            await deepseek_client.generate_json(
                FOOD_SYSTEM_PROMPT,
                FOOD_USER_PROMPT_TEMPLATE.format(city=city, count=FOOD_TARGET_COUNT),
            )
        )
    )
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_AMAP_REQUESTS)

    async def _load_one(food: Mapping[str, Any]) -> FeaturedFoodItem:
        async with semaphore:
            # 拉间隔,避免 3 个并发请求把高德打到 status=0(限流)
            if FOOD_REQUEST_INTERVAL_SECONDS > 0:
                await asyncio.sleep(FOOD_REQUEST_INTERVAL_SECONDS)
            restaurants = await search_representative_restaurants(city, food.get("name") or "")
        return build_food_response(food, restaurants)

    results = await asyncio.gather(
        *(_load_one(food) for food in foods), return_exceptions=True
    )

    items: list[FeaturedFoodItem] = []
    for food, result in zip(foods, results):
        if isinstance(result, BaseException):
            # 单个美食失败(含限流)只让这一项没有餐厅,不影响其余美食(§36)
            logger.warning("featured food restaurant lookup failed: %s", type(result).__name__)
            items.append(build_food_response(food, [], None))
        else:
            items.append(result)
    return FeaturedFoodResponse(items=items)


async def search_food_restaurants(
    city_name: str,
    keyword: str,
    page: int = 1,
    page_size: int = DEFAULT_RESTAURANT_PAGE_SIZE,
    adcode: Optional[str] = None,
) -> PagedRestaurantResponse:
    """用户主动搜索某种美食(如"火锅"),返回该城市相关餐厅的分页结果。"""
    safe_keyword = _clean_str(keyword) or ""
    if not safe_keyword:
        raise ValueError("搜索关键词不能为空")
    safe_page = max(int(page or 1), 1)
    safe_page_size = min(max(int(page_size or DEFAULT_RESTAURANT_PAGE_SIZE), 1), MAX_RESTAURANT_PAGE_SIZE)

    payload = await amap_client.search_pois(
        city_name=_resolve_city(city_name, adcode),
        keyword=safe_keyword,
        category=amap_client.RESTAURANT_TYPES,
        page=safe_page,
        page_size=safe_page_size,
    )
    restaurants = _valid_restaurants(payload)
    items = [map_restaurant_summary(poi) for poi in restaurants][:safe_page_size]
    total = _total_count(payload)
    return PagedRestaurantResponse(
        items=items,
        page=safe_page,
        page_size=safe_page_size,
        has_more=_has_more(safe_page, safe_page_size, total, len(items)),
        total=total,
    )


async def get_restaurant_detail(poi_id: str) -> RestaurantDetail:
    """餐厅详情:取高德 POI detail 后映射成契约结构。"""
    poi = await amap_client.get_poi_detail(poi_id)
    return map_restaurant_detail(poi)
