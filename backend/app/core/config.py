"""应用配置:集中读取环境变量,并构造数据库连接串。

其它模块一律通过 get_settings() 读取配置,不直接读 os.environ,
这样将来增加 DEEPSEEK_API_KEY / AMAP_API_KEY 时只需要改这一处。
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> backend/app/core/config.py
BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    """v0.1 全部可配置项。字段名与环境变量名大小写无关。"""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "travelmate"
    mysql_password: str = "change_me"
    mysql_database: str = "travelmate"

    jwt_secret: str = "change_me"
    jwt_expire_minutes: int = 1440

    frontend_origin: str = "http://localhost:5173"

    # v0.2 第三方服务:高德(天气 / POI)+ DeepSeek(美食名单 → v0.3 起是通用 Chat / Tool Calling)
    # 默认值一律是占位符:缺失或仍是 change_me 时业务层给出可控错误,绝不带着假 Key 发请求。
    amap_api_key: str = "change_me"
    deepseek_api_key: str = "change_me"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # v0.3 Agent:工具循环上限(防止模型无限调工具)+ 单次请求注入的历史消息条数上限。
    # 数据库仍然保存全部消息,这两个值只影响单次请求的 token 成本(§17.5 / §33)。
    agent_max_tool_rounds: int = 5
    agent_context_message_limit: int = 30


@lru_cache
def get_settings() -> Settings:
    """加载并缓存环境变量,整个进程只解析一次 .env。"""
    return Settings()


def build_database_url(settings: Settings) -> str:
    """构造 SQLAlchemy 使用的 mysql+pymysql 连接串(密码做 URL 编码)。"""
    return (
        f"mysql+pymysql://{settings.mysql_user}:{quote_plus(settings.mysql_password)}"
        f"@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}"
        f"?charset=utf8mb4"
    )
