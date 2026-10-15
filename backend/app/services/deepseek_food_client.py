"""v0.2 受限 DeepSeek 客户端:只为当前城市生成"10 种代表性美食名称 + 1~2 句简介"。

这不是聊天、不是 Agent、没有上下文(§32)。硬约束:
- 只允许返回美食 name + description;
- 绝不生成餐厅地址 / 电话 / 价格 / 评分 —— 餐厅事实全部由高德提供(§36);
- `response_format={"type": "json_object"}` 只接受 **JSON 对象**,所以 prompt 要求
  返回 `{"foods": [...]}`,而 parse_food_json 同时容忍裸数组与 ```json 代码块。
"""

import json
import logging
import re
from collections.abc import Mapping
from typing import Any, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

CHAT_COMPLETIONS_PATH = "/chat/completions"
DEEPSEEK_TIMEOUT_SECONDS = 30.0

FOOD_TARGET_COUNT = 10

PLACEHOLDER_API_KEYS = {"", "change_me"}

CONFIG_ERROR_MESSAGE = "美食推荐服务未配置"
UNAVAILABLE_MESSAGE = "美食推荐服务暂时不可用"
PARSE_ERROR_MESSAGE = "美食数据解析失败,请稍后重试"
EMPTY_ERROR_MESSAGE = "美食数据为空,请稍后重试"

SYSTEM_PROMPT = (
    "你是一位中国地方美食专家。你只输出 JSON,不输出任何解释性文字。"
)

USER_PROMPT_TEMPLATE = """请列出「{city}」最有代表性的 {count} 种当地美食。

只输出一个 JSON 对象,格式必须严格如下:
{{"foods": [{{"name": "美食名称", "description": "1~2 句简介"}}]}}

硬性要求:
1. foods 数组必须恰好 {count} 项,不多不少;
2. name 只能是美食名称本身(如"麻婆豆腐"),不要带城市名、不要带任何修饰;
3. description 用 1~2 句中文说明这道美食的特点,不要写地址、不要写餐厅名;
4. 绝对禁止输出任何餐厅的地址、电话、人均价格、评分、营业时间;
5. 绝对禁止编造具体餐厅信息,餐厅信息由其它系统查询;
6. 不要输出 Markdown 代码块,不要输出 JSON 以外的任何内容。"""


class DeepSeekError(RuntimeError):
    """受限 DeepSeek 调用失败(面向前端的可控异常)。"""

    retryable = True


class DeepSeekConfigError(DeepSeekError):
    """DEEPSEEK_API_KEY 缺失或仍是占位符。"""

    retryable = False


class FoodDataError(DeepSeekError):
    """模型返回的美食 JSON 解析 / 校验失败,属于可重试业务异常(§32.2)。"""

    retryable = True


def _is_api_key_configured(value: Optional[str]) -> bool:
    """Key 非空且不是 change_me 占位符才算配置好。"""
    return bool(value) and value.strip().lower() not in PLACEHOLDER_API_KEYS


def _clean_str(value: Any) -> Optional[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _strip_code_fence(text: str) -> str:
    """剥掉 ```json ... ``` / ``` ... ``` 包裹。"""
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned
    # 去掉第一行(``` 或 ```json)
    _, _, rest = cleaned.partition("\n")
    cleaned = rest if rest else ""
    cleaned = re.sub(r"```\s*$", "", cleaned.strip())
    return cleaned.strip()


def _json_candidates(text: str) -> list[str]:
    """依次尝试:全文 -> 第一个括号到最后一个括号之间的内容。"""
    candidates = [text]
    start_positions = [pos for pos in (text.find("["), text.find("{")) if pos >= 0]
    if start_positions:
        start = min(start_positions)
        end = max(text.rfind("]"), text.rfind("}"))
        if end > start:
            candidates.append(text[start : end + 1])
    return candidates


def _extract_items(data: Any) -> Optional[list[Any]]:
    """容忍三种形态:裸数组 / {"foods": [...]} / 其它单列表字段。"""
    if isinstance(data, (list, tuple)):
        return list(data)
    if isinstance(data, Mapping):
        for key in ("foods", "items", "data", "result", "list"):
            value = data.get(key)
            if isinstance(value, (list, tuple)):
                return list(value)
        list_values = [value for value in data.values() if isinstance(value, (list, tuple))]
        if len(list_values) == 1:
            return list(list_values[0])
    return None


def parse_food_json(content: Any) -> list[Any]:
    """把模型输出解析成美食条目列表;失败抛可重试的 FoodDataError。"""
    text = _strip_code_fence(content) if isinstance(content, str) else ""
    if not text:
        raise FoodDataError(PARSE_ERROR_MESSAGE)

    for candidate in _json_candidates(text):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        items = _extract_items(data)
        if items is not None:
            return items
    raise FoodDataError(PARSE_ERROR_MESSAGE)


def validate_food_items(items: Any) -> list[dict[str, str]]:
    """校验并清洗:必须是 list、name / description 非空、按 name 去重,最多取 10 个。"""
    if not isinstance(items, (list, tuple)):
        raise FoodDataError(PARSE_ERROR_MESSAGE)

    validated: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        name = _clean_str(item.get("name"))
        description = _clean_str(item.get("description"))
        if not name or not description or name in seen_names:
            continue
        seen_names.add(name)
        validated.append({"name": name, "description": description})
        if len(validated) >= FOOD_TARGET_COUNT:
            break

    if not validated:
        raise FoodDataError(EMPTY_ERROR_MESSAGE)
    return validated


async def generate_representative_foods(city_name: str) -> list[dict[str, str]]:
    """调用受限 DeepSeek,返回最多 10 条 {"name", "description"}。"""
    settings = get_settings()
    if not _is_api_key_configured(settings.deepseek_api_key):
        raise DeepSeekConfigError(CONFIG_ERROR_MESSAGE)

    city = _clean_str(city_name) or ""
    if not city:
        raise DeepSeekConfigError(CONFIG_ERROR_MESSAGE)

    request_body = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(city=city, count=FOOD_TARGET_COUNT),
            },
        ],
        # DeepSeek 的 json_object 只接受 JSON 对象,所以 prompt 里要求 {"foods": [...]}
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(
            base_url=settings.deepseek_base_url,
            timeout=DEEPSEEK_TIMEOUT_SECONDS,
            headers=headers,
        ) as client:
            response = await client.post(CHAT_COMPLETIONS_PATH, json=request_body)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.warning("deepseek request failed: %s", type(exc).__name__)
        raise DeepSeekError(UNAVAILABLE_MESSAGE) from exc
    except ValueError as exc:  # 非 JSON 响应
        logger.warning("deepseek returned non-json body")
        raise DeepSeekError(UNAVAILABLE_MESSAGE) from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("deepseek response shape unexpected")
        raise DeepSeekError(UNAVAILABLE_MESSAGE) from exc

    return validate_food_items(parse_food_json(content))
