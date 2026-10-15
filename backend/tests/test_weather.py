"""天气测试:实时 + 预报合并、穿衣建议、外部 API 失败。

所有高德调用都必须 mock,测试绝不消耗真实 API quota。
"""

import asyncio

from app.schemas.weather import WeatherInfo
from app.services import amap_client, weather_service

API = "/api/v1"

# 实测:extensions=base 才有 lives;extensions=all 只有 forecasts
LIVE_PAYLOAD = {
    "status": "1",
    "infocode": "10000",
    "lives": [
        {
            "province": "四川",
            "city": "成都市",
            "adcode": "510100",
            "weather": "多云",
            "temperature": "22",
            "winddirection": "东北",
            "windpower": "3",
            "humidity": "65",
            "reporttime": "2024-05-01 10:00:00",
        }
    ],
}
FORECAST_PAYLOAD = {
    "status": "1",
    "infocode": "10000",
    "forecasts": [
        {
            "city": "成都市",
            "casts": [
                {
                    "date": "2024-05-01",
                    "dayweather": "多云",
                    "nightweather": "小雨",
                    "daytemp": "25",
                    "nighttemp": "18",
                    "daytemp_float": "25.0",
                    "nighttemp_float": "18.0",
                }
            ],
        }
    ],
}
# get_weather() 合并后的原始结构
MERGED_WEATHER = {
    "lives": LIVE_PAYLOAD["lives"],
    "forecasts": FORECAST_PAYLOAD["forecasts"],
}


def _login(client, payload):
    assert client.post(f"{API}/auth/register", json=payload).status_code == 201


def _patch_weather(monkeypatch, payload):
    """把 amap_client.get_weather 换成异步假函数(不发任何真实请求)。"""

    async def fake_get_weather(adcode):
        assert adcode
        return payload

    monkeypatch.setattr(amap_client, "get_weather", fake_get_weather)


def test_weather_success(monkeypatch, client_fixture, user_payload_fixture):
    # 1) 真实 amap_client.get_weather 必须请求两次:base 拿实时、all 拿预报
    requested_extensions = []

    async def fake_request_amap(path, params):
        requested_extensions.append(params["extensions"])
        return LIVE_PAYLOAD if params["extensions"] == "base" else FORECAST_PAYLOAD

    monkeypatch.setattr(amap_client, "request_amap", fake_request_amap)
    raw = asyncio.run(amap_client.get_weather("510100"))

    assert sorted(requested_extensions) == ["all", "base"]
    assert raw["lives"][0]["weather"] == "多云"
    assert raw["forecasts"][0]["casts"][0]["daytemp"] == "25"

    # 2) 归一化:实时 + 预报合并成契约字段(字符串 -> float)
    normalized = weather_service.normalize_weather(raw)
    assert normalized.weather == "多云"
    assert normalized.temperature == 22.0
    assert normalized.min_temperature == 18.0
    assert normalized.max_temperature == 25.0
    assert normalized.humidity == 65.0
    assert normalized.wind_direction == "东北"
    assert normalized.wind_power == "3"

    # 3) 接口层
    _patch_weather(monkeypatch, MERGED_WEATHER)
    _login(client_fixture, user_payload_fixture)

    response = client_fixture.get(f"{API}/weather", params={"adcode": "510100"})

    assert response.status_code == 200
    body = response.json()
    assert body["weather"] == {
        "weather": "多云",
        "temperature": 22.0,
        "min_temperature": 18.0,
        "max_temperature": 25.0,
        "humidity": 65.0,
        "wind_direction": "东北",
        "wind_power": "3",
    }
    assert body["clothing_advice"] == "薄外套"


def test_clothing_advice_cold(monkeypatch, client_fixture, user_payload_fixture):
    assert weather_service.build_clothing_advice(WeatherInfo(weather="晴", temperature=3.0)) == "厚外套"
    assert weather_service.build_clothing_advice(WeatherInfo(weather="晴", temperature=10.0)) == "外套 / 毛衣"
    assert weather_service.build_clothing_advice(WeatherInfo(weather="晴", temperature=35.0)) == "轻薄透气衣物"
    # 温度缺失时退回 (min + max) / 2
    assert (
        weather_service.build_clothing_advice(
            WeatherInfo(weather="晴", min_temperature=2.0, max_temperature=4.0)
        )
        == "厚外套"
    )
    # 什么都没有 -> 暂无信息,绝不编造
    assert weather_service.build_clothing_advice(WeatherInfo()) == "暂无信息"

    _patch_weather(
        monkeypatch,
        {
            "lives": [{"weather": "晴", "temperature": "3", "humidity": [], "windpower": []}],
            "forecasts": [],
        },
    )
    _login(client_fixture, user_payload_fixture)

    body = client_fixture.get(f"{API}/weather", params={"adcode": "510100"}).json()

    assert body["clothing_advice"] == "厚外套"
    # 空数组一律归一化成 None
    assert body["weather"]["humidity"] is None
    assert body["weather"]["wind_power"] is None
    assert body["weather"]["min_temperature"] is None


def test_clothing_advice_rain(monkeypatch, client_fixture, user_payload_fixture):
    assert (
        weather_service.build_clothing_advice(WeatherInfo(weather="中雨", temperature=20.0))
        == "薄外套 / 建议携带雨具"
    )
    assert (
        weather_service.build_clothing_advice(WeatherInfo(weather="雷阵雨", temperature=None))
        == "建议携带雨具"
    )

    _patch_weather(monkeypatch, {"lives": [{"weather": "阵雨", "temperature": "26"}], "forecasts": []})
    _login(client_fixture, user_payload_fixture)

    body = client_fixture.get(f"{API}/weather", params={"adcode": "510100"}).json()

    assert body["weather"]["weather"] == "阵雨"
    assert body["clothing_advice"] == "短袖 / 建议携带雨具"


def test_weather_external_api_failure(monkeypatch, client_fixture, user_payload_fixture):
    async def broken_get_weather(adcode):
        raise amap_client.AmapError(amap_client.UNAVAILABLE_MESSAGE)

    monkeypatch.setattr(amap_client, "get_weather", broken_get_weather)
    _login(client_fixture, user_payload_fixture)

    response = client_fixture.get(f"{API}/weather", params={"adcode": "510100"})

    assert response.status_code == 502
    assert response.json()["detail"] == "天气服务暂时不可用"
    # 不泄露 Key / 完整 URL / 原始异常
    assert "restapi" not in response.text.lower()
    assert "key" not in response.text.lower()
    assert "AmapError" not in response.text

    # 空结果(高德没有该城市):字段全 None + 暂无信息,而不是 500
    _patch_weather(monkeypatch, {"lives": [], "forecasts": []})
    empty = client_fixture.get(f"{API}/weather", params={"adcode": "999999"})
    assert empty.status_code == 200
    assert empty.json()["weather"] == {
        "weather": None,
        "temperature": None,
        "min_temperature": None,
        "max_temperature": None,
        "humidity": None,
        "wind_direction": None,
        "wind_power": None,
    }
    assert empty.json()["clothing_advice"] == "暂无信息"

    # 未登录一律 401
    client_fixture.cookies.clear()
    assert client_fixture.get(f"{API}/weather", params={"adcode": "510100"}).status_code == 401
