"""认证服务层:所有用户读写逻辑都在这里,路由只负责 HTTP 语义。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import RegisterRequest


class AuthServiceError(Exception):
    """认证业务异常基类。"""


class EmailAlreadyRegisteredError(AuthServiceError):
    """邮箱已被注册。"""


class UsernameAlreadyRegisteredError(AuthServiceError):
    """用户名已存在。"""


def get_user_by_email(db: Session, email: str) -> User | None:
    """按 email 查询用户,不存在返回 None。"""
    return db.scalar(select(User).where(User.email == email.lower()))


def get_user_by_username(db: Session, username: str) -> User | None:
    """按 username 查询用户,不存在返回 None。"""
    return db.scalar(select(User).where(User.username == username))


def register_user(db: Session, data: RegisterRequest) -> User:
    """注册:先查重,再哈希密码,最后落库并刷新出 id / 时间戳。"""
    email = data.email.lower()
    if get_user_by_email(db, email) is not None:
        raise EmailAlreadyRegisteredError
    if get_user_by_username(db, data.username) is not None:
        raise UsernameAlreadyRegisteredError

    user = User(
        username=data.username,
        email=email,
        password_hash=hash_password(data.password),
        onboarding_completed=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """登录校验:用户不存在或密码不匹配都返回 None,不区分原因以防枚举账号。"""
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
