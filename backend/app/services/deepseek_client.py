"""v0.3 通用 DeepSeek Client(§27)。

整个项目只保留这一个 DeepSeek 客户端:
- `chat_completion()`:通用 Chat / Tool Calling(Agent 用);
- `generate_json()`  :要求模型只返回 JSON 对象(v0.2 的"10 种代表性美食"继续用它);
- `normalize_tool_calls()`:把第三方原始响应里的 tool_calls 转成内部统一结构。

实测事实(务必保持):
1. `POST {base_url}/chat/completions`,带 `tools=[{"type":"function","function":{...}}]`
   的 OpenAI 兼容格式;
2. 返回 `choices[0].message.tool_calls[].function.arguments` 是 **JSON 字符串**,
   必须 json.loads;坏 JSON 只让这一条工具调用给出受控错误,绝不能让接口 500;
3. 一轮可能返回多个 tool_calls,上层必须全部执行、全部回灌;
4. `response_format={"type":"json_object"}` 只接受 JSON 对象,所以配套 prompt 必须
   要求 `{"foods": [...]}` 这类对象包装;解析时同时容忍裸数组与 ```json 代码块
   (v0.2 的容错逻辑原样保留,否则美食 Tab 会回归失败)。

安全:Key 只来自后端环境变量;日志与异常文本里绝不含 Key / 完整 URL / 原始响应体(§43.4 / §43.10)。
"""

import json
import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

CHAT_COMPLETIONS_PATH = "/chat/completions"
DEEPSEEK_TIMEOUT_SECONDS = 30.0

#: 占位 / 空 Key 一律视为"未配置",绝不带着假 Key 发请求
PLACEHOLDER_API_KEYS = {"", "change_me"}

CONFIG_ERROR_MESSAGE = "AI 服务未配置"
UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"
PARSE_ERROR_MESSAGE = "AI 返回数据解析失败,请稍后重试"

#: JSON 生成模式:DeepSeek 只接受 JSON 对象
JSON_RESPONSE_FORMAT = {"type": "json_object"}
JSON_TEMPERATURE = 0.7


class DeepSeekError(RuntimeError):
    """DeepSeek 调用失败(面向前端的可控异常)。"""

    #: 是否值得重试,供上层决定要不要提示用户稍后再试
    retryable = True


class DeepSeekConfigError(DeepSeekError):
    """DEEPSEEK_API_KEY 缺失或仍是占位符。"""

    retryable = False


class DeepSeekDataError(DeepSeekError):
    """模型返回的内容不是可解析的 JSON(可重试业务异常)。"""

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


def _parse_json_payload(content: Any) -> Any:
    """把模型输出解析成 Python 数据;已解析好的对象直接透传。

    容忍:裸数组 / `{"foods": [...]}` / ```json 代码块 / 前后夹带解释文字。
    失败抛可重试的 DeepSeekDataError。
    """
    if isinstance(content, (Mapping, list, tuple)):
        return content

    text = _strip_code_fence(content) if isinstance(content, str) else ""
    if not text:
        raise DeepSeekDataError(PARSE_ERROR_MESSAGE)

    for candidate in _json_candidates(text):
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    raise DeepSeekDataError(PARSE_ERROR_MESSAGE)


def _parse_tool_arguments(raw: Any) -> Optional[dict[str, Any]]:
    """`arguments` 是 JSON 字符串 -> dict。

    返回 None 表示"模型给的参数不是合法 JSON 对象",由 dispatcher 转成受控工具错误;
    空字符串 / 空对象都按"无参数"处理(两个工具真的不需要参数)。
    """
    if isinstance(raw, Mapping):
        return dict(raw)
    text = _strip_code_fence(raw) if isinstance(raw, str) else ""
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning("deepseek tool arguments are not valid json")
        return None
    return dict(parsed) if isinstance(parsed, Mapping) else None


