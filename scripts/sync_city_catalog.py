#!/usr/bin/env python3
"""把前端城市目录同步到后端资源,供 city_catalog_service 使用。

任务书 §3.2 要求:
- 复用 `frontend/src/data/cities.json`,不靠 LLM 生成 adcode;
- 构建时同步到 `backend/app/data/cities.json`,并有 CI 一致性检查;
- 发布包自带资源,运行时**不依赖**前端目录存在。

用法:
    python scripts/sync_city_catalog.py          # 生成/更新后端目录
    python scripts/sync_city_catalog.py --check   # CI 模式:不一致则非 0 退出
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend" / "src" / "data" / "cities.json"
TARGET = ROOT / "backend" / "app" / "data" / "cities.json"

# 后端目录需要的字段(顺序固定,便于 diff)
FIELDS = (
    "city_name",
    "province",
    "adcode",
    "citycode",
    "pinyin",
    "city_name_en",
    "province_en",
    "pinyin_initials",
    "aliases_en",
)


def build_catalog() -> list[dict]:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit(f"源目录不是数组: {SOURCE}")

    catalog: list[dict] = []
    seen: set[str] = set()
    problems: list[str] = []

    for entry in raw:
        if not isinstance(entry, dict):
            problems.append(f"非对象条目: {entry!r}")
            continue

        adcode = str(entry.get("adcode") or "").strip()
        city_name = str(entry.get("city_name") or "").strip()

        if not adcode or not city_name:
            problems.append(f"缺 adcode 或 city_name: {entry!r}")
            continue
        if adcode in seen:
            problems.append(f"adcode 重复: {adcode} ({city_name})")
            continue
        seen.add(adcode)

        record = {
            "city_name": city_name,
            "province": str(entry.get("province") or "").strip(),
            "adcode": adcode,
            "citycode": str(entry.get("citycode") or "").strip(),
            "pinyin": str(entry.get("pinyin") or "").strip(),
            "city_name_en": str(entry.get("city_name_en") or "").strip(),
            "province_en": str(entry.get("province_en") or "").strip(),
            "pinyin_initials": str(entry.get("pinyin_initials") or "").strip(),
            "aliases_en": [
                str(a).strip()
                for a in (entry.get("aliases_en") or [])
                if str(a).strip()
            ],
        }

        missing = [f for f in ("city_name", "adcode") if not record[f]]
        if missing:
            problems.append(f"{city_name or adcode} 缺必填字段: {missing}")

        catalog.append(record)

    if problems:
        print("源目录存在问题:", file=sys.stderr)
        for p in problems[:20]:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(1)

    if not catalog:
        raise SystemExit("同步结果为空,拒绝写入")

    return catalog


def main() -> int:
    check_only = "--check" in sys.argv[1:]

    if not SOURCE.exists():
        print(f"源目录不存在: {SOURCE}", file=sys.stderr)
        return 1

    catalog = build_catalog()
    payload = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"

    if check_only:
        if not TARGET.exists():
            print(f"[check] 后端目录缺失: {TARGET}", file=sys.stderr)
            return 1
        if TARGET.read_text(encoding="utf-8") != payload:
            print(
                "[check] 后端城市目录与前端不一致,请运行 "
                "`python scripts/sync_city_catalog.py` 后提交",
                file=sys.stderr,
            )
            return 1
        print(f"[check] 一致({len(catalog)} 个城市)")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(payload, encoding="utf-8")

    provinces = sorted({c["province"] for c in catalog})
    print(f"已同步 {len(catalog)} 个城市 / {len(provinces)} 个省级单位 -> {TARGET}")
    print(f"字段: {', '.join(FIELDS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
