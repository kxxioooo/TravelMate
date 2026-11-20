"""全量城市目录解析(任务书 §3.2)。

设计要点:
- 数据来源是构建期同步好的 ``app/data/cities.json``,运行时**不依赖**前端目录存在;
  资源缺失直接抛错(fail fast),绝不静默降级成"只认已绑定城市"的旧白名单语义。
- 进程内缓存并冻结,避免每次请求重复解析 JSON。
- 这里的解析**只读**,不写库、不改会话标签。工具调用方拿到 adcode 后再去查高德。
"""

from __future__ import annotations

import json
import threading
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "cities.json"

# 城市数量上限(与 CONVERSATION_CITY_MAX_COUNT 默认值一致,由调用方传入覆盖)
DEFAULT_MAX_CITIES = 20

#: 直辖市在部分数据源里用"省级 adcode"(500000),而目录用的是"市级 adcode"(500100)。
#: 老会话/第三方数据可能存的是前者,这里做一次等价映射,避免用户一编辑就 422。
#: 只收录有确定对应关系的四个直辖市,不做模糊猜测。
LEGACY_ADCODE_ALIASES: dict[str, str] = {
    "110000": "110100",  # 北京
    "120000": "120100",  # 天津
    "310000": "310100",  # 上海
    "500000": "500100",  # 重庆
}

ResolutionStatus = Literal["resolved", "missing", "ambiguous", "unknown"]


@dataclass(frozen=True)
class CityRecord:
    """目录中的一条城市记录(不可变)。"""

    city_name: str
    province: str
    adcode: str
    citycode: str = ""
    pinyin: str = ""
    city_name_en: str = ""
    province_en: str = ""
    pinyin_initials: str = ""
    aliases_en: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        """给工具返回值/前端用的最小载荷(保留中文名 + 审核过的英文名)。"""
        return {
            "city_name": self.city_name,
            "adcode": self.adcode,
            "province": self.province,
            "city_name_en": self.city_name_en or None,
            "province_en": self.province_en or None,
        }


@dataclass(frozen=True)
class CityResolution:
    """城市解析结果。``status`` 决定上层是继续查询还是要求澄清。"""

    status: ResolutionStatus
    city: CityRecord | None = None
    candidates: tuple[CityRecord, ...] = ()
    query: str = ""
    reason: str = ""

    @property
    def resolved(self) -> bool:
        return self.status == "resolved" and self.city is not None


@dataclass(frozen=True)
class CityCatalog:
    """不可变目录索引。"""

    records: tuple[CityRecord, ...]
    by_adcode: dict[str, CityRecord] = field(default_factory=dict)
    by_key: dict[str, tuple[CityRecord, ...]] = field(default_factory=dict)

    def __len__(self) -> int:  # pragma: no cover - 便捷
        return len(self.records)


_lock = threading.Lock()
_catalog: CityCatalog | None = None


def normalize_city_query(value: Any) -> str:
    """Unicode NFKC + 去噪 + casefold。

    保留省份字样用于消歧(例如 `成都 四川`),只做空白归一化。
    """
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\u3000", " ")
    text = "".join(ch for ch in text if ch.isprintable())
    return " ".join(text.split()).strip().casefold()


def _keys_for(record: CityRecord) -> set[str]:
    """一条记录可用于检索的全部键。"""
    keys: set[str] = set()

    def add(raw: Any) -> None:
        key = normalize_city_query(raw)
        if key:
            keys.add(key)
            # 去掉撇号后再加一份,让 xian / xi'an 等价
            stripped = key.replace("'", "").replace("’", "")
            if stripped and stripped != key:
                keys.add(stripped)

    add(record.city_name)
    add(record.city_name_en)
    add(record.pinyin)
    add(record.pinyin_initials)
    for alias in record.aliases_en:
        add(alias)
    # 「成都 四川」这种带省份的写法
    if record.province:
        add(f"{record.city_name} {record.province}")
        add(f"{record.city_name}, {record.province}")
    return keys


