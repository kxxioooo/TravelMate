"""认证路由:注册 / 登录 / 退出 / 当前用户。

JWT 一律通过 HttpOnly Cookie 下发,响应体里永远不出现 token 本身。
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import ACCESS_TOKEN_COOKIE, create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register_endpoint(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """注册新用户,并在同一个响应里建立登录态。"""
    try:
        user = auth_service.register_user(db, payload)
    except auth_service.EmailAlreadyRegisteredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已经注册") from None
    except auth_service.UsernameAlreadyRegisteredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已经存在") from None

    settings = get_settings()
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=create_access_token(user.id),
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
        path="/",
    )
    return AuthResponse(user=UserResponse.model_validate(user), message="注册成功")


@router.post("/login", response_model=AuthResponse)
def login_endpoint(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """登录成功后写入 HttpOnly Cookie,前端无需接触 JWT。"""
    user = auth_service.authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误"
        )

    settings = get_settings()
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=create_access_token(user.id),
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
        path="/",
    )
    return AuthResponse(user=UserResponse.model_validate(user), message="登录成功")


@router.post("/logout")
def logout_endpoint(
    response: Response,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """清除 Cookie。JWT 本身无状态,退出即客户端不再持有凭证。"""
    response.delete_cookie(key=ACCESS_TOKEN_COOKIE, path="/")
    return {"message": "已退出登录"}


@router.get("/me", response_model=UserResponse)
def me_endpoint(current_user: User = Depends(get_current_user)) -> UserResponse:
    """刷新页面时前端调用它恢复登录态。"""
    return UserResponse.model_validate(current_user)
