"""Conversation 测试(§41.1,7 个):

0 / 1 / 多城市创建、只列当前用户的会话、取别人会话被拒(404)、
整组替换城市、adcode 去重。

不消耗任何外部 API:Conversation 接口完全不碰 DeepSeek / 高德。
"""

from fastapi.testclient import TestClient

API = "/api/v1"

CHENGDU = {"city_name": "成都", "adcode": "510100"}
CHONGQING = {"city_name": "重庆", "adcode": "500000"}
HANGZHOU = {"city_name": "杭州", "adcode": "330100"}
WUHAN = {"city_name": "武汉", "adcode": "420100"}


def _register(client, payload):
    assert client.post(f"{API}/auth/register", json=payload).status_code == 201


def _other_payload():
    return {"username": "other", "email": "other@example.com", "password": "travel1234"}


def _create(client, cities=None):
    response = client.post(f"{API}/conversations", json={"cities": cities or []})
    assert response.status_code == 201
    return response.json()


def test_create_conversation_without_city(client_fixture, user_payload_fixture):
    _register(client_fixture, user_payload_fixture)

    response = client_fixture.post(f"{API}/conversations", json={"cities": []})

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["title"] == "新对话"
    assert body["cities"] == []
    assert body["created_at"] and body["updated_at"]
    # 立刻出现在自己的列表里
    assert [item["id"] for item in client_fixture.get(f"{API}/conversations").json()] == [body["id"]]


def test_create_conversation_with_one_city(client_fixture, user_payload_fixture):
    _register(client_fixture, user_payload_fixture)

    body = _create(client_fixture, [CHENGDU])

    assert body["cities"] == [CHENGDU]
    assert body["title"] == "新对话"
    detail = client_fixture.get(f"{API}/conversations/{body['id']}").json()
    assert detail == body


def test_create_conversation_with_multiple_cities(client_fixture, user_payload_fixture):
    _register(client_fixture, user_payload_fixture)

    body = _create(client_fixture, [CHENGDU, CHONGQING, WUHAN])

    assert body["cities"] == [CHENGDU, CHONGQING, WUHAN]
    assert [city["adcode"] for city in body["cities"]] == ["510100", "500000", "420100"]


def test_list_only_current_users_conversations(create_test_app, client_fixture, user_payload_fixture):
    _register(client_fixture, user_payload_fixture)
    first = _create(client_fixture, [CHENGDU])
    second = _create(client_fixture, [CHONGQING])

    with TestClient(create_test_app) as other:
        _register(other, _other_payload())
        other_conversation = _create(other, [HANGZHOU])
        # 别人的列表里只有别人的会话
        assert [item["id"] for item in other.get(f"{API}/conversations").json()] == [
            other_conversation["id"]
        ]

    # 最近活跃(updated_at DESC)排在最前
    assert client_fixture.put(
        f"{API}/conversations/{first['id']}/cities", json={"cities": [CHENGDU, WUHAN]}
    ).status_code == 200

    items = client_fixture.get(f"{API}/conversations").json()
    assert [item["id"] for item in items] == [first["id"], second["id"]]
    assert all(set(item) == {"id", "title", "cities", "created_at", "updated_at"} for item in items)


def test_get_other_users_conversation_denied(create_test_app, client_fixture, user_payload_fixture):
    _register(client_fixture, user_payload_fixture)
    conversation = _create(client_fixture, [CHENGDU])

    with TestClient(create_test_app) as other:
        _register(other, _other_payload())

        assert other.get(f"{API}/conversations/{conversation['id']}").status_code == 404
        assert other.get(f"{API}/conversations/{conversation['id']}/messages").status_code == 404
        assert (
            other.put(
                f"{API}/conversations/{conversation['id']}/cities", json={"cities": [HANGZHOU]}
            ).status_code
            == 404
        )
        assert (
            other.post(
                f"{API}/conversations/{conversation['id']}/messages", json={"content": "你好"}
            ).status_code
            == 404
        )
        # 别人的会话城市没有被改动
        assert client_fixture.get(f"{API}/conversations/{conversation['id']}").json()["cities"] == [
            CHENGDU
        ]

    # 不存在的会话同样是 404;自己的仍然可读
    assert client_fixture.get(f"{API}/conversations/999999").status_code == 404
    assert client_fixture.get(f"{API}/conversations/{conversation['id']}").status_code == 200


def test_update_conversation_cities(client_fixture, user_payload_fixture):
    _register(client_fixture, user_payload_fixture)
    conversation = _create(client_fixture, [CHENGDU])

    replaced = client_fixture.put(
        f"{API}/conversations/{conversation['id']}/cities", json={"cities": [CHONGQING, WUHAN]}
    )

    assert replaced.status_code == 200
    assert replaced.json()["cities"] == [CHONGQING, WUHAN]
    # 是"整组替换",不是追加
    assert client_fixture.get(f"{API}/conversations/{conversation['id']}").json()["cities"] == [
        CHONGQING,
        WUHAN,
    ]

    # 也可以整组替换成 0 个城市
    emptied = client_fixture.put(
        f"{API}/conversations/{conversation['id']}/cities", json={"cities": []}
    )
    assert emptied.status_code == 200
    assert emptied.json()["cities"] == []

    # 复用已有的 adcode 重新整组替换:先删后插,不会撞 UNIQUE(conversation_id, adcode)
    again = client_fixture.put(
        f"{API}/conversations/{conversation['id']}/cities", json={"cities": [WUHAN, CHONGQING]}
    )
    assert again.status_code == 200
    assert again.json()["cities"] == [WUHAN, CHONGQING]


def test_conversation_city_deduplication(client_fixture, user_payload_fixture):
    _register(client_fixture, user_payload_fixture)

    created = _create(client_fixture, [CHENGDU, CHENGDU, {"city_name": "成都市", "adcode": "510100"}])

    # 同一个 adcode 只保留第一次出现的那个
    assert created["cities"] == [CHENGDU]

    updated = client_fixture.put(
        f"{API}/conversations/{created['id']}/cities",
        json={"cities": [CHONGQING, CHENGDU, CHONGQING]},
    )
    assert updated.status_code == 200
    assert updated.json()["cities"] == [CHONGQING, CHENGDU]
