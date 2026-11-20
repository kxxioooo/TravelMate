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

    # v0.3.1 i18n:翻译缓存与批量结构化翻译的成本 / 稳定性闸门(§6.3 / §13.2)。
    # - translation_cache_enabled:关掉后不读也不写 entity_translations(仍然会翻译);
    # - translation_batch_size:单次 DeepSeek 请求最多带多少条待翻译字段(契约要求 ≤ 该值);
    # - translation_timeout_seconds:单次翻译请求超时,超时按失败降级,不阻塞整页;
    # - translation_max_retries:失败后的有限重试次数(0 = 不重试)。
    translation_cache_enabled: bool = True
    translation_batch_size: int = 10
    translation_timeout_seconds: float = 20.0
    translation_max_retries: int = 1

    # 任务书 §3.1:单个会话最多绑定多少个城市标签(0/1/多都合法,只是有上限)。
    conversation_city_max_count: int = 20

    # 任务书 §4 / §5:记忆与跨会话检索的授权、预算与开关。
    # 默认全部关闭 —— 用户主动授权后才会把历史/画像注入模型上下文。
    memory_feature_enabled: bool = True
    memory_history_default_enabled: bool = False
    memory_profile_learning_default_enabled: bool = False
    memory_history_lookback_days: int = 180
    memory_history_candidate_limit: int = 500
    memory_history_top_k: int = 5
    memory_history_per_conversation_limit: int = 2
    memory_history_excerpt_max_chars: int = 300
    memory_profile_max_chars: int = 600
    memory_context_max_chars: int = 2500
    memory_model_input_token_budget: int = 8000

    # 任务书 §7:本轮只预留 RAG 契约,不实现检索。
    rag_enabled: bool = False


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
