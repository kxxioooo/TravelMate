"""景点测试:默认 Top 10 / 关键词搜索 / 分页 / 详情 / 缺失字段 / 外部失败。

高德调用全部 mock,测试不消耗真实 quota。
"""

import asyncio

from app.services import amap_client

API = "/api/v1"

# 模块级保存真实实现:monkeypatch 只替换 amap_client 上的属性,这里仍指向原函数
_REAL_SEARCH_POIS = amap_client.search_pois


def _login(client, payload):
    assert client.post(f"{API}/auth/register", json=payload).status_code == 201


def _poi(poi_id, name="宽窄巷子", rating="4.5", cost="60.00", photos=True, type_text="风景名胜;公园广场"):
    """高德真实结构:缺失值可能是空数组,biz_ext 里是字符串数字,location 是 "经度,纬度"。"""
    return {
        "id": poi_id,
        "name": name,
        "type": type_text,
        "typecode": "110000",
        "address": "四川省成都市青羊区",
        "location": "104.077761,30.651100",
        "tel": [],
        "biz_ext": {"rating": rating, "cost": cost},
        "photos": [{"title": [], "url": f"http://store.is.autonavi.com/{poi_id}.jpg"}]
        if photos
        else [],
    }


def _patch_search(monkeypatch, handler):
    async def fake_search_pois(city_name, keyword=None, category=None, page=1, page_size=10):
        return handler(city_name=city_name, keyword=keyword, category=category, page=page, page_size=page_size)

    monkeypatch.setattr(amap_client, "search_pois", fake_search_pois)


