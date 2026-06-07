import json
from pathlib import Path

import httpx
import pytest

from open_gil.cache import RouteCache
from open_gil.errors import AUTH_INVALID, QUOTA_EXCEEDED, OpenGilError
from open_gil.kakao import KakaoLocalClient, parse_address_response, parse_keyword_response


FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_keyword_response() -> None:
    places = parse_keyword_response(_fixture("kakao_keyword_success.json"))

    assert len(places) == 1
    assert places[0].name == "내수동교회"
    assert places[0].lat == pytest.approx(37.5727687)
    assert places[0].lon == pytest.approx(126.9707238)
    assert places[0].address == "서울 종로구 경희궁2길 5-6"
    assert places[0].source == "kakao_local_keyword"


def test_parse_address_response_prefers_building_name() -> None:
    places = parse_address_response(_fixture("kakao_address_success.json"), query="인천 연수구 센트럴로 415")

    assert len(places) == 1
    assert places[0].name == "힐스테이트송도더테라스"
    assert places[0].lat == pytest.approx(37.4105748)
    assert places[0].lon == pytest.approx(126.6266089)
    assert places[0].address == "인천 연수구 센트럴로 415"
    assert places[0].source == "kakao_local_address"


def test_kakao_client_searches_keyword_first_for_place_name(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.headers["authorization"] == "KakaoAK kakao-key"
        assert request.url.path == "/v2/local/search/keyword.json"
        return httpx.Response(200, json=_fixture("kakao_keyword_success.json"))

    client = KakaoLocalClient(
        "kakao-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        cache=RouteCache(tmp_path / "cache.json"),
    )

    places = client.search_poi("내수동교회")

    assert calls == ["/v2/local/search/keyword.json"]
    assert places[0].name == "내수동교회"


def test_kakao_client_searches_address_first_for_address_like_query(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.url.path == "/v2/local/search/address.json"
        return httpx.Response(200, json=_fixture("kakao_address_success.json"))

    client = KakaoLocalClient(
        "kakao-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        cache=RouteCache(tmp_path / "cache.json"),
    )

    places = client.search_poi("인천 연수구 센트럴로 415")

    assert calls == ["/v2/local/search/address.json"]
    assert places[0].name == "힐스테이트송도더테라스"


def test_kakao_auth_error_is_specific() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "invalid appKey"})

    client = KakaoLocalClient("bad-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(OpenGilError) as exc:
        client.search_poi("강남역")

    assert exc.value.code == AUTH_INVALID
    assert "Kakao" in exc.value.message


def test_kakao_quota_error_is_specific() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "quota exceeded"})

    client = KakaoLocalClient("kakao-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(OpenGilError) as exc:
        client.search_poi("강남역")

    assert exc.value.code == QUOTA_EXCEEDED
    assert "한도" in exc.value.message
