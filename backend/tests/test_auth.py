"""认证接口测试:注册 / 登录 / 当前用户 / 未登录拦截。"""

API = "/api/v1"


def test_register_success(client_fixture, user_payload_fixture):
    response = client_fixture.post(f"{API}/auth/register", json=user_payload_fixture)

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["username"] == user_payload_fixture["username"]
    assert body["user"]["email"] == user_payload_fixture["email"]
    assert body["user"]["onboarding_completed"] is False
    # 密码 / 哈希绝不能出现在响应里,注册即建立登录态
    assert "password" not in response.text
    assert response.cookies.get("access_token")


def test_register_duplicate_email(client_fixture, user_payload_fixture):
    client_fixture.post(f"{API}/auth/register", json=user_payload_fixture)

    duplicate = {**user_payload_fixture, "username": "another_traveler"}
    response = client_fixture.post(f"{API}/auth/register", json=duplicate)

    assert response.status_code == 409
    assert response.json()["detail"] == "邮箱已经注册"


def test_register_duplicate_username(client_fixture, user_payload_fixture):
    client_fixture.post(f"{API}/auth/register", json=user_payload_fixture)

    duplicate = {**user_payload_fixture, "email": "another@example.com"}
    response = client_fixture.post(f"{API}/auth/register", json=duplicate)

    assert response.status_code == 409
    assert response.json()["detail"] == "用户名已经存在"


def test_login_success(client_fixture, user_payload_fixture):
    client_fixture.post(f"{API}/auth/register", json=user_payload_fixture)
    client_fixture.cookies.clear()

    response = client_fixture.post(
        f"{API}/auth/login",
        json={
            "email": user_payload_fixture["email"],
            "password": user_payload_fixture["password"],
        },
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == user_payload_fixture["email"]
    assert response.cookies.get("access_token")

    me = client_fixture.get(f"{API}/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == user_payload_fixture["username"]


def test_login_wrong_password(client_fixture, user_payload_fixture):
    client_fixture.post(f"{API}/auth/register", json=user_payload_fixture)
    client_fixture.cookies.clear()

    response = client_fixture.post(
        f"{API}/auth/login",
        json={"email": user_payload_fixture["email"], "password": "wrong_password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "邮箱或密码错误"


def test_me_requires_authentication(client_fixture):
    response = client_fixture.get(f"{API}/auth/me")

    assert response.status_code == 401
