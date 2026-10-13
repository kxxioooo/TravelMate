"""认证依赖:从 HttpOnly Cookie 取 JWT,解析出当前登录用户。

后续任何需要登录的接口都复用 get_current_user。
"""

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import ACCESS_TOKEN_COOKIE, decode_access_token
from app.db.session import get_db
from app.models.user import User

UNAUTHORIZED_DETAIL = "未登录或登录已失效"


def get_token_from_cookie(request: Request) -> str:
    """读取 HttpOnly Cookie 中的 JWT,缺失则 401。"""
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=UNAUTHORIZED_DETAIL)
    return token


def get_current_user(
    token: str = Depends(get_token_from_cookie),
    db: Session = Depends(get_db),
) -> User:
    """cookie -> 解码 JWT -> user_id -> 查库 -> User;任一步失败都是 401。"""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=UNAUTHORIZED_DETAIL
    )
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise unauthorized from None

    subject = payload.get("sub")
    if not subject:
        raise unauthorized
    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise unauthorized from None

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user
