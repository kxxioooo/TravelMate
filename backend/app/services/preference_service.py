"""偏好服务层:读取 / 保存 / 跳过 Onboarding。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.preference import UserPreference
from app.models.user import User
from app.schemas.preference import PreferenceResponse, PreferenceUpsertRequest


def get_preferences_by_user_id(db: Session, user_id: int) -> UserPreference | None:
    """查询某个用户的偏好记录,没有则返回 None。"""
    return db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))


def build_empty_preferences(user_id: int) -> PreferenceResponse:
    """新用户的统一空结构:前端拿到的永远是同一形状,不用做空值判断。"""
    return PreferenceResponse(
        id=None,
        user_id=user_id,
        attraction_preferences=[],
        food_preferences=[],
        budget=None,
        travel_pace=None,
    )


def upsert_preferences(db: Session, user: User, data: PreferenceUpsertRequest) -> UserPreference:
    """不存在就 INSERT,存在就 UPDATE,并标记 Onboarding 已完成。"""
    preference = get_preferences_by_user_id(db, user.id)
    if preference is None:
        preference = UserPreference(user_id=user.id)
        db.add(preference)

    preference.attraction_preferences = list(data.attraction_preferences)
    preference.food_preferences = list(data.food_preferences)
    preference.budget = data.budget
    preference.travel_pace = data.travel_pace
    user.onboarding_completed = True

    db.commit()
    db.refresh(preference)
    db.refresh(user)
    return preference


def mark_onboarding_skipped(db: Session, user: User) -> User:
    """Skip 只标记完成,不伪造任何偏好数据。"""
    user.onboarding_completed = True
    db.commit()
    db.refresh(user)
    return user
