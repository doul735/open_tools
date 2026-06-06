from datetime import datetime

from open_gil.formatters import format_plan_text
from open_gil.models import PlanResult, ResolvedPlace, RouteCandidate, RouteLeg, VerificationLinks
from open_gil.timeutils import DEFAULT_TZ


def test_format_plan_text_names_same_stop_transfer() -> None:
    departure = datetime(2026, 6, 8, 11, 4, tzinfo=DEFAULT_TZ)
    candidate = RouteCandidate(
        kind="recommended",
        depart_at=departure,
        arrive_at=datetime(2026, 6, 8, 12, 45, tzinfo=DEFAULT_TZ),
        duration_seconds=6060,
        route_summary="도보 -> 버스 광역:M6450 -> 같은 정류장 환승 -> 버스 간선:360",
        route_signature="BUS:M6450|BUS:360",
        legs=[
            RouteLeg(
                mode="WALK",
                start_name="출발지",
                end_name="송도달빛축제공원역",
                section_time_seconds=120,
                distance_meters=150,
            ),
            RouteLeg(
                mode="BUS",
                route_name="광역:M6450",
                start_name="송도달빛축제공원역",
                end_name="선릉역",
                section_time_seconds=4247,
            ),
            RouteLeg(
                mode="WALK",
                start_name="선릉역",
                end_name="선릉역",
                section_time_seconds=0,
                distance_meters=0,
            ),
            RouteLeg(
                mode="BUS",
                route_name="간선:360",
                start_name="선릉역",
                end_name="도착지",
                section_time_seconds=823,
            ),
        ],
    )
    result = PlanResult(
        origin=ResolvedPlace(name="송도달빛축제공원역", lat=37.4, lon=126.6),
        destination=ResolvedPlace(name="올림픽홀", lat=37.5, lon=127.1),
        time_mode="event_at",
        requested_time=datetime(2026, 6, 8, 13, 0, tzinfo=DEFAULT_TZ),
        target_arrival_at=datetime(2026, 6, 8, 12, 45, tzinfo=DEFAULT_TZ),
        arrival_buffer_minutes=15,
        candidates=[candidate],
        verification_links=VerificationLinks(naver_maps="nmap://route/public", kakao_map="kakao"),
    )

    text = format_plan_text(result)

    assert "같은 정류장 환승: 선릉역에서 버스 광역:M6450 하차 후 버스 간선:360 탑승" in text
    assert "도보: 선릉역 -> 선릉역" not in text
    assert "도보: 출발지 -> 송도달빛축제공원역" in text
    assert "버스 광역:M6450: 송도달빛축제공원역 승차 -> 선릉역 하차" in text
    assert "버스 간선:360: 선릉역 승차 -> 올림픽홀 하차" in text
