"""实体双语化服务(契约 §2 / §6.2 / §6.3)。

可信优先级(严格按此顺序,绝不跳级伪造):
1. 人工审核词典 `app/data/localization_lexicon.json` -> `verified`;
2. `entity_translations` 缓存(按原文 SHA-256 命中) -> 原样沿用来源等级;
3. DeepSeek 结构化批量翻译(每批 ≤ translation_batch_size,有超时/有限重试) -> `model`;
4. 都拿不到 -> `name_en = None` + `name_en_source = "fallback"`(绝不编造,§13.1)。

红线(任何时候都不许违反):
- `poi_id` / `location` / `rating` / `cost` / `telephone` / `photos` / `adcode` / 分页字段
  不参与翻译、不被改写;
- 输入输出 id 一一对应:多出来的条目丢弃,缺失的字段保持 None;
- 译文去 HTML / 控制字符并截断长度;
- 词典文件缺失时一切查询返回空(dict),绝不崩。
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from app.core.config import get_settings
from app.core.locale import LOCALE_EN_US
from app.models.entity_translation import (
    PROVIDER_AMAP,
    PROVIDER_DEEPSEEK,
    TRANSLATION_VERSION,
)
from app.schemas.attraction import AttractionDetail, AttractionSummary
from app.schemas.food import FeaturedFoodItem, RestaurantDetail, RestaurantSummary
from app.schemas.localization import (
    FIELD_SOURCE_FALLBACK,
    FIELD_SOURCE_MODEL,
    FIELD_SOURCE_VERIFIED,
    MAX_NAME_LENGTH,
    is_valid_field_source,
    max_length_for_field,
    parse_translation_items,
    sanitize_translation_text,
)
from app.services import deepseek_client, translation_cache_service

logger = logging.getLogger(__name__)

#: 词典位置:`backend/app/data/localization_lexicon.json`(契约 §8)。
#: 由数据工作流并行维护;文件不存在时所有查询返回空,绝不抛错。
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_LEXICON_PATH = DATA_DIR / "localization_lexicon.json"
#: 兼容另一种存放位置(backend/data/...),只在默认路径不存在时才尝试
FALLBACK_LEXICON_PATHS: tuple[Path, ...] = (
    Path(__file__).resolve().parents[2] / "data" / "localization_lexicon.json",
)
#: 测试 / 部署可以覆盖;一旦被覆盖就**只**用覆盖后的路径,保证行为可预期
LEXICON_PATH: Path = DEFAULT_LEXICON_PATH

DEFAULT_TRANSLATION_BATCH_SIZE = 10
DEFAULT_TRANSLATION_TIMEOUT_SECONDS = 20.0
DEFAULT_TRANSLATION_MAX_RETRIES = 1

#: 词典里可能出现的分区名
LEXICON_SEARCH_ALIASES = "search_aliases"
LEXICON_PLACES = "places"
LEXICON_DISHES = "dishes"
LEXICON_CITIES = "cities"
LEXICON_PROVINCES = "provinces"
LEXICON_WEATHER_CODES = "weather_codes"
LEXICON_TAG_EN = "tag_en"

TRANSLATION_SYSTEM_PROMPT = (
    "你是一名严谨的中英翻译引擎,负责把中国旅游平台的公开实体信息翻译成英文。"
    "你只输出 JSON,不输出任何解释、Markdown 或代码块。"
)

TRANSLATION_USER_PROMPT_TEMPLATE = """把下面这些中国旅游实体字段翻译成自然、规范、简洁的英文。

硬性要求:
1. 只输出一个 JSON 对象:{{"items": [{{"id": "输入的 id", "text": "英文译文"}}]}};
2. id 必须与输入条目一一对应,不增加、不减少、不改写 id;
3. text 只放译文本身,不要解释、不要拼音、不要引号,不要残留中文;
4. 地址必须保留门牌号 / 楼层 / 路名的数字与顺序,不得改动任何数字;
5. 专有名词(景点、餐厅、品牌)使用常见英文名,不确定时给最保守的直译;
6. 确实无法翻译时 text 输出空字符串,绝不编造事实。

