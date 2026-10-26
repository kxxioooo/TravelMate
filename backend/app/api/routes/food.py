"""美食路由。

- GET /food/featured        默认:DeepSeek 出 10 种当地美食 + 每种最多 2 家真实餐厅;
- GET /food/restaurants     用户搜索某种美食 -> 该城市相关餐厅分页结果;
- GET /food/restaurants/{poi_id}  餐厅详情(价格 / 地址 / 评分 / 电话 / 照片)。
全部要求登录;外部服务失败统一 502 + 中文人话。

v0.3.1(契约 §1 / §2 / §6.4 / §6.5):
- 解析 locale;英文关键词先转中文再查高德(失败 422 `query.unrecognized`);
- 只**追加** name_en / description_en / address_en,数字与电话等事实字段不变。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.locale import resolve_request_locale
from app.db.session import get_db
from app.models.user import User
from app.schemas.food import FeaturedFoodResponse, PagedRestaurantResponse, RestaurantDetail
from app.services import food_service, query_translation_service
from app.services.amap_client import AmapError, AmapNotFoundError
from app.services.deepseek_client import DeepSeekError

router = APIRouter(prefix="/food", tags=["food"])

FEATURED_UNAVAILABLE_DETAIL = "美食推荐服务暂时不可用"
RESTAURANT_UNAVAILABLE_DETAIL = "餐厅服务暂时不可用"
RESTAURANT_NOT_FOUND_DETAIL = "未找到该餐厅信息"
MISSING_CITY_DETAIL = "缺少城市参数"


def _resolve_city(city_name: Optional[str], adcode: Optional[str]) -> str:
    """城市名与 adcode 至少给一个,城市名优先(高德 city 参数两者都接受)。"""
    city = (city_name or "").strip() or (adcode or "").strip()
    if not city:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=MISSING_CITY_DETAIL)
    return city


@router.get("/featured", response_model=FeaturedFoodResponse)
async def get_featured_foods_endpoint(
    request: Request,
    city_name: Optional[str] = Query(None, max_length=100, description="城市名,如 成都"),
    adcode: Optional[str] = Query(None, max_length=20, description="城市 adcode,如 510100"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeaturedFoodResponse:
    """默认美食模式:目标 10 种当地代表性美食,每种最多 2 家代表餐厅。"""
    city = _resolve_city(city_name, adcode)
    locale = resolve_request_locale(request)
    try:
        return await food_service.get_featured_foods(
            city_name=city, adcode=None, locale=locale, db=db
        )
    except DeepSeekError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=FEATURED_UNAVAILABLE_DETAIL
        ) from exc
    except AmapError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=RESTAURANT_UNAVAILABLE_DETAIL
        ) from exc


@router.get("/restaurants", response_model=PagedRestaurantResponse)
async def search_food_restaurants_endpoint(
    request: Request,
    keyword: str = Query(..., min_length=1, max_length=100, description="美食关键词,如 火锅"),
    city_name: Optional[str] = Query(None, max_length=100),
    adcode: Optional[str] = Query(None, max_length=20),
    page: int = Query(1, ge=1),
    page_size: int = Query(food_service.DEFAULT_RESTAURANT_PAGE_SIZE, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PagedRestaurantResponse:
    """搜索模式:当前城市中与该美食关键词相关的餐厅,支持 Load More。"""
    city = _resolve_city(city_name, adcode)
    locale = resolve_request_locale(request)
    try:
        resolved_keyword = await query_translation_service.resolve_search_keyword(
            db, keyword, locale
        )
        return await food_service.search_food_restaurants(
            city_name=city,
            keyword=resolved_keyword,
            page=page,
            page_size=page_size,
            adcode=None,
            locale=locale,
            db=db,
        )
    except AmapError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=RESTAURANT_UNAVAILABLE_DETAIL
        ) from exc


@router.get("/restaurants/{poi_id}", response_model=RestaurantDetail)
async def get_restaurant_detail_endpoint(
    request: Request,
    poi_id: str = Path(..., min_length=1, max_length=64),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RestaurantDetail:
    """餐厅详情:价格 / 地址 / 评分 / 电话 / 照片,缺失字段一律 None。"""
    locale = resolve_request_locale(request)
    try:
        return await food_service.get_restaurant_detail(poi_id, locale=locale, db=db)
    except AmapNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=RESTAURANT_NOT_FOUND_DETAIL
        ) from exc
    except AmapError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=RESTAURANT_UNAVAILABLE_DETAIL
        ) from exc
