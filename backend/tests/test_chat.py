"""Chat 测试(§41.2,6 个):

消息落库、会话所有权、A/B 消息隔离、第一条消息改标题、
DeepSeek 失败不写假 assistant、聊天必须登录。

DeepSeek 与高德的调用全部 mock,测试不消耗真实 quota。
"""

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.schemas.weather import WeatherInfo, WeatherResponse
from app.services import agent_service, deepseek_client, weather_service

API = "/api/v1"

CHENGDU = {"city_name": "成都", "adcode": "510100"}
HANGZHOU = {"city_name": "杭州", "adcode": "330100"}


def _register(client, payload):
    assert client.post(f"{API}/auth/register", json=payload).status_code == 201


def _other_payload():
    return {"username": "other", "email": "other@example.com", "password": "travel1234"}


def _create(client, cities=None):
    response = client.post(f"{API}/conversations", json={"cities": cities or []})
    assert response.status_code == 201
    return response.json()


def _send(client, conversation_id, content):
    return client.post(f"{API}/conversations/{conversation_id}/messages", json={"content": content})


def _final_text_response(text):
    return {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": text}}]}


def _tool_call_response(*tool_calls):
    return {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {"role": "assistant", "content": None, "tool_calls": list(tool_calls)},
            }
        ]
    }


def _tool_call(call_id, name, arguments):
    return {
        "index": 0,
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
    }


def _patch_deepseek(monkeypatch, responses):
    """按调用顺序依次返回预设响应,并记录每次真正发给模型的消息。"""
    seen = []

    async def fake_chat_completion(messages, tools=None, response_format=None, temperature=None):
        seen.append([dict(message) for message in messages])
        index = min(len(seen) - 1, len(responses) - 1)
        return responses[index]

    monkeypatch.setattr(deepseek_client, "chat_completion", fake_chat_completion)
    return seen


def _patch_weather(monkeypatch):
    calls = []

    async def fake_get_city_weather(adcode):
        calls.append(adcode)
        return WeatherResponse(
            weather=WeatherInfo(
                weather="多云",
                temperature=18.0,
                min_temperature=15.0,
                max_temperature=22.0,
                humidity=60.0,
                wind_direction="北",
                wind_power="2",
            ),
            clothing_advice="薄外套",
        )

    monkeypatch.setattr(weather_service, "get_city_weather", fake_get_city_weather)
    return calls