输入:
{payload}"""

_ITEM_ID_SEPARATOR = "|"

_LEXICON_CACHE: dict[str, Any] = {"path": None, "stamp": None, "data": {}}


# --------------------------------------------------------------------------- #
# 词典加载:文件缺失 / 损坏都只能得到空 dict
# --------------------------------------------------------------------------- #
def _clean_str(value: Any) -> Optional[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _normalize_key(value: Any) -> str:
    """匹配用归一化:大小写、空白、两侧引号都不敏感。"""
    text = _clean_str(value) or ""
    return re.sub(r"\s+", " ", text.strip().strip("\"'“”‘’")).lower()


def _plural_variants(normalized: str) -> set[str]:
    """英文单复数兜底:`museums` <-> `museum`、`ancient towns` <-> `ancient town`。"""
    variants: set[str] = set()
    if not normalized:
        return variants
    if normalized.endswith("ies") and len(normalized) > 3:
        variants.add(normalized[:-3] + "y")
    if normalized.endswith("es") and len(normalized) > 2:
        variants.add(normalized[:-2])
    if normalized.endswith("s") and not normalized.endswith("ss"):
        variants.add(normalized[:-1])
    return variants


def _lexicon_candidates() -> tuple[Path, ...]:
    """当前要读的词典路径(覆盖时只看覆盖值,避免测试被真实文件干扰)。"""
    if LEXICON_PATH != DEFAULT_LEXICON_PATH:
        return (LEXICON_PATH,)
    return (DEFAULT_LEXICON_PATH, *FALLBACK_LEXICON_PATHS)


def _file_stamp(path: Path) -> Optional[tuple[int, int]]:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def reset_lexicon_cache() -> None:
    """清空词典缓存(测试换词典文件后必须调用)。"""
    _LEXICON_CACHE.update({"path": None, "stamp": None, "data": {}})


def load_lexicon() -> dict[str, Any]:
    """读取并缓存词典;文件不存在 / 不是 JSON 对象 -> 空 dict(绝不抛错)。"""
    for path in _lexicon_candidates():
        stamp = _file_stamp(path)
        if stamp is None:
            continue
        if _LEXICON_CACHE.get("path") == str(path) and _LEXICON_CACHE.get("stamp") == stamp:
            return _LEXICON_CACHE["data"]

        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            logger.warning("localization lexicon unreadable: %s", path.name)
            continue

        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            logger.warning("localization lexicon is not valid json: %s", path.name)
            parsed = {}
        data = dict(parsed) if isinstance(parsed, Mapping) else {}

        _LEXICON_CACHE.update({"path": str(path), "stamp": stamp, "data": data})
        return data

    # 一个候选文件都不存在:缓存"空词典",调用方继续走降级路径
    _LEXICON_CACHE.update({"path": str(LEXICON_PATH), "stamp": None, "data": {}})
    return {}


def get_lexicon_section(section: str) -> Mapping[str, Any]:
    """取某个分区;缺失或类型不对一律返回空 dict。"""
    data = load_lexicon()
    value = data.get(section)
    return value if isinstance(value, Mapping) else {}


def _entry_to_translation(entry: Any) -> Optional[tuple[str, str]]:
    """词典条目 -> (英文, 来源);支持字符串与 {"en": ..., "source": ...} 两种写法。"""
    if isinstance(entry, str):
        text = sanitize_translation_text(entry, MAX_NAME_LENGTH)
        return (text, FIELD_SOURCE_VERIFIED) if text else None
    if isinstance(entry, Mapping):
        text = sanitize_translation_text(
            entry.get("en") or entry.get("english") or entry.get("name_en"), MAX_NAME_LENGTH
        )
        if not text:
            return None
        source = entry.get("source")
        return (text, source if is_valid_field_source(source) else FIELD_SOURCE_VERIFIED)
    return None


def _section_entry(section_name: str, key: str) -> Optional[tuple[str, str]]:
    """按中文原名查某个分区(大小写 / 空白不敏感)。"""
    section = get_lexicon_section(section_name)
    if not section:
        return None

    entry = section.get(key)
    if entry is None:
        normalized = _normalize_key(key)
        for raw_key, raw_entry in section.items():
            if isinstance(raw_key, str) and _normalize_key(raw_key) == normalized:
                entry = raw_entry
                break
    return _entry_to_translation(entry)


def lookup_verified_name(name_zh: Any) -> Optional[tuple[str, str]]:
    """中文实体名 -> 经审核英文名(places / dishes / cities 三个分区)。"""
    text = _clean_str(name_zh)
    if not text:
        return None
    for section_name in (LEXICON_PLACES, LEXICON_DISHES, LEXICON_CITIES):
        found = _section_entry(section_name, text)
        if found:
            return found
    return None


def lookup_city_translation(name_zh: Any) -> Optional[str]:
    """中文城市名 -> 英文名(词典缺失时返回 None,由调用方决定降级展示)。"""
    found = _section_entry(LEXICON_CITIES, _clean_str(name_zh) or "")
    return found[0] if found else None


def lookup_tag_translation(tag: Any) -> Optional[str]:
    """中文标签 -> 英文标签(只认词典,不调模型)。"""
    text = _clean_str(tag)
    if not text:
        return None
    section = get_lexicon_section(LEXICON_TAG_EN)
    if not section:
        return None

    entry = section.get(text)
    if entry is None:
        normalized = _normalize_key(text)
        for raw_key, raw_entry in section.items():
            if isinstance(raw_key, str) and _normalize_key(raw_key) == normalized:
                entry = raw_entry
                break
    if isinstance(entry, str):
        return sanitize_translation_text(entry, max_length_for_field("name"))
    return _entry_to_translation(entry)[0] if _entry_to_translation(entry) else None


def lookup_search_alias(keyword: Any) -> Optional[str]:
    """英文搜索词 -> 经验证中文关键词(契约 §8 第 1 步)。"""
    text = _clean_str(keyword)
    if not text:
        return None
    section = get_lexicon_section(LEXICON_SEARCH_ALIASES)
    if not section:
        return None

    normalized = _normalize_key(text)
    variants = {normalized} | _plural_variants(normalized)
    for raw_key, raw_value in section.items():
        if not isinstance(raw_key, str) or _normalize_key(raw_key) not in variants:
            continue
        if isinstance(raw_value, str):
            translated = raw_value
        elif isinstance(raw_value, Mapping):
            translated = raw_value.get("zh") or raw_value.get("text") or raw_value.get("keyword")
        else:
            translated = None
        cleaned = sanitize_translation_text(translated, MAX_NAME_LENGTH)
        if cleaned:
            return cleaned
    return None


def _entry_english_names(entry: Any) -> list[str]:
    """词典条目里的英文名与别名(用于英文 -> 中文反查)。"""
    if isinstance(entry, str):
        return [entry]
    if not isinstance(entry, Mapping):
        return []

    names: list[str] = []
    for key in ("en", "english", "name_en"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            names.append(value)
    for key in ("aliases", "aliases_en", "alias"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            names.append(value)
        elif isinstance(value, (list, tuple)):
            names.extend(item for item in value if isinstance(item, str) and item.strip())
    return names


def lookup_entity_by_english(keyword: Any) -> Optional[str]:
    """英文名 / 别名 -> 中文原名(契约 §8 第 2 步,只认已审核词典)。"""
    text = _clean_str(keyword)
    if not text:
        return None

    normalized = _normalize_key(text)
    variants = {normalized} | _plural_variants(normalized)
    for section_name in (LEXICON_PLACES, LEXICON_DISHES, LEXICON_CITIES):
        section = get_lexicon_section(section_name)
        for raw_key, raw_entry in section.items():
            if not isinstance(raw_key, str):
                continue
            for english_name in _entry_english_names(raw_entry):
                if _normalize_key(english_name) in variants:
                    return sanitize_translation_text(raw_key, MAX_NAME_LENGTH)
    return None


# --------------------------------------------------------------------------- #
# 批量结构化翻译(DeepSeek generate_json,唯一允许的模型翻译通道)
# --------------------------------------------------------------------------- #
def _settings_snapshot() -> dict[str, Any]:
    """读翻译相关配置;用 getattr 兜底,方便测试注入最小 Settings 替身。"""
    settings = get_settings()
    batch_size = getattr(settings, "translation_batch_size", DEFAULT_TRANSLATION_BATCH_SIZE)
    timeout = getattr(settings, "translation_timeout_seconds", DEFAULT_TRANSLATION_TIMEOUT_SECONDS)
    max_retries = getattr(settings, "translation_max_retries", DEFAULT_TRANSLATION_MAX_RETRIES)
    try:
        safe_batch = max(int(batch_size or DEFAULT_TRANSLATION_BATCH_SIZE), 1)
    except (TypeError, ValueError):
        safe_batch = DEFAULT_TRANSLATION_BATCH_SIZE
    try:
        safe_timeout = max(float(timeout or DEFAULT_TRANSLATION_TIMEOUT_SECONDS), 0.1)
    except (TypeError, ValueError):
        safe_timeout = DEFAULT_TRANSLATION_TIMEOUT_SECONDS
    try:
        safe_retries = max(int(max_retries or 0), 0)
    except (TypeError, ValueError):
        safe_retries = DEFAULT_TRANSLATION_MAX_RETRIES
    return {
        "cache_enabled": bool(getattr(settings, "translation_cache_enabled", True)),
        "batch_size": safe_batch,
        "timeout": safe_timeout,
        "max_retries": safe_retries,
    }


def _output_keys(field_name: str) -> tuple[str, Optional[str]]:
    """字段名 -> (译文字段, 来源字段);description 没有来源字段(契约 §2)。"""
    text_key = f"{field_name}_en"
    source_key = None if field_name == "description" else f"{field_name}_en_source"
    return text_key, source_key


def _item_id(entity_key: str, field_name: str) -> str:
    """请求/响应的条目 id:实体键 + 字段名,保证一一对应且可回填。"""
    return f"{entity_key}{_ITEM_ID_SEPARATOR}{field_name}"


def _record_key(record: Mapping[str, Any]) -> Optional[str]:
    for name in ("entity_key", "poi_id", "id"):
        key = _clean_str(record.get(name))
        if key:
            return key
    return None


def _read_cache(
    db: Any,
    provider: str,
    entity_key: str,
    field_name: str,
    target_locale: str,
    source_text: str,
    settings: Mapping[str, Any],
) -> Optional[tuple[str, str]]:
    if not settings["cache_enabled"]:
        return None
    record = translation_cache_service.get_cached_translation(
        db,
        provider,
        entity_key,
        field_name,
        target_locale,
        translation_cache_service.make_source_hash(source_text),
        TRANSLATION_VERSION,
    )
    if record is None:
        return None
    text = sanitize_translation_text(record.translation_text, max_length_for_field(field_name))
    if not text:
        return None
    source = record.translation_source
    return (text, source if is_valid_field_source(source) else FIELD_SOURCE_MODEL)


async def _request_translation_batch(
    chunk: Sequence[tuple[str, str, str]],
    target_locale: str,
    settings: Mapping[str, Any],
) -> dict[str, Optional[str]]:
    """发一批结构化翻译请求;超时 / 失败按 translation_max_retries 有限重试。

    只走 `deepseek_client.generate_json()`(绝不引入第二个翻译供应商)。
    """
    if not chunk:
        return {}

    payload = {
        "items": [
            {"id": _item_id(key, field_name), "field": field_name, "text": source_text}
            for key, field_name, source_text in chunk
        ]
    }
    user_prompt = TRANSLATION_USER_PROMPT_TEMPLATE.format(
        payload=json.dumps(payload, ensure_ascii=False)
    )

    for attempt in range(int(settings["max_retries"]) + 1):
        try:
            raw = await asyncio.wait_for(
                deepseek_client.generate_json(TRANSLATION_SYSTEM_PROMPT, user_prompt),
                timeout=float(settings["timeout"]),
            )
        except Exception as exc:  # noqa: BLE001 - 翻译失败只能降级,不能 500
            logger.warning(
                "translation batch failed (attempt %s, %s)", attempt + 1, type(exc).__name__
            )
            continue

        parsed = parse_translation_items(raw)
        if parsed:
            return parsed

    return {}


async def _translate_pending(
    db: Any,
    provider: str,
    target_locale: str,
    pending: Sequence[tuple[str, str, str]],
    settings: Mapping[str, Any],
) -> dict[tuple[str, str], str]:
    """把待翻译条目按 batch_size 切批翻译,成功的结果顺手写缓存。"""
    results: dict[tuple[str, str], str] = {}
    batch_size = int(settings["batch_size"])

    for start in range(0, len(pending), batch_size):
        chunk = list(pending[start : start + batch_size])
        parsed = await _request_translation_batch(chunk, target_locale, settings)
        if not parsed:
            continue

        for entity_key, field_name, source_text in chunk:
            cleaned = sanitize_translation_text(
                parsed.get(_item_id(entity_key, field_name)), max_length_for_field(field_name)
            )
            # 模型没给 / 给了空串 -> 保持缺失,绝不编造
            if not cleaned:
                continue
            results[(entity_key, field_name)] = cleaned
            if settings["cache_enabled"]:
                translation_cache_service.save_translation(
                    db,
                    provider,
                    entity_key,
                    field_name,
                    target_locale,
                    cleaned,
                    FIELD_SOURCE_MODEL,
                    TRANSLATION_VERSION,
                    source_hash=translation_cache_service.make_source_hash(source_text),
                )

    return results


# --------------------------------------------------------------------------- #
# 契约要求的三个核心入口
# --------------------------------------------------------------------------- #
async def localize_poi_batch(
    db: Any,
    records: Optional[Sequence[Mapping[str, Any]]],
    target_locale: str = LOCALE_EN_US,
    fields: Sequence[str] = ("name",),
    provider: str = PROVIDER_AMAP,
) -> dict[str, dict[str, Any]]:
    """批量把 POI 记录的双语字段算出来。

    入参 `records` 是 `[{"poi_id"/"entity_key": ..., "name": ..., "address": ...}]`;
    返回 `{entity_key: {"name_en": ..., "name_en_source": ...}}`。

    - 非英文 locale 直接返回空 dict(中文模式不产生任何译文,响应与 v0.3 一致);
    - 找不到可信英文名时只写 `*_en_source = "fallback"`,不写任何假译文。
    """
    if target_locale != LOCALE_EN_US or not records:
        return {}

    normalized: list[tuple[str, Mapping[str, Any]]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        key = _record_key(record)
        if key:
            normalized.append((key, record))
    if not normalized:
        return {}

    settings = _settings_snapshot()
    localized: dict[str, dict[str, Any]] = {key: {} for key, _ in normalized}
    pending: list[tuple[str, str, str]] = []
    pending_keys: set[tuple[str, str]] = set()
    attempted: set[tuple[str, str]] = set()

    for key, record in normalized:
        for raw_field in fields:
            field_name = str(raw_field)
            source_text = _clean_str(record.get(field_name))
            if not source_text:
                continue
            # 同一 (实体, 字段) 在批次里只请求一次(输入去重,§6.3)
            if (key, field_name) in attempted:
                continue
            attempted.add((key, field_name))

            text_key, source_key = _output_keys(field_name)
            verified = lookup_verified_name(source_text) if field_name == "name" else None
            if verified:
                localized[key][text_key] = verified[0]
                if source_key:
                    localized[key][source_key] = verified[1]
                continue

            cached = _read_cache(db, provider, key, field_name, target_locale, source_text, settings)
            if cached:
                localized[key][text_key] = cached[0]
                if source_key:
                    localized[key][source_key] = cached[1]
                continue

            if (key, field_name) not in pending_keys:
                pending_keys.add((key, field_name))
                pending.append((key, field_name, source_text))

    if pending:
        translated = await _translate_pending(db, provider, target_locale, pending, settings)
        for (key, field_name), text in translated.items():
            text_key, source_key = _output_keys(field_name)
            localized.setdefault(key, {})[text_key] = text
            if source_key:
                localized[key][source_key] = FIELD_SOURCE_MODEL

    # 有原文但拿不到可信英文:显式标 fallback(译文字段保持 None,不编造)
    for key, field_name in attempted:
        text_key, source_key = _output_keys(field_name)
        if source_key and text_key not in localized.get(key, {}):
            localized.setdefault(key, {})[source_key] = FIELD_SOURCE_FALLBACK

    return localized


async def localize_address(
    db: Any,
    address: Any,
    entity_key: Any = None,
    target_locale: str = LOCALE_EN_US,
    provider: str = PROVIDER_AMAP,
) -> dict[str, Any]:
    """单条地址双语化:返回 `{"address_en": ..., "address_en_source": ...}`。

    没有 entity_key 时用地址哈希兜底(仍然只缓存公开地址文本)。
    """
    source = _clean_str(address)
    if not source or target_locale != LOCALE_EN_US:
        return {}

    key = _clean_str(entity_key) or f"address:{translation_cache_service.make_source_hash(source)[:16]}"
    localized = await localize_poi_batch(
        db, [{"entity_key": key, "address": source}], target_locale, ("address",), provider
    )
    return localized.get(key) or {}


async def localize_food_batch(
    db: Any,
    foods: Optional[Sequence[Mapping[str, Any]]],
    target_locale: str = LOCALE_EN_US,
) -> dict[str, dict[str, Any]]:
    """代表美食双语化:菜名 + 介绍。

    返回 `{dish:<中文菜名>: {"name_en": ..., "description_en": ...}}`;
    菜名先查词典(麻婆豆腐 -> Mapo Tofu,verified),再走缓存 / 批量模型翻译。
    """
    if target_locale != LOCALE_EN_US or not foods:
        return {}

    records: list[dict[str, Any]] = []
    for food in foods:
        if not isinstance(food, Mapping):
            continue
        name = _clean_str(food.get("name")) or _clean_str(food.get("name_zh"))
        if not name:
            continue
        records.append(
            {
                "entity_key": food_cache_key(name),
                "name": name,
                "description": _clean_str(food.get("description")),
            }
        )
    if not records:
        return {}

    return await localize_poi_batch(
        db, records, target_locale, ("name", "description"), PROVIDER_DEEPSEEK
    )


def food_cache_key(name: Any) -> str:
    """菜品 canonical key:`dish:<中文菜名>`(菜名本身不会跨语言改变)。"""
    return f"dish:{_clean_str(name) or ''}"


# --------------------------------------------------------------------------- #
# 面向具体响应模型的便捷封装(服务层与 Agent 工具共用,避免逻辑重复)
# --------------------------------------------------------------------------- #
def _merge(model: Any, update: Optional[Mapping[str, Any]]) -> Any:
    if not update:
        return model
    return model.model_copy(update=dict(update))


def localize_tags(tags: Optional[Sequence[str]]) -> Optional[list[str]]:
    """标签双语化:词典里**全部**命中才返回英文列表,否则 None(不混排中英)。"""
    values = [tag for tag in (tags or []) if isinstance(tag, str) and tag.strip()]
    if not values:
        return None
    translated: list[str] = []
    for tag in values:
        item = lookup_tag_translation(tag)
        if not item:
            return None
        if item not in translated:
            translated.append(item)
    return translated or None


async def localize_attraction_summaries(
    db: Any,
    items: Optional[Sequence[AttractionSummary]],
    target_locale: str,
) -> list[AttractionSummary]:
    """景点列表卡片:只补 name_en / name_en_source。"""
    summaries = list(items or [])
    if target_locale != LOCALE_EN_US or not summaries:
        return summaries

    try:
        records = [{"entity_key": item.poi_id, "name": item.name} for item in summaries]
        localized = await localize_poi_batch(db, records, target_locale, ("name",), PROVIDER_AMAP)
    except Exception:  # noqa: BLE001 - 双语化失败必须降级成中文,不能整页 500
        logger.warning("attraction summary localization failed")
        return summaries
    return [_merge(item, localized.get(item.poi_id)) for item in summaries]


async def localize_attraction_detail(
    db: Any, detail: AttractionDetail, target_locale: str
) -> AttractionDetail:
    """景点详情:name_en / address_en / tags_en(poi_id、location、cost 等一律不动)。"""
    if target_locale != LOCALE_EN_US or detail is None:
        return detail

    try:
        records = [{"entity_key": detail.poi_id, "name": detail.name, "address": detail.address}]
        localized = await localize_poi_batch(db, records, target_locale, ("name", "address"), PROVIDER_AMAP)
    except Exception:  # noqa: BLE001
        logger.warning("attraction detail localization failed")
        return detail

    update = dict(localized.get(detail.poi_id) or {})
    tags_en = localize_tags(detail.tags)
    if tags_en:
        update["tags_en"] = tags_en
    return _merge(detail, update)


async def localize_restaurant_summaries(
    db: Any,
    items: Optional[Sequence[RestaurantSummary]],
    target_locale: str,
) -> list[RestaurantSummary]:
    """餐厅列表:只补 name_en / name_en_source。"""
    summaries = list(items or [])
    if target_locale != LOCALE_EN_US or not summaries:
        return summaries

    try:
        records = [{"entity_key": item.poi_id, "name": item.name} for item in summaries]
        localized = await localize_poi_batch(db, records, target_locale, ("name",), PROVIDER_AMAP)
    except Exception:  # noqa: BLE001
        logger.warning("restaurant summary localization failed")
        return summaries
    return [_merge(item, localized.get(item.poi_id)) for item in summaries]


async def localize_restaurant_detail(
    db: Any, detail: RestaurantDetail, target_locale: str
) -> RestaurantDetail:
    """餐厅详情:name_en / address_en;电话、价格、评分、照片保持原值。"""
    if target_locale != LOCALE_EN_US or detail is None:
        return detail

    try:
        records = [{"entity_key": detail.poi_id, "name": detail.name, "address": detail.address}]
        localized = await localize_poi_batch(db, records, target_locale, ("name", "address"), PROVIDER_AMAP)
    except Exception:  # noqa: BLE001
        logger.warning("restaurant detail localization failed")
        return detail
    return _merge(detail, localized.get(detail.poi_id))


async def localize_featured_foods(
    db: Any,
    items: Optional[Sequence[FeaturedFoodItem]],
    target_locale: str,
) -> list[FeaturedFoodItem]:
    """代表美食 + 嵌套代表餐厅的双语化(一次批量,不给每张卡片单独发请求)。"""
    foods = list(items or [])
    if target_locale != LOCALE_EN_US or not foods:
        return foods

    restaurants = [
        restaurant
        for food in foods
        for restaurant in (food.representative_restaurants or [])
        if isinstance(restaurant, RestaurantSummary)
    ]

    try:
        dish_updates = await localize_food_batch(
            db,
            [{"name": food.name, "description": food.description} for food in foods],
            target_locale,
        )
        restaurant_updates: dict[str, dict[str, Any]] = {}
        if restaurants:
            restaurant_updates = await localize_poi_batch(
                db,
                [{"entity_key": item.poi_id, "name": item.name} for item in restaurants],
                target_locale,
                ("name",),
                PROVIDER_AMAP,
            )
    except Exception:  # noqa: BLE001
        logger.warning("featured food localization failed")
        return foods

    localized: list[FeaturedFoodItem] = []
    for food in foods:
        update = dict(dish_updates.get(food_cache_key(food.name)) or {})
        nested = [
            _merge(restaurant, restaurant_updates.get(restaurant.poi_id))
            for restaurant in (food.representative_restaurants or [])
        ]
        if nested:
            update["representative_restaurants"] = nested
        localized.append(_merge(food, update))
    return localized


async def localize_text_field(
    db: Any,
    text: Any,
    field_name: str,
    entity_key: str,
    target_locale: str = LOCALE_EN_US,
    provider: str = PROVIDER_DEEPSEEK,
) -> Optional[str]:
    """单字段双语化(内部工具函数):只返回译文字符串,失败就是 None。"""
    localized = await localize_poi_batch(
        db,
        [{"entity_key": entity_key, field_name: _clean_str(text)}],
        target_locale,
        (field_name,),
        provider,
    )
    return (localized.get(entity_key) or {}).get(f"{field_name}_en")
