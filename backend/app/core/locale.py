"""v0.3.1 中英双语 locale 解析(契约 §1)。

唯一权威规则:
- 只允许 `zh-CN` / `en-US` 两个值,默认 `zh-CN`;
- 后端解析优先级:**body 的 `locale` > `Accept-Language` 头 > `zh-CN`**;
- 非法值(例如 `fr-FR`)一律回落 `zh-CN`,绝不抛错、绝不影响业务字段。

`Accept-Language` 可能是 `en-US,en;q=0.9` / `zh-CN,zh;q=0.9,en;q=0.8` / `en` 这种列表,
所以这里按 q 值从高到低挑第一个受支持的语言,而不是只读第一段字符串。
"""

from typing import Any, Optional

LOCALE_ZH_CN = "zh-CN"
LOCALE_EN_US = "en-US"

#: 全项目唯一的两个合法 locale
SUPPORTED_LOCALES: tuple[str, ...] = (LOCALE_ZH_CN, LOCALE_EN_US)

#: 默认语言:保持面向中国旅游的产品定位(§4.1)
DEFAULT_LOCALE = LOCALE_ZH_CN

ACCEPT_LANGUAGE_HEADER = "accept-language"

#: 语言主标签 -> 受支持 locale(zh-TW / zh-Hans 等一律归到 zh-CN)
_PRIMARY_LOCALE_MAP = {
    "zh": LOCALE_ZH_CN,
    "en": LOCALE_EN_US,
}


def _split_accept_language(value: str) -> list[str]:
    """把 Accept-Language 拆成按 q 值降序的 tag 列表(同 q 保持原始顺序)。"""
    weighted: list[tuple[float, int, str]] = []
    for index, raw_part in enumerate(value.split(",")):
        part = raw_part.strip()
        if not part:
            continue
        tag, _, params = part.partition(";")
        quality = 1.0
        for param in params.split(";"):
            key, _, raw_value = param.partition("=")
            if key.strip().lower() != "q":
                continue
            try:
                quality = float(raw_value.strip())
            except (TypeError, ValueError):
                quality = 0.0
        tag = tag.strip()
        if tag:
            weighted.append((-quality, index, tag))
    weighted.sort()
    return [tag for _, _, tag in weighted]


def _match_locale_tag(tag: str) -> Optional[str]:
    """单个 tag -> 受支持 locale;不认识就返回 None(不猜)。"""
    normalized = tag.strip().lower().replace("_", "-")
    if not normalized or normalized in {"*", "und"}:
        return None
    primary = normalized.split("-")[0]
    return _PRIMARY_LOCALE_MAP.get(primary)


def normalize_locale(value: Any) -> str:
    """把任意输入归一化成 `zh-CN` / `en-US`(非法值回落默认 zh-CN)。

    接受:
    - 单个 tag:`en-US` / `en` / `EN_us` / `zh-Hans`;
    - 整条 Accept-Language:`en-US,en;q=0.9`;
    - 列表(某些客户端会重复发头);
    - None / 空串 / 非字符串 -> 默认 zh-CN。
    """
    if isinstance(value, (list, tuple, set)):
        candidates = [str(item) for item in value]
    elif isinstance(value, str):
        candidates = _split_accept_language(value)
    else:
        return DEFAULT_LOCALE

    for candidate in candidates:
        matched = _match_locale_tag(candidate)
        if matched is not None:
            return matched
    return DEFAULT_LOCALE


def _header_value(request: Any, name: str) -> str:
    """从 Starlette Request / 普通 Mapping / 测试替身上读头,读不到就当空。"""
    if request is None:
        return ""
    headers = getattr(request, "headers", None)
    if headers is None and isinstance(request, dict):
        headers = request.get("headers")
    if headers is None:
        return ""
    try:
        return headers.get(name) or ""
    except (AttributeError, TypeError):
        return ""


def resolve_request_locale(request: Any = None, explicit: Any = None) -> str:
    """解析本次请求的 locale:body 的 locale > Accept-Language > 默认 zh-CN。

    `explicit` 是请求体里的 `locale`(仅 Chat 这类需要精细控制的接口会带)。
    显式值非法时按规格回落 `zh-CN`,不再往下看请求头 —— 避免两端"各取一半"。
    """
    if isinstance(explicit, str) and explicit.strip():
        return normalize_locale(explicit)
    return normalize_locale(_header_value(request, ACCEPT_LANGUAGE_HEADER))


def is_supported_locale(value: Any) -> bool:
    """是否恰好是受支持的两个 locale 之一(用于校验,不做猜测)。"""
    return isinstance(value, str) and value.strip() in SUPPORTED_LOCALES
