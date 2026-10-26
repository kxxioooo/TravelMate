"""英文搜索词 -> 中文关键词(契约 §6.4 / §8 的"最容易被做错的一条")。

**绝不能**把英文关键词悄悄丢掉、退化成"默认 Top 10":那样用户搜 `ancient town`
会以为该城市没有古镇,而实际上只是把过滤条件丢了。这里的顺序是硬约定:

1. 原样命中 `search_aliases`(经审核别名表) -> 得到中文关键词;
2. 命中 `places` / `dishes` 的英文名或别名 -> 得到中文关键词;
3. 输入本身含中文 -> 直接当中文用;
4. 以上都没有 -> 单次受控 DeepSeek 结构化翻译(可缓存);
5. 仍然失败 -> `AppError("query.unrecognized")`(HTTP 422),让前端明确提示。

高德收到的永远是中文关键词 + 调用方原有的 `types` 过滤,行为与 v0.2 完全一致。
"""

import asyncio
import json
import logging
import re
from typing import Any, Optional

from app.core.config import get_settings
from app.core.errors import QUERY_UNRECOGNIZED, AppError
from app.core.locale import DEFAULT_LOCALE
from app.models.entity_translation import PROVIDER_DEEPSEEK, TRANSLATION_VERSION
from app.schemas.localization import parse_query_keyword, sanitize_translation_text
from app.services import deepseek_client, entity_localization_service, translation_cache_service

logger = logging.getLogger(__name__)

#: 搜索结果只用于高德检索,长度与 v0.2 的 keyword 上限保持一致
MAX_QUERY_LENGTH = 100

#: 搜索词翻译缓存的键:同一英文搜索词第二次不会再调模型
QUERY_CACHE_FIELD = "search_keyword"
QUERY_CACHE_TARGET_LOCALE = "zh-CN"

DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_RETRIES = 1

#: 任何 CJK 统一表意文字都算"已经含中文"
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
#: 归一化:去掉首尾标点/引号,塌掉多余空白
_EDGE_PUNCTUATION = " \t\r\n\"'“”‘’.,!?;:。、,;:!?"

QUERY_TRANSLATION_SYSTEM_PROMPT = (
    "你是一名搜索词翻译器,负责把英文旅游搜索词转换成中国地图服务可检索的中文关键词。"
    "你只输出 JSON,不输出任何解释。"
)

QUERY_TRANSLATION_USER_PROMPT_TEMPLATE = """用户在英文界面搜索中国城市里的景点或美食。
请把下面的英文搜索词翻译成最适合在中国高德地图检索的简体中文关键词。

硬性要求:
1. 只输出一个 JSON 对象:{{"keyword_zh": "中文关键词"}};
2. 只给一个简短的名词性关键词(2~10 个字),不要整句、不要解释、不要引号;
3. 通用类别词只能翻译成通用类别词(例如 ancient town -> 古镇),
   绝对不能替换成某个具体的景点名、店铺名或品牌名;
4. 无法确定时输出空字符串 ""。

英文搜索词:{keyword}"""


def normalize_query(keyword: Any) -> str:
    """归一化搜索词:去首尾空白与标点、折叠空白、限制长度。"""
    if not isinstance(keyword, str):
        return ""
    text = re.sub(r"\s+", " ", keyword.strip())
    text = text.strip(_EDGE_PUNCTUATION)
    return text[:MAX_QUERY_LENGTH].strip()


def contains_chinese(text: Any) -> bool:
    """是否包含中文(含中文就直接当高德关键词用,不再翻译)。"""
    return isinstance(text, str) and bool(_CJK_RE.search(text))


