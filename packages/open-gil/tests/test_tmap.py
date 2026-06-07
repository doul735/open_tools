import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from open_gil.cache import RouteCache
from open_gil.errors import AUTH_FORBIDDEN, AUTH_INVALID, QUOTA_EXCEEDED, OpenGilError
from open_gil.models import ResolvedPlace
from open_gil.timeutils import DEFAULT_TZ
from open_gil.tmap import TMapClient, parse_poi_response, parse_transit_response


FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_poi_response() -> None:
    places = parse_poi_response(_fixture("tmap_poi_success.json"))

    assert len(places) == 2
    assert places[0].name == "송도달빛축제공원역"
    assert places[0].lat == pytest.approx(37.407722)
    assert places[0].lon == pytest.approx(126.625572)
    assert places[1].address == "서울특별시 송파구 방이동"


def test_parse_transit_response() -> None:
    departure = datetime(2026, 6, 6, 11, 0, tzinfo=DEFAULT_TZ)

    candidate = parse_transit_response(_fixture("tmap_route_success.json"), departure)

    assert candidate.arrive_at == datetime(2026, 6, 6, 11, 40, tzinfo=DEFAULT_TZ)
    assert candidate.transfer_count == 1
    assert candidate.total_fare == 3250
    assert "인천1호선" in candidate.route_summary
    assert "SUBWAY:I1" in candidate.route_signature


def test_route_summary_names_same_stop_transfer() -> None:
    data = _fixture("tmap_route_success.json")
    data["metaData"]["plan"]["itineraries"][0]["legs"] = [
        {
            "mode": "BUS",
            "route": "광역:M6450",
            "routeId": "M6450",
            "sectionTime": 4247,
            "start": {"name": "송도달빛축제공원역"},
            "end": {"name": "선릉역"},
        },
        {
            "mode": "WALK",
            "sectionTime": 0,
            "distance": 0,
            "start": {"name": "선릉역"},
            "end": {"name": "선릉역"},
        },
        {
            "mode": "BUS",
            "route": "간선:360",
            "routeId": "360",
            "sectionTime": 823,
            "start": {"name": "선릉역"},
            "end": {"name": "잠실트리지움아파트앞"},
        },
    ]

    candidate = parse_transit_response(data, datetime(2026, 6, 6, 11, 0, tzinfo=DEFAULT_TZ))

    assert candidate.route_summary == "버스 광역:M6450 -> 같은 정류장 환승 -> 버스 간선:360"


def test_tmap_client_sends_route_request_and_uses_cache(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["appkey"] == "test-key"
        assert request.url.path == "/transit/routes"
        payload = json.loads(request.content.decode())
        assert payload["searchDttm"] == "202606061100"
        return httpx.Response(200, json=_fixture("tmap_route_success.json"))

    transport = httpx.MockTransport(handler)
    client = TMapClient(
        "test-key",
        http_client=httpx.Client(transport=transport),
        cache=RouteCache(tmp_path / "cache.json"),
    )
    origin = ResolvedPlace(name="origin", lat=37.4, lon=126.6)
    dest = ResolvedPlace(name="dest", lat=37.5, lon=127.1)
    departure = datetime(2026, 6, 6, 11, 0, tzinfo=DEFAULT_TZ)

    first = client.search_transit_route(origin, dest, departure)
    second = client.search_transit_route(origin, dest, departure)

    assert first.arrive_at == second.arrive_at
    assert calls == 1


def test_tmap_auth_error_is_specific() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "invalid appKey"})

    client = TMapClient("bad-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(OpenGilError) as exc:
        client.search_poi("강남역")

    assert exc.value.code == AUTH_INVALID
    assert "API 키" in exc.value.message
    assert "unset TMAP_API_KEY 후 open-gil setup" in (exc.value.remediation or "")


def test_tmap_forbidden_error_is_permission_specific() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="Forbidden")

    client = TMapClient("restricted-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(OpenGilError) as exc:
        client.search_poi("강남역")

    assert exc.value.code == AUTH_FORBIDDEN
    assert "권한" in exc.value.message


def test_tmap_quota_error_is_specific() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "Limit Exceeded"})

    client = TMapClient("test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(OpenGilError) as exc:
        client.search_poi("강남역")

    assert exc.value.code == QUOTA_EXCEEDED
    assert "한도" in exc.value.message
