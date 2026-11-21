"""ORM 模型集中导出。

`init_db()` 与 Alembic 的 `env.py` 都依赖"import 这个包 = 注册全部模型"。
新增模型时**必须**在这里补一行,否则建表/迁移会漏表。
"""

from app.models import (  # noqa: F401
    city_history,
    conversation,
    conversation_city,
    entity_translation,
    knowledge_chunk,
    knowledge_document,
    memory_exclusion,
    memory_item,
    memory_settings,
    memory_source,
    message,
    preference,
    rag_ingestion_job,
    rag_message_citation,
    user,
    user_profile,
)

__all__ = [
    "city_history",
    "conversation",
    "conversation_city",
    "entity_translation",
    "knowledge_chunk",
    "knowledge_document",
    "memory_exclusion",
    "memory_item",
    "memory_settings",
    "memory_source",
    "message",
    "preference",
    "rag_ingestion_job",
    "rag_message_citation",
    "user",
    "user_profile",
]
