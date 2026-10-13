"""偏好接口测试:读取 / 保存 / 修改 / Skip / 未登录拦截。"""

API = "/api/v1"

SAMPLE_PREFERENCES = {
    "attraction_preferences": ["自然风景", "古镇"],
    "food_preferences": ["火锅", "当地特色"],
    "budget": "普通",
    "travel_pace": "适中",
}


def test_get_empty_preferences(client_fixture, user_payload_fixture):
    client_fixture.post(f"{API}/auth/register", json=user_payload_fixture)

    response = client_fixture.get(f"{API}/preferences/me")

    assert response.status_code == 200
    body = response.json()
    assert body["attraction_preferences"] == []
    assert body["food_preferences"] == []
    assert body["budget"] is None
    assert body["travel_pace"] is None


def test_save_preferences(client_fixture, user_payload_fixture):
    client_fixture.post(f"{API}/auth/register", json=user_payload_fixture)

    response = client_fixture.put(f"{API}/preferences/me", json=SAMPLE_PREFERENCES)

    assert response.status_code == 200
    assert response.json()["attraction_preferences"] == SAMPLE_PREFERENCES["attraction_preferences"]

    # 保存偏好即视为完成 Onboarding
    me = client_fixture.get(f"{API}/auth/me")
    assert me.json()["onboarding_completed"] is True

    # 重新读取应回显同一份偏好
    again = client_fixture.get(f"{API}/preferences/me")
    assert again.json()["food_preferences"] == SAMPLE_PREFERENCES["food_preferences"]


def test_update_preferences(client_fixture, user_payload_fixture):
    client_fixture.post(f"{API}/auth/register", json=user_payload_fixture)
    client_fixture.put(f"{API}/preferences/me", json=SAMPLE_PREFERENCES)

    updated = {
        "attraction_preferences": ["博物馆"],
        "food_preferences": ["甜食"],
        "budget": "高品质",
        "travel_pace": "紧凑",
    }
    response = client_fixture.put(f"{API}/preferences/me", json=updated)

    assert response.status_code == 200
    body = response.json()
    assert body["attraction_preferences"] == ["博物馆"]
    assert body["budget"] == "高品质"
    assert body["travel_pace"] == "紧凑"

    # 仍是同一份记录,不应产生第二条
    assert body["id"] == client_fixture.get(f"{API}/preferences/me").json()["id"]


def test_skip_onboarding(client_fixture, user_payload_fixture):
    client_fixture.post(f"{API}/auth/register", json=user_payload_fixture)

    response = client_fixture.post(f"{API}/preferences/skip")

    assert response.status_code == 200
    assert response.json()["onboarding_completed"] is True

    # Skip 不伪造偏好
    preferences = client_fixture.get(f"{API}/preferences/me")
    assert preferences.json()["attraction_preferences"] == []
    assert preferences.json()["budget"] is None


def test_preferences_require_login(client_fixture):
    assert client_fixture.get(f"{API}/preferences/me").status_code == 401
    assert client_fixture.put(f"{API}/preferences/me", json=SAMPLE_PREFERENCES).status_code == 401
    assert client_fixture.post(f"{API}/preferences/skip").status_code == 401
