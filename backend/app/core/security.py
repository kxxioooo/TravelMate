"""安全相关:密码哈希与 JWT 的签发 / 校验。

JWT 只放在 HttpOnly Cookie 里,前端永远拿不到 token 本身。
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

ALGORITHM = "HS256"
ACCESS_TOKEN_COOKIE = "access_token"

_password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """bcrypt 哈希,数据库里只保存哈希值。"""
    return _password_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    try:
        return _password_context.verify(plain_password, hashed_password)
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    """按 user_id 签发 JWT,有效期取自 JWT_EXPIRE_MINUTES。"""
    settings = get_settings()
    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """校验 JWT 并返回 payload;签名错误 / 过期会抛出 JWTError。"""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