def _build_catalog(path: Path) -> CityCatalog:
    if not path.exists():
        raise RuntimeError(
            f"城市目录资源缺失: {path}。请先运行 scripts/sync_city_catalog.py 生成后再启动。"
        )

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise RuntimeError(f"城市目录格式非法(应为非空数组): {path}")

    records: list[CityRecord] = []
    by_adcode: dict[str, CityRecord] = {}
    by_key: dict[str, list[CityRecord]] = {}

    for item in raw:
        if not isinstance(item, dict):
            raise RuntimeError(f"城市目录条目应为对象: {item!r}")

        city_name = str(item.get("city_name") or "").strip()
        adcode = str(item.get("adcode") or "").strip()
        if not city_name or not adcode:
            raise RuntimeError(f"城市目录条目缺 city_name/adcode: {item!r}")
        if adcode in by_adcode:
            raise RuntimeError(f"城市目录 adcode 重复: {adcode}")

        record = CityRecord(
            city_name=city_name,
            province=str(item.get("province") or "").strip(),
            adcode=adcode,
            citycode=str(item.get("citycode") or "").strip(),
            pinyin=str(item.get("pinyin") or "").strip(),
            city_name_en=str(item.get("city_name_en") or "").strip(),
            province_en=str(item.get("province_en") or "").strip(),
            pinyin_initials=str(item.get("pinyin_initials") or "").strip(),
            aliases_en=tuple(
                str(a).strip() for a in (item.get("aliases_en") or []) if str(a).strip()
            ),
        )

        records.append(record)
        by_adcode[adcode] = record
        for key in _keys_for(record):
            by_key.setdefault(key, []).append(record)

    frozen_by_key = {k: tuple(v) for k, v in by_key.items()}
    return CityCatalog(
        records=tuple(records),
        by_adcode=by_adcode,
        by_key=frozen_by_key,
    )


def load_city_catalog() -> CityCatalog:
    """加载并缓存目录。资源缺失或数据非法时抛错(启动即失败)。"""
    global _catalog
    if _catalog is not None:
        return _catalog
    with _lock:
        if _catalog is None:
            _catalog = _build_catalog(CATALOG_PATH)
    return _catalog


def reset_city_catalog_cache() -> None:
    """测试用:清空缓存以便重载。"""
    global _catalog
    with _lock:
        _catalog = None


def get_city_by_adcode(adcode: Any) -> CityRecord | None:
    """按 adcode 精确查找;省级直辖市代码会先映射到目录里的市级代码。"""
    key = normalize_city_query(adcode)
    if not key:
        return None
    key = LEGACY_ADCODE_ALIASES.get(key, key)
    return load_city_catalog().by_adcode.get(key)


def search_city_exact(query: Any) -> list[CityRecord]:
    """中/英/拼音/首字母/别名精确匹配;同名(如 Taizhou)返回多项。"""
    key = normalize_city_query(query)
    if not key:
        return []
    catalog = load_city_catalog()
    hits = catalog.by_key.get(key)
    if hits:
        return list(hits)
    # 带省份的写法:拆一次再试
    for sep in (" ", ","):
        if sep in key:
            head = key.split(sep)[0].strip()
            if head:
                hits = catalog.by_key.get(head)
                if hits:
                    return list(hits)
    return []


def search_city_suggestions(query: Any, limit: int = 8) -> list[CityRecord]:
    """模糊建议(仅用于提示,不能作为解析依据)。"""
    key = normalize_city_query(query)
    if not key:
        return []
    catalog = load_city_catalog()
    scored: list[tuple[int, CityRecord]] = []
    for record in catalog.records:
        haystack = {
            normalize_city_query(record.city_name),
            normalize_city_query(record.city_name_en),
            normalize_city_query(record.pinyin),
            normalize_city_query(record.pinyin_initials),
        }
        best = None
        for candidate in haystack:
            if not candidate:
                continue
            if candidate.startswith(key):
                best = 0 if best is None else min(best, 0)
            elif key in candidate:
                best = 1 if best is None else min(best, 1)
        if best is not None:
            scored.append((best, record))
    scored.sort(key=lambda pair: (pair[0], pair[1].adcode))
    return [record for _, record in scored[:limit]]