def test_default_returns_at_most_10(monkeypatch, client_fixture, user_payload_fixture):
    calls = []

    def handler(**kwargs):
        calls.append(kwargs)
        return {
            "status": "1",
            "infocode": "10000",
            "count": "600",
            "pois": [_poi(f"B{i:03d}") for i in range(kwargs["page_size"])],
        }

    _patch_search(monkeypatch, handler)
    _login(client_fixture, user_payload_fixture)

    response = client_fixture.get(f"{API}/attractions", params={"city_name": "成都", "adcode": "510100"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 10
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["total"] == 600
    assert body["has_more"] is True

    # 默认模式:不带 keywords(避免"景点"宽匹配出写字楼),只用类别码 110000
    assert calls[0]["keyword"] is None
    assert calls[0]["category"] == "110000"
    assert calls[0]["city_name"] == "成都"

    first = body["items"][0]
    assert first["poi_id"] == "B000"
    assert first["cover_photo"] == "http://store.is.autonavi.com/B000.jpg"
    assert first["rating"] == 4.5  # 字符串 "4.5" -> float
    assert first["tags"] == ["风景名胜", "公园广场"]


def test_search_uses_keyword(monkeypatch, client_fixture, user_payload_fixture):
    calls = []

    def handler(**kwargs):
        calls.append(kwargs)
        return {"status": "1", "count": "3", "pois": [_poi("B001", name="黄龙溪古镇")]}

    _patch_search(monkeypatch, handler)
    _login(client_fixture, user_payload_fixture)

    response = client_fixture.get(
        f"{API}/attractions", params={"city_name": "成都", "keyword": "古镇", "page": 1}
    )

    assert response.status_code == 200
    body = response.json()
    assert calls[0]["keyword"] == "古镇"
    assert calls[0]["category"] == "110000"
    # 搜索模式默认 page_size = 20
    assert calls[0]["page_size"] == 20
    assert body["page_size"] == 20
    assert body["items"][0]["name"] == "黄龙溪古镇"

    # 底层请求参数:默认模式不带 keywords;搜索模式 types=110000 + keywords
    captured = []

    async def fake_request_amap(path, params):
        captured.append(params)
        return {"status": "1", "count": "0", "pois": []}

    monkeypatch.setattr(amap_client, "request_amap", fake_request_amap)

    asyncio.run(
        _REAL_SEARCH_POIS(
            city_name="成都", keyword=None, category=amap_client.ATTRACTION_TYPES, page=1, page_size=10
        )
    )
    asyncio.run(
        _REAL_SEARCH_POIS(
            city_name="成都", keyword="古镇", category=amap_client.ATTRACTION_TYPES, page=2, page_size=20
        )
    )

    assert "keywords" not in captured[0]
    assert captured[0]["types"] == "110000"
    assert captured[0]["citylimit"] == "true"
    assert captured[0]["offset"] == 10
    assert captured[0]["page"] == 1
    assert captured[0]["extensions"] == "all"
    assert captured[1]["keywords"] == "古镇"
    assert captured[1]["offset"] == 20
    assert captured[1]["page"] == 2


def test_search_pagination(monkeypatch, client_fixture, user_payload_fixture):
    calls = []
    total = {"value": "600"}

    def handler(**kwargs):
        calls.append((kwargs["page"], kwargs["page_size"]))
        return {
            "status": "1",
            "count": total["value"],
            "pois": [_poi(f"B{kwargs['page']}-{i}") for i in range(kwargs["page_size"])],
        }

    _patch_search(monkeypatch, handler)
    _login(client_fixture, user_payload_fixture)

    response = client_fixture.get(
        f"{API}/attractions",
        params={"city_name": "成都", "keyword": "古镇", "page": 2, "page_size": 20},
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["page"], body["page_size"]) == (2, 20)
    assert len(body["items"]) == 20
    assert body["total"] == 600
    assert body["has_more"] is True
    assert calls[0] == (2, 20)

    # 最后一页:page * page_size >= count -> has_more False
    total["value"] = "30"
    last_page = client_fixture.get(
        f"{API}/attractions",
        params={"city_name": "成都", "keyword": "古镇", "page": 2, "page_size": 20},
    ).json()
    assert last_page["has_more"] is False

    # page_size 上限 20,超出直接 422
    assert (
        client_fixture.get(
            f"{API}/attractions",
            params={"city_name": "成都", "keyword": "古镇", "page": 1, "page_size": 50},
        ).status_code
        == 422
    )


def test_attraction_detail(monkeypatch, client_fixture, user_payload_fixture):
    async def fake_get_poi_detail(poi_id):
        return _poi(poi_id, name="杜甫草堂")

    monkeypatch.setattr(amap_client, "get_poi_detail", fake_get_poi_detail)
    _login(client_fixture, user_payload_fixture)

    response = client_fixture.get(f"{API}/attractions/B001")

    assert response.status_code == 200
    body = response.json()
    assert body["poi_id"] == "B001"
    assert body["name"] == "杜甫草堂"
    assert body["address"] == "四川省成都市青羊区"
    assert body["cost"] == "60.00"
    assert body["tags"] == ["风景名胜", "公园广场"]
    # title 是空数组 -> None
    assert body["photos"] == [{"url": "http://store.is.autonavi.com/B001.jpg", "title": None}]
    # location 后端保留返回,前端不展示
    assert body["location"] == {"lng": 104.077761, "lat": 30.6511}


def test_missing_fields_stay_none(monkeypatch, client_fixture, user_payload_fixture):
    dirty_poi = {
        "id": "B404",
        "name": "缺失字段景点",
        "type": [],
        "address": [],
        "tel": [],
        "location": [],
        "biz_ext": {"rating": [], "cost": []},
        "photos": [],
    }

    def handler(**kwargs):
        return {"status": "1", "count": [], "pois": [dirty_poi]}

    _patch_search(monkeypatch, handler)

    async def fake_get_poi_detail(poi_id):
        return dirty_poi

    monkeypatch.setattr(amap_client, "get_poi_detail", fake_get_poi_detail)
    _login(client_fixture, user_payload_fixture)

    listing = client_fixture.get(f"{API}/attractions", params={"city_name": "成都"}).json()
    summary = listing["items"][0]
    assert summary["cover_photo"] is None
    assert summary["rating"] is None
    assert summary["tags"] == []
    assert listing["total"] is None

    detail = client_fixture.get(f"{API}/attractions/B404").json()
    assert detail["photos"] == []
    assert detail["address"] is None
    assert detail["cost"] is None
    assert detail["tags"] == []
    assert detail["location"] is None
    # 空数组绝不能原样出现在字符串字段里(Pydantic 会直接 500)
    assert detail["poi_id"] == "B404"
    assert detail["name"] == "缺失字段景点"

    # 空结果:高德没有匹配 POI -> 空列表 + total 0,而不是 500
    _patch_search(monkeypatch, lambda **kwargs: {"status": "1", "count": "0", "pois": []})
    empty = client_fixture.get(
        f"{API}/attractions", params={"city_name": "不存在的城市", "keyword": "古镇"}
    ).json()
    assert empty["items"] == []
    assert empty["total"] == 0
    assert empty["has_more"] is False


def test_amap_failure_returns_controlled_error(monkeypatch, client_fixture, user_payload_fixture):
    async def broken_search_pois(city_name, keyword=None, category=None, page=1, page_size=10):
        raise amap_client.AmapError(amap_client.UNAVAILABLE_MESSAGE)

    monkeypatch.setattr(amap_client, "search_pois", broken_search_pois)
    _login(client_fixture, user_payload_fixture)

    listing = client_fixture.get(f"{API}/attractions", params={"city_name": "成都"})
    assert listing.status_code == 502
    assert listing.json()["detail"] == "景点服务暂时不可用"
    assert "restapi" not in listing.text.lower()
    assert "key" not in listing.text.lower()

    async def broken_get_poi_detail(poi_id):
        raise amap_client.AmapError(amap_client.UNAVAILABLE_MESSAGE)

    monkeypatch.setattr(amap_client, "get_poi_detail", broken_get_poi_detail)
    detail = client_fixture.get(f"{API}/attractions/B001")
    assert detail.status_code == 502
    assert detail.json()["detail"] == "景点服务暂时不可用"

    async def missing_get_poi_detail(poi_id):
        raise amap_client.AmapNotFoundError(amap_client.NOT_FOUND_MESSAGE)

    monkeypatch.setattr(amap_client, "get_poi_detail", missing_get_poi_detail)
    not_found = client_fixture.get(f"{API}/attractions/不存在的POI")
    assert not_found.status_code == 404
    assert not_found.json()["detail"] == "未找到该景点信息"

    # 未登录一律 401
    client_fixture.cookies.clear()
    assert client_fixture.get(f"{API}/attractions", params={"city_name": "成都"}).status_code == 401
    assert client_fixture.get(f"{API}/attractions/B001").status_code == 401