def _response_message(response: Any) -> Mapping[str, Any]:
    """取 choices[0].message;结构不符一律返回空 dict(由调用方给受控错误)。"""
    if not isinstance(response, Mapping):
        return {}
    choices = response.get("choices")
    if not isinstance(choices, Sequence) or not choices:
        return {}
    first = choices[0]
    if not isinstance(first, Mapping):
        return {}
    message = first.get("message")
    return message if isinstance(message, Mapping) else {}


async def chat_completion(
    messages: Sequence[Mapping[str, Any]],
    tools: Optional[Sequence[Mapping[str, Any]]] = None,
    response_format: Optional[Mapping[str, Any]] = None,
    temperature: Optional[float] = None,
) -> dict[str, Any]:
    """调用 DeepSeek /chat/completions,返回原始响应 dict。

    参数:
    - messages:OpenAI 兼容消息数组(system / user / assistant / tool);
    - tools:Agent 的 Tool Calling 定义;tools=None 表示普通对话 / JSON 生成;
    - response_format / temperature:generate_json() 用到的可选透传项。
    """
    settings = get_settings()
    if not _is_api_key_configured(settings.deepseek_api_key):
        raise DeepSeekConfigError(CONFIG_ERROR_MESSAGE)

    request_body: dict[str, Any] = {
        "model": settings.deepseek_model,
        "messages": list(messages),
    }
    if tools:
        request_body["tools"] = list(tools)
    if response_format is not None:
        request_body["response_format"] = dict(response_format)
    if temperature is not None:
        request_body["temperature"] = temperature

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
        # 只记录异常类型:绝不把 Key / 完整 URL / 响应体写进日志
        logger.warning("deepseek request failed: %s", type(exc).__name__)
        raise DeepSeekError(UNAVAILABLE_MESSAGE) from exc
    except ValueError as exc:  # 非 JSON 响应
        logger.warning("deepseek returned non-json body")
        raise DeepSeekError(UNAVAILABLE_MESSAGE) from exc

    if not isinstance(data, Mapping) or data.get("error"):
        logger.warning("deepseek returned an api error payload")
        raise DeepSeekError(UNAVAILABLE_MESSAGE)
    return dict(data)


async def generate_json(system_prompt: str, user_prompt: str, temperature: float = JSON_TEMPERATURE) -> Any:
    """要求模型只输出一个 JSON 对象,并解析成 Python 数据(失败抛 DeepSeekDataError)。

    v0.2 的"10 种代表性美食"继续走这条路:调用方只需给出"要求返回 {"foods": [...]}"
    的 prompt,解析容错(裸数组 / 对象包装 / ```json 代码块)在 _parse_json_payload 里保留。
    """
    response = await chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=None,
        response_format=JSON_RESPONSE_FORMAT,
        temperature=temperature,
    )
    content = _response_message(response).get("content")
    return _parse_json_payload(content)


def normalize_tool_calls(response: Any) -> list[dict[str, Any]]:
    """把 DeepSeek 返回的 tool_calls 转成内部统一结构。

    返回 `[{"id", "name", "arguments"}]`:
    - `arguments` 已是解析后的 dict(可能为空 dict = 该工具本来就没有参数);
    - `arguments is None` 表示模型给的参数不是合法 JSON 对象,上层必须给受控错误。

    这样 agent_service 不必了解第三方原始 JSON 细节(§27.3)。
    """
    raw_calls = _response_message(response).get("tool_calls")
    if not isinstance(raw_calls, (list, tuple)):
        return []

    normalized: list[dict[str, Any]] = []
    for index, raw_call in enumerate(raw_calls):
        if not isinstance(raw_call, Mapping):
            continue
        function = raw_call.get("function")
        function = function if isinstance(function, Mapping) else {}
        name = _clean_str(function.get("name"))
        if not name:
            continue
        normalized.append(
            {
                "id": _clean_str(raw_call.get("id")) or f"call_{index}",
                "name": name,
                "arguments": _parse_tool_arguments(function.get("arguments")),
            }
        )
    return normalized
