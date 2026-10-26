"""景点路由。

一个列表接口同时承担两种模式(契约冻结):
- keyword 为空 -> 默认 Top 10(page_size 固定 10,高德默认排序);
- keyword 非空 -> 搜索模式(page_size 默认 20,允许到 20),支持 Load More。
另有 /attractions/{poi_id} 详情。全部要求登录。

v0.3.1(契约 §1 / §2 / §6.4):
- 解析 locale(body 无 locale 字段,所以按 `Accept-Language` > zh-CN);
- 英文关键词先用 query_translation_service 转成**中文**检索词再查高德
  (解析失败 -> 422 `query.unrecognized`,绝不悄悄返回默认 Top 10);
- 中文事实字段与分页字段不受语言影响,只**追加** name_en / address_en / tags_en。
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.locale import resolve_request_locale
from app.db.session import get_db
from app.models.user import User
from app.schemas.attraction import AttractionDetail, PagedAttractionResponse
from app.services import attraction_service, query_translation_service
from app.services.amap_client import AmapError, AmapNotFoundError

router = APIRouter(prefix="/attractions", tags=["attractions"])

ATTRACTION_UNAVAILABLE_DETAIL = "景点服务暂时不可用"
ATTRACTION_NOT_FOUND_DETAIL = "未找到该景点信息"
MISSING_CITY_DETAIL = "缺少城市参数"


def _resolve_city(city_name: Optional[str], adcode: Optional[str]) -> str:
    """城市名与 adcode 至少给一个,城市名优先(高德 city 参数两者都接受)。"""
    city = (city_name or "").strip() or (adcode or "").strip()
    if not city:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=MISSING_CITY_DETAIL)
    return city


@router.get("", response_model=PagedAttractionResponse)
async def list_attractions_endpoint(
    request: Request,
    city_name: Optional[str] = Query(None, max_length=100, description="城市名,如 成都"),
    adcode: Optional[str] = Query(None, max_length=20, description="城市 adcode,如 510100"),
    keyword: Optional[str] = Query(None, max_length=100, description="空 = 默认 Top 10;非空 = 搜索"),
    page: int = Query(1, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PagedAttractionResponse:
    """景点列表:默认模式或关键词搜索模式。"""
    city = _resolve_city(city_name, adcode)
    locale = resolve_request_locale(request)
    try:
        if (keyword or "").strip():
            page_size_value = min(page_size or attraction_service.SEARCH_DEFAULT_PAGE_SIZE, 20)
            # 英文 -> 中文检索词;解析不出来就是 422 受控错误(不是空列表)
            resolved_keyword = await query_translation_service.resolve_search_keyword(
                db, keyword or "", locale
            )
            return await attraction_service.search_attractions(
                city_name=city,
                adcode=None,
                keyword=resolved_keyword,
                page=page,
                page_size=page_size_value,
                locale=locale,
                db=db,
            )
        return await attraction_service.get_featured_attractions(
            city_name=city, adcode=None, locale=locale, db=db
        )
    except AmapError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=ATTRACTION_UNAVAILABLE_DETAIL
        ) from exc


@router.get("/{poi_id}", response_model=AttractionDetail)
async def get_attraction_detail_endpoint(
    request: Request,
    poi_id: str = Path(..., min_length=1, max_length=64),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AttractionDetail:
    """景点详情:照片 / 地址 / 价格 / 标签(+ 前端不展示的 location)。"""
    locale = resolve_request_locale(request)
    try:
        return await attraction_service.get_attraction_detail(poi_id, locale=locale, db=db)
    except AmapNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ATTRACTION_NOT_FOUND_DETAIL
        ) from exc
    except AmapError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=ATTRACTION_UNAVAILABLE_DETAIL
        ) from exc
