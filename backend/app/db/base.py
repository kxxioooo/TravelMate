"""SQLAlchemy 声明式基类:所有 ORM Model 统一继承它。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """统一 metadata 入口,init_db() 依赖它建表。"""
