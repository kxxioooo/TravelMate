"""应用配置:集中读取环境变量,并构造数据库连接串。

其它模块一律通过 get_settings() 读取配置,不直接读 os.environ,
这样将来增加 DEEPSEEK_API_KEY / AMAP_API_KEY 时只需要改这一处。
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import model_validator
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

    # 任务书 §7 / 《RAG》§12.1:知识增强的总开关与各路径开关。
    # 默认全关:索引与 API 就绪后再逐级开启;关闭时必须无缝退回原有聊天。
    rag_enabled: bool = False
    rag_local_enabled: bool = True
    rag_web_enabled: bool = False
    rag_memory_enabled: bool = True

    # Embedding:默认真实的 bge-m3;只有显式设 RAG_EMBEDDING_PROVIDER=hash
    # 才走离线降级实现(供离线测试/CI,**不是**生产默认)。
    rag_embedding_provider: str = "bge-m3"
    rag_embedding_model: str = "BAAI/bge-m3"
    rag_embedding_dim: int = 1024
    rag_embedding_batch_size: int = 8

    # 向量库(Milvus Lite 本地持久化;部署时可切 Standalone 的 URI)
    rag_vector_backend: str = "milvus-lite"
    rag_milvus_uri: str = "./app/data/rag_state/travelmate_milvus.db"
    rag_collection: str = "travelmate_knowledge_bgem3_v1"

    # 切分与检索参数
    rag_chunk_size: int = 700
    rag_chunk_overlap: int = 120
    rag_dense_top_k: int = 20
    rag_bm25_top_k: int = 20
    rag_final_top_k: int = 6
    rag_max_evidence_chars: int = 6000
    rag_retrieval_timeout_seconds: float = 12.0
    rag_max_tool_searches_per_turn: int = 1

    # 联网检索(没有有效 Provider/Key 时明确禁用,绝不谎称联网已发生)
    web_search_provider: str = "none"
    tavily_api_key: str = ""
    web_search_timeout_seconds: float = 8.0
    web_search_max_results: int = 5
    web_page_max_bytes: int = 1_048_576
    web_cache_ttl_seconds: int = 3600

    @model_validator(mode="after")
    def _validate_rag(self) -> "Settings":
        """启动即校验:参数矛盾时直接失败,而不是运行到一半才发现。"""
        if self.rag_chunk_size <= 0:
            raise ValueError("RAG_CHUNK_SIZE 必须大于 0")
        if self.rag_chunk_overlap < 0:
            raise ValueError("RAG_CHUNK_OVERLAP 不能为负")
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError("RAG_CHUNK_OVERLAP 必须小于 RAG_CHUNK_SIZE")
        for name in ("rag_dense_top_k", "rag_bm25_top_k", "rag_final_top_k"):
            if int(getattr(self, name)) <= 0:
                raise ValueError(f"{name.upper()} 必须大于 0")
        if self.rag_embedding_dim <= 0:
            raise ValueError("RAG_EMBEDDING_DIM 必须大于 0")
        return self


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
