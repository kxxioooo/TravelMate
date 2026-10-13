"""偏好路由:读取 / 保存 / 跳过 Onboarding。

三个接口都要求登录,用户身份一律取自 Cookie 里的 JWT,不接受前端传 user_id。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.preference import PreferenceResponse, PreferenceUpsertRequest
from app.services import preference_service

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("/me", response_model=PreferenceResponse)
def get_my_preferences_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreferenceResponse:
    """读取当前用户偏好;从未保存过则返回统一空结构而不是 404。"""
    preference = preference_service.get_preferences_by_user_id(db, current_user.id)
    if preference is None:
        return preference_service.build_empty_preferences(current_user.id)
    return PreferenceResponse.model_validate(preference)


@router.put("/me", response_model=PreferenceResponse)
def save_my_preferences_endpoint(
    payload: PreferenceUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PreferenceResponse:
    """保存或修改偏好,同时把 onboarding_completed 置为 true。"""
    preference = preference_service.upsert_preferences(db, current_user, payload)
    return PreferenceResponse.model_validate(preference)


@router.post("/skip", response_model=UserResponse)
def skip_onboarding_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Skip:只标记 Onboarding 完成,不写入任何偏好。"""
    user = preference_service.mark_onboarding_skipped(db, current_user)
    return UserResponse.model_validate(user)