def _dedupe(records: Iterable[CityRecord]) -> list[CityRecord]:
    seen: set[str] = set()
    out: list[CityRecord] = []
    for record in records:
        if record.adcode in seen:
            continue
        seen.add(record.adcode)
        out.append(record)
    return out


def validate_and_normalize_cities(
    cities: Any,
    max_count: int = DEFAULT_MAX_CITIES,
) -> list[dict[str, str]]:
    """校验并规范化客户端提交的城市数组。

    - 只认 ``adcode``,城市中文名以目录为准(不信任客户端名称);
    - 按 adcode 去重、保序、限流;
    - 任一非法则**整组失败**(抛 ValueError),绝不默默丢弃。
    """
    if not isinstance(cities, (list, tuple)):
        raise ValueError("cities 必须是数组")

    if len(cities) > max_count:
        raise ValueError(f"最多只能绑定 {max_count} 个城市")

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()

    for raw in cities:
        if not isinstance(raw, dict):
            raise ValueError("cities 的每一项必须是对象")

        adcode = str(raw.get("adcode") or "").strip()
        if not adcode:
            raise ValueError("每个城市都必须提供 adcode")

        record = get_city_by_adcode(adcode)
        if record is None:
            raise ValueError(f"无法识别的城市代码: {adcode}")

        if record.adcode in seen:
            continue
        seen.add(record.adcode)
        normalized.append({"city_name": record.city_name, "adcode": record.adcode})

    return normalized


def resolve_city(
    query: Any,
    selected_cities: Any = None,
    *,
    max_count: int = DEFAULT_MAX_CITIES,
) -> CityResolution:
    """把一次提问里的城市意图解析成规范城市。

    规则(任务书 §3.2):
    - 显式给了城市:在全目录里解析;解析不出就返回 unknown / ambiguous,
      **绝不回退到已绑定城市**;
    - 没给城市:只有一个标签时才用它做默认;零个或多个都要求澄清;
    - 全程只读,不写库、不改标签。
    """
    catalog = load_city_catalog()
    tags = _normalize_tags(selected_cities, max_count)

    text = normalize_city_query(query)

    if text:
        hits = search_city_exact(text)
        if len(hits) == 1:
            return CityResolution(status="resolved", city=hits[0], query=text)

        if len(hits) > 1:
            return CityResolution(
                status="ambiguous",
                candidates=tuple(hits),
                query=text,
                reason="multiple_exact_matches",
            )

        # 精确没命中:用 adcode 再试一次(模型有时直接传代码)
        if text.isdigit():
            record = catalog.by_adcode.get(text)
            if record is not None:
                return CityResolution(status="resolved", city=record, query=text)

        # 同省多城之类,给出候选供上层要求澄清
        suggestions = search_city_suggestions(text)
        if suggestions:
            return CityResolution(
                status="unknown",
                candidates=tuple(suggestions),
                query=text,
                reason="no_exact_match",
            )
        return CityResolution(status="unknown", query=text, reason="not_in_catalog")

    # 没给城市
    if len(tags) == 1:
        return CityResolution(status="resolved", city=tags[0], query="", reason="default_tag")

    if len(tags) > 1:
        return CityResolution(
            status="missing",
            candidates=tuple(tags),
            reason="multiple_tags_need_clarification",
        )

    return CityResolution(status="missing", reason="no_tag")


def _normalize_tags(selected_cities: Any, max_count: int = DEFAULT_MAX_CITIES) -> list[CityRecord]:
    """把会话标签(可能是 adcode 字符串或 {adcode, city_name})解析成目录记录。"""
    if not selected_cities:
        return []

    records: list[CityRecord] = []
    for raw in list(selected_cities)[:max_count]:
        adcode = None
        if isinstance(raw, dict):
            adcode = raw.get("adcode")
        elif isinstance(raw, str):
            adcode = raw
        if not adcode:
            continue
        record = get_city_by_adcode(adcode)
        if record is not None:
            records.append(record)
    return _dedupe(records)