def _settings_snapshot() -> dict[str, Any]:
    settings = get_settings()
    timeout = getattr(settings, "translation_timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    max_retries = getattr(settings, "translation_max_retries", DEFAULT_MAX_RETRIES)
    try:
        safe_timeout = max(float(timeout or DEFAULT_TIMEOUT_SECONDS), 0.1)
    except (TypeError, ValueError):
        safe_timeout = DEFAULT_TIMEOUT_SECONDS
    try:
        safe_retries = max(int(max_retries or 0), 0)
    except (TypeError, ValueError):
        safe_retries = DEFAULT_MAX_RETRIES
    return {
        "cache_enabled": bool(getattr(settings, "translation_cache_enabled", True)),
        "timeout": safe_timeout,
        "max_retries": safe_retries,
    }


def _read_cached_keyword(db: Any, keyword: str) -> Optional[str]:
    """同一英文搜索词的受控翻译结果复用(只缓存公开搜索词,不含用户聊天内容)。"""
    record = translation_cache_service.get_cached_translation(
        db,
        PROVIDER_DEEPSEEK,
        keyword,
        QUERY_CACHE_FIELD,
        QUERY_CACHE_TARGET_LOCALE,
        translation_cache_service.make_source_hash(keyword),
        TRANSLATION_VERSION,
    )
    if record is None:
        return None
    return sanitize_translation_text(record.translation_text, MAX_QUERY_LENGTH)


def _save_cached_keyword(db: Any, keyword: str, chinese_keyword: str) -> None:
    translation_cache_service.save_translation(
        db,
        PROVIDER_DEEPSEEK,
        keyword,
        QUERY_CACHE_FIELD,
        QUERY_CACHE_TARGET_LOCALE,
        chinese_keyword,
        "model",
        TRANSLATION_VERSION,
        source_hash=translation_cache_service.make_source_hash(keyword),
    )


async def _translate_keyword(keyword: str, settings: dict[str, Any]) -> Optional[str]:
    """单次受控翻译:超时 + 有限重试;失败返回 None(由调用方给 422)。"""
    user_prompt = QUERY_TRANSLATION_USER_PROMPT_TEMPLATE.format(
        keyword=json.dumps(keyword, ensure_ascii=False)
    )
    for attempt in range(int(settings["max_retries"]) + 1):
        try:
            raw = await asyncio.wait_for(
                deepseek_client.generate_json(QUERY_TRANSLATION_SYSTEM_PROMPT, user_prompt),
                timeout=float(settings["timeout"]),
            )
        except Exception as exc:  # noqa: BLE001 - 搜索词翻译失败只能降级成受控错误
            logger.warning(
                "query translation failed (attempt %s, %s)", attempt + 1, type(exc).__name__
            )
            continue

        candidate = parse_query_keyword(raw)
        if candidate and contains_chinese(candidate):
            return candidate
    return None


async def resolve_search_keyword(
    db: Any, keyword: Any, locale: str = DEFAULT_LOCALE
) -> str:
    """把用户输入解析成**高德可用的中文关键词**;解析不出来就抛 422 受控错误。

    `locale` 只用于日志语义:英文界面和中文界面都允许输入英文/中文,
    两者都必须能落到真实的中文检索词(§1.5)。
    """
    cleaned = normalize_query(keyword)
    if not cleaned:
        raise AppError(QUERY_UNRECOGNIZED)

    # 1. 经审核别名表(原样命中)
    alias = entity_localization_service.lookup_search_alias(cleaned)
    if alias:
        return alias

    # 2. 已审核实体英文名 / 别名(places / dishes)
    entity = entity_localization_service.lookup_entity_by_english(cleaned)
    if entity:
        return entity

    # 3. 输入本身含中文 -> 就是中文关键词
    if contains_chinese(cleaned):
        return cleaned

    # 4. 单次受控翻译(可缓存)
    settings = _settings_snapshot()
    if settings["cache_enabled"]:
        cached = _read_cached_keyword(db, cleaned)
        if cached:
            return cached

    translated = await _translate_keyword(cleaned, settings)
    if translated:
        if settings["cache_enabled"]:
            _save_cached_keyword(db, cleaned, translated)
        return translated

    # 5. 仍失败:绝不返回默认列表,给受控错误(§6.4)
    logger.info("query keyword unrecognized (locale=%s)", locale)
    raise AppError(QUERY_UNRECOGNIZED)