def test_send_message_persists_user_and_assistant(monkeypatch, client_fixture, user_payload_fixture):
    _register(client_fixture, user_payload_fixture)
    conversation = _create(client_fixture, [CHENGDU])
    client_fixture.put(
        f"{API}/preferences/me",
        json={
            "attraction_preferences": ["自然风景"],
            "food_preferences": ["辣"],
            "budget": "普通",
            "travel_pace": "悠闲",
        },
    )

    # 一轮同时触发两个工具(实测 DeepSeek 会这样),第二轮才给最终文本
    responses = [
        _tool_call_response(
            _tool_call("call_pref", "get_user_preferences", {}),
            _tool_call("call_weather", "get_weather", {"city_name": "成都"}),
        ),
        _final_text_response("成都今天多云,18℃,建议薄外套,适合自然风景的一日行程。"),
    ]
    seen = _patch_deepseek(monkeypatch, responses)
    weather_calls = _patch_weather(monkeypatch)

    response = _send(client_fixture, conversation["id"], "明天成都天气怎么样?我想看自然风景")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"user_message", "assistant_message", "activities"}
    assert body["user_message"]["role"] == "user"
    assert body["user_message"]["content"] == "明天成都天气怎么样?我想看自然风景"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["content"] == "成都今天多云,18℃,建议薄外套,适合自然风景的一日行程。"
    assert body["assistant_message"]["id"] > body["user_message"]["id"]

    # Activity 只来自真实执行过的两个工具,顺序与调用顺序一致。
    # v0.3.1(契约 §4):每项新增机器可读 code + params(原始中文/ID),text 保留兼容。
    assert body["activities"] == [
        {
            "type": "preference",
            "status": "success",
            "code": "agent.preferences_read",
            "params": {},
            "text": "已读取旅行偏好",
        },
        {
            "type": "weather",
            "status": "success",
            "code": "agent.weather_found",
            "params": {"city_name": "成都", "city_adcode": "510100"},
            "text": "已查询成都天气",
        },
    ]
    assert weather_calls == ["510100"]

    # 工具消息被回灌:assistant(tool_calls) + 两条 tool 结果,顺序与 id 都对得上
    second_round = seen[1]
    assert [message["role"] for message in second_round[-3:]] == ["assistant", "tool", "tool"]
    assert len(second_round[-3]["tool_calls"]) == 2
    assert second_round[-2]["tool_call_id"] == "call_pref"
    assert second_round[-1]["tool_call_id"] == "call_weather"
    tool_payload = json.loads(second_round[-1]["content"])
    assert tool_payload["ok"] is True
    assert tool_payload["data"]["weather"]["weather"] == "多云"
    preference_payload = json.loads(second_round[-2]["content"])
    assert preference_payload["data"]["attraction_preferences"] == ["自然风景"]

    # 第一轮:system prompt + 当前 user message,且注册了 4 个工具
    assert seen[0][0]["role"] == "system"
    assert "TravelMate" in seen[0][0]["content"]
    assert [message["role"] for message in seen[0][1:]] == ["user"]

    # 数据库只保存最终两条消息:工具临时消息不落库
    messages = client_fixture.get(f"{API}/conversations/{conversation['id']}/messages").json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == body["user_message"]["content"]
    assert set(messages[0]) == {"id", "role", "content", "created_at"}

    # 上下文只注入最近 N 条历史 + 新的 user message(N = AGENT_CONTEXT_MESSAGE_LIMIT)
    monkeypatch.setattr(
        agent_service,
        "get_settings",
        lambda: SimpleNamespace(agent_context_message_limit=2, agent_max_tool_rounds=5),
    )
    seen = _patch_deepseek(monkeypatch, [_final_text_response("第三轮回答")])
    assert _send(client_fixture, conversation["id"], "第三个问题").status_code == 200
    limited_round = seen[-1]
    assert [message["role"] for message in limited_round] == ["system", "user", "assistant", "user"]
    assert limited_round[-1]["content"] == "第三个问题"
    assert limited_round[1]["content"] == body["user_message"]["content"]
    assert limited_round[2]["content"] == body["assistant_message"]["content"]
    # 数据库仍然保存全部消息
    assert len(client_fixture.get(f"{API}/conversations/{conversation['id']}/messages").json()) == 4


def test_get_messages_only_for_owned_conversation(
    create_test_app, client_fixture, user_payload_fixture
):
    _register(client_fixture, user_payload_fixture)
    conversation = _create(client_fixture, [CHENGDU])

    assert client_fixture.get(f"{API}/conversations/{conversation['id']}/messages").json() == []
    assert client_fixture.get(f"{API}/conversations/999999/messages").status_code == 404

    with TestClient(create_test_app) as other:
        _register(other, _other_payload())
        assert other.get(f"{API}/conversations/{conversation['id']}/messages").status_code == 404


def test_conversation_a_messages_not_in_b(monkeypatch, client_fixture, user_payload_fixture):
    _register(client_fixture, user_payload_fixture)
    conversation_a = _create(client_fixture, [CHENGDU])
    conversation_b = _create(client_fixture, [HANGZHOU])

    responses = [
        _final_text_response("回答一"),
        _final_text_response("回答二"),
        _final_text_response("B 的回答"),
    ]
    seen = _patch_deepseek(monkeypatch, responses)

    assert _send(client_fixture, conversation_a["id"], "A 的问题一").status_code == 200
    assert _send(client_fixture, conversation_a["id"], "A 的问题二").status_code == 200

    # B 的历史里绝不能出现 A 的消息
    assert client_fixture.get(f"{API}/conversations/{conversation_b['id']}/messages").json() == []

    assert _send(client_fixture, conversation_b["id"], "B 的问题").status_code == 200

    # 第三次请求是发给 B 的:上下文只有 system + B 自己的新问题
    b_round = seen[2]
    assert [message["role"] for message in b_round] == ["system", "user"]
    assert b_round[1]["content"] == "B 的问题"
    assert "A 的问题" not in json.dumps(b_round, ensure_ascii=False)

    # A 自己的第二轮上下文里确实带着 A 的上一轮(user + assistant)
    assert [message["role"] for message in seen[1]] == ["system", "user", "assistant", "user"]

    a_messages = client_fixture.get(f"{API}/conversations/{conversation_a['id']}/messages").json()
    assert [message["content"] for message in a_messages] == [
        "A 的问题一",
        "回答一",
        "A 的问题二",
        "回答二",
    ]
    b_messages = client_fixture.get(f"{API}/conversations/{conversation_b['id']}/messages").json()
    assert [message["content"] for message in b_messages] == ["B 的问题", "B 的回答"]


