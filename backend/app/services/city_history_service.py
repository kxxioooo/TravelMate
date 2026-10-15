"""城市浏览历史服务:Recent Searches 的读写。

同一用户同一 adcode 只保留一条记录(UNIQUE(user_id, adcode)),
再次打开同一座城市时更新 viewed_at,不新增重复项。
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.city_history import CityViewHistory
from app.schemas.city import CityHistoryCreate

RECENT_CITY_LIMIT = 10


def _utcnow() -> datetime:
    """不带时区的 UTC 现在(与 v0.1 Model 的时间口径一致)。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def record_city_view(db: Session, user_id: int, data: CityHistoryCreate) -> CityViewHistory:
    """选中城市时写入历史:存在则更新,不存在则新增。"""
    record = db.scalar(
        select(CityViewHistory).where(
            CityViewHistory.user_id == user_id,
            CityViewHistory.adcode == data.adcode,
        )
    )
    if record is None:
        record = CityViewHistory(
            user_id=user_id,
            city_name=data.city_name,
            province=data.province,
            adcode=data.adcode,
            viewed_at=_utcnow(),
        )
        db.add(record)
    else:
        record.city_name = data.city_name
        record.province = data.province
        record.viewed_at = _utcnow()

    db.commit()
    db.refresh(record)
    return record


def get_recent_cities(db: Session, user_id: int, limit: int = RECENT_CITY_LIMIT) -> list[CityViewHistory]:
    """最近浏览:按 viewed_at 倒序,最多 limit 条(默认 10)。"""
    statement = (
        select(CityViewHistory)
        .where(CityViewHistory.user_id == user_id)
        .order_by(CityViewHistory.viewed_at.desc(), CityViewHistory.id.desc())
        .limit(limit)
    )
    return list(db.scalars(statement).all())
