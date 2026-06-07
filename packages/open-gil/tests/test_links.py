from open_gil.links import build_verification_links
from open_gil.models import ResolvedPlace


def test_verification_links_use_public_transit() -> None:
    links = build_verification_links(
        ResolvedPlace(name="출발", lat=37.1, lon=127.1),
        ResolvedPlace(name="도착", lat=37.2, lon=127.2),
    )

    assert links.naver_maps.startswith("nmap://route/public?")
    assert "by=publictransit" in links.kakao_map

