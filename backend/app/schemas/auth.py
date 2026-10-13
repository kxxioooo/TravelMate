"""认证相关 Pydantic Schema。

密码长度上限 72 是因为 bcrypt 只处理前 72 字节,提前挡住比运行时报错更友好。
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserResponse(BaseModel):
    """返回给前端的用户信息:绝不含 password_hash。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    onboarding_completed: bool


class AuthResponse(BaseModel):
    user: UserResponse
    message: str
