"""Agent 运行时(§31–§35):Context -> Model Messages -> Tool Loop -> Activity -> 落库。

职责边界:
- 只持久化最终的 user / assistant 消息;assistant tool_call 消息与 tool 结果消息
  只在本次请求内传给 DeepSeek(§13 / §43.9);
- 上下文只包含当前 Conversation 的历史,绝不混入别的会话(§32 / §43);
- Activity 只根据实际执行过的工具生成,不含 prompt / Chain-of-Thought(§34 / §43.8)。
"""

import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.agent_prompts import AGENT_SYSTEM_PROMPT
from app.core.config import get_settings
from app.models.conversation import Conversation
from app.models.user import User
from app.services import agent_tools, conversation_service, deepseek_client

MESSAGE_ROLE_SYSTEM = "system"
MESSAGE_ROLE_USER = "user"
MESSAGE_ROLE_ASSISTANT = "assistant"
MESSAGE_ROLE_TOOL = "tool"

ACTIVITY_STATUS_SUCCESS = "success"
ACTIVITY_STATUS_ERROR = "error"

ACTIVITY_TYPE_PREFERENCE = "preference"
ACTIVITY_TYPE_WEATHER = "weather"
ACTIVITY_TYPE_ATTRACTION = "attraction"
ACTIVITY_TYPE_FOOD = "food"
ACTIVITY_TYPE_TOOL = "tool"

ACTIVITY_TEXTS: dict[str, dict[str, str]] = {
    agent_tools.TOOL_GET_USER_PREFERENCES: {
        "success": "已读取旅行偏好",
        "error": "偏好读取失败",
    },
    agent_tools.TOOL_GET_WEATHER: {
        "success": "已查询{city}天气",
        "error": "天气查询失败",
    },
    agent_tools.TOOL_SEARCH_ATTRACTIONS: {
        "success": "已找到{city}景点数据",
        "error": "景点查询失败",
    },
    agent_tools.TOOL_SEARCH_FOOD: {
        "success": "已找到{city}美食数据",
        "error": "美食查询失败",
    },
}

ACTIVITY_TYPES: dict[str, str] = {
    agent_tools.TOOL_GET_USER_PREFERENCES: ACTIVITY_TYPE_PREFERENCE,
    agent_tools.TOOL_GET_WEATHER: ACTIVITY_TYPE_WEATHER,
    agent_tools.TOOL_SEARCH_ATTRACTIONS: ACTIVITY_TYPE_ATTRACTION,
    agent_tools.TOOL_SEARCH_FOOD: ACTIVITY_TYPE_FOOD,
}

UNKNOWN_TOOL_ACTIVITY_TEXT = "工具调用失败"
EMPTY_ANSWER_MESSAGE = "AI 助手没有返回有效回复,请稍后重试"
MAX_TOOL_ROUNDS_MESSAGE = "AI 助手思考轮次过多,请稍后重试"


class AgentError(RuntimeError):
    """Agent 执行失败(面向前端的可控异常)。"""

    retryable = True


