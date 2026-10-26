"""v0.3.1 统一业务错误码(契约 §5)。

v0.3 的错误全是 `HTTPException(detail="中文人话")`,前端只能按句子翻译。
v0.3.1 新增 `AppError` + 机器可读 `error_code` / `message_key`,响应体:

    {"detail": "中文原文(向后兼容)", "error_code": "query.unrecognized",
     "message_key": "error.query.unrecognized"}

`detail` 仍然是字符串(v0.3 前端读它做兜底),所以老客户端不会坏。
这里只登记错误码与默认中文文案,**不改变** v0.3 已有 `HTTPException` 的行为。
"""

from typing import Any, Optional

# --- 错误码清单(契约 §5,逐条对齐,新增码必须同步前端 error.* 资源) ---------------
AUTH_INVALID_CREDENTIALS = "auth.invalid_credentials"
AUTH_EMAIL_EXISTS = "auth.email_exists"
AUTH_USERNAME_EXISTS = "auth.username_exists"
AUTH_UNAUTHORIZED = "auth.unauthorized"
PREFERENCE_SAVE_FAILED = "preference.save_failed"
WEATHER_UNAVAILABLE = "weather.unavailable"
AMAP_RATE_LIMITED = "amap.rate_limited"
AMAP_UNAVAILABLE = "amap.unavailable"
ATTRACTION_UNAVAILABLE = "attraction.unavailable"
FOOD_UNAVAILABLE = "food.unavailable"
QUERY_UNRECOGNIZED = "query.unrecognized"
AGENT_FAILED = "agent.failed"
AGENT_TOOL_REJECTED = "agent.tool_rejected"
TRANSLATION_UNAVAILABLE = "translation.unavailable"
CONVERSATION_NOT_FOUND = "conversation.not_found"
VALIDATION_FAILED = "validation.failed"
SERVER_UNAVAILABLE = "server.unavailable"

#: 全部合法错误码(顺序与契约一致)
ERROR_CODES: tuple[str, ...] = (
    AUTH_INVALID_CREDENTIALS,
    AUTH_EMAIL_EXISTS,
    AUTH_USERNAME_EXISTS,
    AUTH_UNAUTHORIZED,
    PREFERENCE_SAVE_FAILED,
    WEATHER_UNAVAILABLE,
    AMAP_RATE_LIMITED,
    AMAP_UNAVAILABLE,
    ATTRACTION_UNAVAILABLE,
    FOOD_UNAVAILABLE,
    QUERY_UNRECOGNIZED,
    AGENT_FAILED,
    AGENT_TOOL_REJECTED,
    TRANSLATION_UNAVAILABLE,
    CONVERSATION_NOT_FOUND,
    VALIDATION_FAILED,
    SERVER_UNAVAILABLE,
)

#: 错误码 -> HTTP 状态码
ERROR_CODE_STATUS: dict[str, int] = {
    AUTH_INVALID_CREDENTIALS: 401,
    AUTH_EMAIL_EXISTS: 409,
    AUTH_USERNAME_EXISTS: 409,
    AUTH_UNAUTHORIZED: 401,
    PREFERENCE_SAVE_FAILED: 500,
    WEATHER_UNAVAILABLE: 502,
    AMAP_RATE_LIMITED: 429,
    AMAP_UNAVAILABLE: 502,
    ATTRACTION_UNAVAILABLE: 502,
    FOOD_UNAVAILABLE: 502,
    QUERY_UNRECOGNIZED: 422,
    AGENT_FAILED: 502,
    AGENT_TOOL_REJECTED: 422,
    TRANSLATION_UNAVAILABLE: 502,
    CONVERSATION_NOT_FOUND: 404,
    VALIDATION_FAILED: 422,
    SERVER_UNAVAILABLE: 500,
}

#: 错误码 -> 默认中文文案(detail 字段,保持 v0.3 的中文风格)
ERROR_CODE_DETAILS: dict[str, str] = {
    AUTH_INVALID_CREDENTIALS: "邮箱或密码错误",
    AUTH_EMAIL_EXISTS: "该邮箱已注册",
    AUTH_USERNAME_EXISTS: "该用户名已被占用",
    AUTH_UNAUTHORIZED: "未登录或登录已失效",
    PREFERENCE_SAVE_FAILED: "偏好保存失败",
    WEATHER_UNAVAILABLE: "天气服务暂时不可用",
    AMAP_RATE_LIMITED: "外部数据服务请求过于频繁,请稍后重试",
    AMAP_UNAVAILABLE: "外部数据服务暂时不可用",
    ATTRACTION_UNAVAILABLE: "景点服务暂时不可用",
    FOOD_UNAVAILABLE: "美食推荐服务暂时不可用",
    QUERY_UNRECOGNIZED: "无法可靠识别该搜索词,请换一个关键词",
    AGENT_FAILED: "AI 助手暂时不可用,请稍后重试",
    AGENT_TOOL_REJECTED: "该请求未被允许,请先选择城市或调整参数",
    TRANSLATION_UNAVAILABLE: "翻译服务暂时不可用",
    CONVERSATION_NOT_FOUND: "未找到该会话",
    VALIDATION_FAILED: "请求参数不合法",
    SERVER_UNAVAILABLE: "服务器暂时不可用",
}

MESSAGE_KEY_PREFIX = "error."


def build_message_key(error_code: str) -> str:
    """错误码 -> 前端 i18n key(`error.<code>`,契约 §5/§6)。"""
    return f"{MESSAGE_KEY_PREFIX}{error_code}"


class AppError(Exception):
    """受控业务异常:同时带中文 detail 与机器可读错误码。

    用法:
        raise AppError(QUERY_UNRECOGNIZED)            # 状态码/文案走登记表
        raise AppError(QUERY_UNRECOGNIZED, detail="…") # 覆盖文案
        raise AppError(QUERY_UNRECOGNIZED, status_code=422)

    未登记的 code 也能用(状态码默认 400,文案给通用提示),但会记 warning,
    方便开发时发现"前端 key 没有对应后端码"。
    """

    def __init__(
        self,
        code: str = SERVER_UNAVAILABLE,
        detail: Optional[str] = None,
        status_code: Optional[int] = None,
        message_key: Optional[str] = None,
    ) -> None:
        self.code = str(code or SERVER_UNAVAILABLE)
        self.detail = (
            detail
            if isinstance(detail, str) and detail.strip()
            else ERROR_CODE_DETAILS.get(self.code, ERROR_CODE_DETAILS[SERVER_UNAVAILABLE])
        )
        self.status_code = int(
            status_code
            if status_code is not None
            else ERROR_CODE_STATUS.get(self.code, 400)
        )
        self.message_key = message_key or build_message_key(self.code)
        super().__init__(self.detail)

    @property
    def error_code(self) -> str:
        """响应体里的字段名是 error_code,这里给个别名方便调用方读取。"""
        return self.code

    def to_response_body(self) -> dict[str, Any]:
        """契约 §5 的响应体:detail + error_code + message_key。"""
        return {
            "detail": self.detail,
            "error_code": self.code,
            "message_key": self.message_key,
        }

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<AppError {self.code} status={self.status_code}>"
