"""v0.3.1 本地化相关 Schema:locale / 字段来源枚举 + 翻译响应校验(契约 §2 / §6.3)。

这里的两个职责:
1. 定义跨端约定的类型别名(`Locale`、`FieldSource`)与长度上限;
2. **校验并清洗**模型返回的翻译结果 —— 只信 id 一一对应、只收字符串、
   去控制字符与 HTML、限制长度,`null` 绝不变成编造的值。

清洗函数单独暴露(sanitize_translation_text),服务和测试都复用同一份规则。
"""

import re
from typing import Any, Literal, Mapping, Optional

from pydantic import BaseModel, Field

#: 唯一允许的两个语言(契约 §1)
Locale = Literal["zh-CN", "en-US"]

#: 译文可信度(契约 §2:verified > model > transliterated > fallback)
FieldSource = Literal["verified", "model", "transliterated", "fallback"]

FIELD_SOURCE_VERIFIED: FieldSource = "verified"
FIELD_SOURCE_MODEL: FieldSource = "model"
FIELD_SOURCE_TRANSLITERATED: FieldSource = "transliterated"
FIELD_SOURCE_FALLBACK: FieldSource = "fallback"

FIELD_SOURCES: tuple[str, ...] = (
    FIELD_SOURCE_VERIFIED,
    FIELD_SOURCE_MODEL,
    FIELD_SOURCE_TRANSLITERATED,
    FIELD_SOURCE_FALLBACK,
)

#: 译文长度上限:防止模型返回整段解释把卡片撑坏
MAX_NAME_LENGTH = 120
MAX_ADDRESS_LENGTH = 300
MAX_DESCRIPTION_LENGTH = 600
MAX_TAG_LENGTH = 60

#: 单值字段 -> 长度上限
FIELD_MAX_LENGTHS: dict[str, int] = {
    "name": MAX_NAME_LENGTH,
    "address": MAX_ADDRESS_LENGTH,
    "description": MAX_DESCRIPTION_LENGTH,
    "keyword": MAX_NAME_LENGTH,
}

_HTML_TAG_RE = re.compile(r"<[^<>]{0,300}>")
#: C0 控制字符与 DEL(保留 \t \n \r,后面统一折叠成空格)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")
#: 模型偶尔会返回"未翻译"的占位,一律当成缺失
_EMPTY_PLACEHOLDERS = {"", "-", "n/a", "na", "none", "null", "无", "暂无", "暂无信息"}


def exclude_when_none(value: Any) -> bool:
    """`Field(exclude_if=...)`:None 的可选双语字段不参与序列化。

    这样不带 locale 的老客户端拿到的响应与 v0.3 完全一致(真正向后兼容),
    而 `name_en=null` / `name_en_source="fallback"` 这种"明确缺失"的语义仍然保留。
    """
    return value is None


def is_valid_field_source(value: Any) -> bool:
    """是否是契约允许的四个来源之一。"""
    return isinstance(value, str) and value in FIELD_SOURCES


def sanitize_translation_text(value: Any, max_length: int = MAX_NAME_LENGTH) -> Optional[str]:
    """清洗模型返回的译文:去 HTML / 控制字符、折叠空白、截断长度。

    返回 None 表示"没有可用译文" —— 调用方必须保持字段为 None,绝不编造。
    """
    if not isinstance(value, str):
        return None
    text = _HTML_TAG_RE.sub(" ", value)
    text = _CONTROL_CHAR_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    # 去掉模型常见的包裹引号
    text = text.strip("\"'“”‘’").strip()
    if not text or text.lower() in _EMPTY_PLACEHOLDERS:
        return None
    if max_length > 0 and len(text) > max_length:
        text = text[:max_length].strip()
    return text or None


def sanitize_translation_list(values: Any, max_length: int = MAX_TAG_LENGTH) -> list[str]:
    """清洗字符串数组(标签),保留顺序去重,空值丢弃。"""
    if not isinstance(values, (list, tuple)):
        return []
    cleaned: list[str] = []
    for value in values:
        item = sanitize_translation_text(value, max_length)
        if item and item not in cleaned:
            cleaned.append(item)
    return cleaned