def _utcnow() -> datetime:
    """统一的"不带时区的 UTC 现在"(MySQL DATETIME 不存 tzinfo)。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clean_str(value: Any) -> Optional[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _response_message(response: Any) -> Mapping[str, Any]:
    """取 DeepSeek 响应里的 choices[0].message;结构不符返回空 dict。"""
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


def _role_and_content(item: Any) -> tuple[Optional[str], Optional[str]]:
    """兼容 ORM Message 与 dict 形态的历史消息。"""
    if isinstance(item, Mapping):
        role, content = item.get("role"), item.get("content")
    else:
        role, content = getattr(item, "role", None), getattr(item, "content", None)
    return _clean_str(role), content if isinstance(content, str) else None


def build_agent_context(db: Session, user_id: int, conversation: Conversation) -> dict[str, Any]:
    """构造 Agent 上下文(§31):当前用户 + 当前会话 + 会话已选城市。

    `db` 与 `user_id` 都由服务端注入,模型无法影响;
    绝不把别的 Conversation 的任何东西放进来。
    """
    cities = [
        {"city_name": city.city_name, "adcode": city.adcode}
        for city in sorted(conversation.cities, key=lambda item: item.id or 0)
    ]
    return {
        "db": db,
        "user_id": user_id,
        "conversation_id": conversation.id,
        "cities": cities,
    }


def build_model_messages(
    history: Optional[Sequence[Any]], user_content: str
) -> list[dict[str, str]]:
    """拼装单次请求的模型消息(§32):

    1. system prompt
    2. 当前 Conversation 最近 N 条 user / assistant 消息(N = AGENT_CONTEXT_MESSAGE_LIMIT)
    3. 当前新的 user message
    """
    limit = max(int(get_settings().agent_context_message_limit or 0), 0)

    normalized: list[dict[str, str]] = []
    for item in history or []:
        role, content = _role_and_content(item)
        if role in (MESSAGE_ROLE_USER, MESSAGE_ROLE_ASSISTANT) and content:
            normalized.append({"role": role, "content": content})
    if limit:
        normalized = normalized[-limit:]

    return [
        {"role": MESSAGE_ROLE_SYSTEM, "content": AGENT_SYSTEM_PROMPT},
        *normalized,
        {"role": MESSAGE_ROLE_USER, "content": user_content},
    ]


def build_activity(
    tool_name: str, arguments: Optional[Mapping[str, Any]], result: Mapping[str, Any]
) -> dict[str, str]:
    """把一次真实执行过的工具调用转成 Activity 文案(§34)。

    只翻译"确实发生过"的工具;失败时 status=error。
    绝不显示 prompt、工具原始 payload 或任何思维链。
    """
    status = (
        ACTIVITY_STATUS_SUCCESS
        if isinstance(result, Mapping) and result.get("ok")
        else ACTIVITY_STATUS_ERROR
    )
    texts = ACTIVITY_TEXTS.get(tool_name)
    if texts is None:
        return {"type": ACTIVITY_TYPE_TOOL, "status": ACTIVITY_STATUS_ERROR, "text": UNKNOWN_TOOL_ACTIVITY_TEXT}

    activity_type = ACTIVITY_TYPES.get(tool_name, ACTIVITY_TYPE_TOOL)
    if status == ACTIVITY_STATUS_ERROR:
        return {"type": activity_type, "status": status, "text": texts["error"]}

    city = ""
    keyword = ""
    if isinstance(arguments, Mapping):
        city = _clean_str(arguments.get("city_name")) or ""
        keyword = _clean_str(arguments.get("keyword")) or ""

    if tool_name == agent_tools.TOOL_SEARCH_FOOD and keyword:
        text = f"已找到{city}“{keyword}”相关餐厅"
    else:
        text = texts["success"].format(city=city)
    return {"type": activity_type, "status": status, "text": text}


async def run_tool_loop(
    messages: Sequence[Mapping[str, Any]], context: Mapping[str, Any]
) -> tuple[str, list[dict[str, str]]]:
    """Tool Calling 主循环(§33):返回 (最终文本, activities)。

    - 一轮返回多个 tool_calls 时全部执行、全部回灌;
    - 单个工具失败只让那一条 tool 消息变成受控错误说明,不中断整轮;
    - 超过 AGENT_MAX_TOOL_ROUNDS 仍不收敛 -> AgentError(受控错误,不写假消息)。
    """
    tools = agent_tools.build_tool_definitions()
    max_rounds = max(int(get_settings().agent_max_tool_rounds or 0), 1)

    working: list[dict[str, Any]] = [dict(message) for message in messages]
    activities: list[dict[str, str]] = []

    for _ in range(max_rounds):
        response = await deepseek_client.chat_completion(working, tools)
        message = _response_message(response)
        tool_calls = deepseek_client.normalize_tool_calls(response)

        if not tool_calls:
            final_text = _clean_str(message.get("content"))
            if not final_text:
                raise AgentError(EMPTY_ANSWER_MESSAGE)
            return final_text, activities

        # 回灌 assistant tool-call 消息:tool_calls 必须保持第三方原始结构
        working.append(
            {
                "role": MESSAGE_ROLE_ASSISTANT,
                "content": message.get("content"),
                "tool_calls": message.get("tool_calls"),
            }
        )

        for tool_call in tool_calls:
            arguments = tool_call.get("arguments")
            result = await agent_tools.execute_tool(tool_call["name"], arguments, context)
            activities.append(build_activity(tool_call["name"], arguments, result))
            working.append(
                {
                    "role": MESSAGE_ROLE_TOOL,
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )

    raise AgentError(MAX_TOOL_ROUNDS_MESSAGE)


async def handle_user_message(
    db: Session, current_user: User, conversation: Conversation, content: str
) -> dict[str, Any]:
    """一次完整问答(§35 十步):

    1. 路由层已经做过 get_owned_conversation();
    2. 保存 user message;
    3. 如果是该 Conversation 的第一条 user message -> build_conversation_title() 更新 title;
    4. 取该 Conversation 历史(最近 AGENT_CONTEXT_MESSAGE_LIMIT 条);
    5. build_agent_context();
    6. run_tool_loop();
    7. 保存最终 assistant message;
    8. 更新 conversation.updated_at;
    9. commit;
    10. 返回 user_message / assistant_message / activities。

    整体失败时:user message 保留,绝不写入虚假的 assistant 成功消息,抛可重试错误。
    """
    settings = get_settings()

    # 3. 判断这是不是该 Conversation 的第一条 user message(必须在落库之前判断)
    is_first_user_message = not conversation_service.get_conversation_messages(
        db, conversation.id, limit=1
    )

    # 2. 先落 user message(append_message 内部立即 commit,失败也不会丢用户输入)
    user_message = conversation_service.append_message(
        db, conversation.id, conversation_service.MESSAGE_ROLE_USER, content
    )

    # 第一条 user message 决定标题(确定性逻辑,不额外花一次 DeepSeek 请求)
    if is_first_user_message:
        conversation.title = conversation_service.build_conversation_title(content)

    conversation.updated_at = _utcnow()

    # 4. 当前会话历史:多取 1 条(刚保存的这条 user message 不占用 N 个历史额度)
    history = conversation_service.get_conversation_messages(
        db, conversation.id, limit=settings.agent_context_message_limit + 1
    )
    earlier = history[:-1] if history and history[-1].id == user_message.id else history

    # 5. 上下文 + 6. 工具循环
    context = build_agent_context(db, current_user.id, conversation)
    messages = build_model_messages(earlier, content)
    try:
        final_text, activities = await run_tool_loop(messages, context)
    except Exception:
        # 失败也要把 user message / 新标题留下,但绝不写任何 assistant 消息
        try:
            db.commit()
        except Exception:  # noqa: BLE001 - 会话可能已进入失败状态,回滚后再抛原异常
            db.rollback()
        raise

    # 7. 只保存最终 assistant 消息(工具临时消息不落库)
    assistant_message = conversation_service.append_message(
        db, conversation.id, conversation_service.MESSAGE_ROLE_ASSISTANT, final_text
    )

    # 8. + 9.
    conversation.updated_at = _utcnow()
    db.commit()
    db.refresh(conversation)

    # 10.
    return {
        "user_message": user_message,
        "assistant_message": assistant_message,
        "activities": activities,
    }