def test_first_message_updates_title(monkeypatch, client_fixture, user_payload_fixture):
    _register(client_fixture, user_payload_fixture)
    conversation = _create(client_fixture, [])
    _patch_deepseek(monkeypatch, [_final_text_response("好的。")])

    long_content = "帮我规划一个成都三日游，要包含自然风景、当地美食和轻松节奏"
    assert _send(client_fixture, conversation["id"], long_content).status_code == 200

    title = client_fixture.get(f"{API}/conversations/{conversation['id']}").json()["title"]
    assert title == long_content[:20]
    assert 0 < len(title) <= 20
    assert title != long_content
    assert title != "新对话"

    # 第二条消息不再覆盖标题,但要更新 updated_at
    before = client_fixture.get(f"{API}/conversations/{conversation['id']}").json()
    assert _send(client_fixture, conversation["id"], "再帮我加一天").status_code == 200
    after = client_fixture.get(f"{API}/conversations/{conversation['id']}").json()
    assert after["title"] == title
    assert after["updated_at"] >= before["updated_at"]

    # 带换行的第一条消息:标题里不能出现换行
    second = _create(client_fixture, [])
    assert _send(client_fixture, second["id"], "第一行\n第二行 还有   多余空格").status_code == 200
    second_title = client_fixture.get(f"{API}/conversations/{second['id']}").json()["title"]
    assert "\n" not in second_title
    assert second_title == "第一行 第二行 还有 多余空格"


def test_deepseek_failure_does_not_create_fake_assistant(
    monkeypatch, client_fixture, user_payload_fixture
):
    _register(client_fixture, user_payload_fixture)
    conversation = _create(client_fixture, [CHENGDU])

    async def broken_chat_completion(messages, tools=None, response_format=None, temperature=None):
        raise deepseek_client.DeepSeekError(deepseek_client.UNAVAILABLE_MESSAGE)

    monkeypatch.setattr(deepseek_client, "chat_completion", broken_chat_completion)

    response = _send(client_fixture, conversation["id"], "成都明天天气怎么样?")

    assert response.status_code == 502
    assert response.json()["detail"] == "AI 助手暂时不可用,请稍后重试"
    assert "DeepSeek" not in response.text

    # 用户消息保留,但绝不写入任何虚假的 assistant 消息
    messages = client_fixture.get(f"{API}/conversations/{conversation['id']}/messages").json()
    assert [message["role"] for message in messages] == ["user"]
    assert messages[0]["content"] == "成都明天天气怎么样?"

    # 重新可用的下一轮仍然能正常问答(可重试)
    _patch_deepseek(monkeypatch, [_final_text_response("现在可以回答了。")])
    retried = _send(client_fixture, conversation["id"], "再试一次")
    assert retried.status_code == 200
    assert retried.json()["assistant_message"]["content"] == "现在可以回答了。"


def test_chat_requires_authentication(client_fixture):
    assert client_fixture.get(f"{API}/conversations").status_code == 401
    assert client_fixture.post(f"{API}/conversations", json={"cities": []}).status_code == 401
    assert client_fixture.get(f"{API}/conversations/1/messages").status_code == 401
    assert (
        client_fixture.post(
            f"{API}/conversations/1/messages", json={"content": "你好"}
        ).status_code
        == 401
    )
