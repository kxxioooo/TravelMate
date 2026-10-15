"""城市浏览历史测试:记录 / 去重 / 排序 / 未登录拦截。"""

import time

API = "/api/v1"

CHENGDU = {"city_name": "成都", "province": "四川", "adcode": "510100"}
CHONGQING = {"city_name": "重庆", "province": "重庆", "adcode": "500100"}
XIAN = {"city_name": "西安", "province": "陕西", "adcode": "610100"}


def _login(client, payload):
    """注册即建立登录态(Cookie 由 TestClient 保持)。"""
    assert client.post(f"{API}/auth/register", json=payload).status_code == 201


def test_record_city_view(client_fixture, user_payload_fixture):
    _login(client_fixture, user_payload_fixture)

    response = client_fixture.post(f"{API}/cities/history", json=CHENGDU)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"city_name", "province", "adcode", "viewed_at"}
    assert body["city_name"] == "成都"
    assert body["province"] == "四川"
    assert body["adcode"] == "510100"
    assert body["viewed_at"]

    history = client_fixture.get(f"{API}/cities/history")
    assert history.status_code == 200
    records = history.json()
    assert len(records) == 1
    assert records[0]["adcode"] == "510100"


def test_same_city_updates_timestamp_not_duplicate(client_fixture, user_payload_fixture):
    _login(client_fixture, user_payload_fixture)

    first = client_fixture.post(f"{API}/cities/history", json=CHENGDU).json()
    time.sleep(0.05)
    second = client_fixture.post(
        f"{API}/cities/history", json={**CHENGDU, "city_name": "成都"}
    ).json()

    assert second["viewed_at"] >= first["viewed_at"]

    records = client_fixture.get(f"{API}/cities/history").json()
    # 同一个 adcode 只保留一条,Recent Searches 不重复
    assert len(records) == 1
    assert records[0]["viewed_at"] == second["viewed_at"]


def test_recent_cities_order(client_fixture, user_payload_fixture):
    _login(client_fixture, user_payload_fixture)

    for city in (CHENGDU, CHONGQING, XIAN):
        assert client_fixture.post(f"{API}/cities/history", json=city).status_code == 200
        time.sleep(0.05)

    records = client_fixture.get(f"{API}/cities/history").json()

    # viewed_at 倒序:最后看的排最前
    assert [record["city_name"] for record in records] == ["西安", "重庆", "成都"]
    viewed_at = [record["viewed_at"] for record in records]
    assert viewed_at == sorted(viewed_at, reverse=True)
    assert len(records) <= 10


def test_history_requires_login(client_fixture):
    assert client_fixture.get(f"{API}/cities/history").status_code == 401
    assert client_fixture.post(f"{API}/cities/history", json=CHENGDU).status_code == 401