def max_length_for_field(field_name: str) -> int:
    """字段名 -> 长度上限(未知字段按 name 处理)。"""
    return FIELD_MAX_LENGTHS.get(str(field_name), MAX_NAME_LENGTH)


class TranslationItem(BaseModel):
    """单条译文;`id` 必须与请求一一对应(多余条目由调用方丢弃)。

    同时兼容几种模型可能给的字段名:`text` / `translation` / `name_en` 等。
    """

    id: str
    text: Optional[str] = None
    name_en: Optional[str] = None
    address_en: Optional[str] = None
    description_en: Optional[str] = None
    tags_en: Optional[list[str]] = None

    def best_text(self) -> Optional[str]:
        """按优先级取这条记录里唯一的译文文本。"""
        for candidate in (self.text, self.name_en, self.address_en, self.description_en):
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        return None


class TranslationPayload(BaseModel):
    """结构化翻译响应:`{"items": [...]}`(也容忍裸数组,见 parse_translation_items)。"""

    items: list[TranslationItem] = Field(default_factory=list)


class QueryTranslationPayload(BaseModel):
    """英文搜索词 -> 中文搜索词的受控翻译响应(契约 §8 第 4 步)。"""

    keyword_zh: Optional[str] = None


_ITEM_LIST_KEYS = ("items", "translations", "results", "data", "list")
_TEXT_KEYS = (
    "text",
    "translation",
    "translation_text",
    "text_en",
    "name_en",
    "address_en",
    "description_en",
    "keyword",
    "keyword_zh",
    "zh",
)
_QUERY_KEY_ORDER = ("keyword_zh", "keyword", "zh", "text", "translation")


def _extract_item_list(payload: Any) -> list[Any]:
    """从 `{"items": [...]}` / 裸数组 / 单个对象里取出条目列表。"""
    if isinstance(payload, (list, tuple)):
        return list(payload)
    if isinstance(payload, Mapping):
        for key in _ITEM_LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, (list, tuple)):
                return list(value)
    return []


def parse_translation_items(payload: Any) -> dict[str, Optional[str]]:
    """把模型返回解析成 `{id: 原始译文}`;格式不对就是空 dict(不抛错、不编造)。

    只保留带合法字符串 id 的条目;同一 id 重复时后出现的不覆盖先出现的。
    解析结果还要经过 `sanitize_translation_text` 才真正可用。
    """
    parsed: dict[str, Optional[str]] = {}
    for raw_item in _extract_item_list(payload):
        if not isinstance(raw_item, Mapping):
            continue
        raw_id = raw_item.get("id") or raw_item.get("key") or raw_item.get("poi_id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            continue
        item_id = raw_id.strip()
        if item_id in parsed:
            continue
        text: Optional[str] = None
        for key in _TEXT_KEYS:
            candidate = raw_item.get(key)
            if isinstance(candidate, str) and candidate.strip():
                text = candidate
                break
        parsed[item_id] = text
    return parsed


def parse_query_keyword(payload: Any) -> Optional[str]:
    """从受控翻译响应里取中文关键词;取不到返回 None(调用方给 422 受控错误)。"""
    if isinstance(payload, Mapping):
        for key in _QUERY_KEY_ORDER:
            candidate = payload.get(key)
            cleaned = sanitize_translation_text(candidate, MAX_NAME_LENGTH)
            if cleaned:
                return cleaned
        for item in _extract_item_list(payload):
            if isinstance(item, Mapping):
                for key in _QUERY_KEY_ORDER:
                    cleaned = sanitize_translation_text(item.get(key), MAX_NAME_LENGTH)
                    if cleaned:
                        return cleaned
        return None
    if isinstance(payload, str):
        return sanitize_translation_text(payload, MAX_NAME_LENGTH)
    for item in _extract_item_list(payload):
        if isinstance(item, Mapping):
            for key in _QUERY_KEY_ORDER:
                cleaned = sanitize_translation_text(item.get(key), MAX_NAME_LENGTH)
                if cleaned:
                    return cleaned
    return None
