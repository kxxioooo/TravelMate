"""城市浏览历史路由:Recent Searches。

两个接口都要求登录,用户身份一律取自 Cookie 里的 JWT,不接受前端传 user_id。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.city import CityHistoryCreate, CityHistoryResponse
from app.services import city_history_service

router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("/history", response_model=list[CityHistoryResponse])
def get_recent_cities_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CityHistoryResponse]:
    """最近浏览的城市,最多 10 条,按 viewed_at 倒序。"""
    records = city_history_service.get_recent_cities(db, current_user.id)
    return [CityHistoryResponse.model_validate(record) for record in records]


@router.post("/history", response_model=CityHistoryResponse)
def record_city_view_endpoint(
    payload: CityHistoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CityHistoryResponse:
    """记录一次城市浏览;同 user + adcode 已存在时只更新 viewed_at。"""
    record = city_history_service.record_city_view(db, current_user.id, payload)
    return CityHistoryResponse.model_validate(record)
