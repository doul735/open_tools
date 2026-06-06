from datetime import datetime, timedelta

import pytest

from open_gil.errors import PLACE_AMBIGUOUS, OpenGilError
from open_gil.models import PlanRequest, ResolvedPlace, RouteCandidate
from open_gil.planner import Planner
from open_gil.timeutils import DEFAULT_TZ


ORIGIN = ResolvedPlace(name="출발", lat=37.4, lon=126.6)
DEST = ResolvedPlace(name="도착", lat=37.5, lon=127.1)


class FakeClient:
    def __init__(self, *, duration_minutes: int = 20) -> None:
        self.duration_minutes = duration_minutes
        self.route_calls: list[datetime] = []

    def search_poi(self, query: str, *, count: int = 5):
        if query == "ambiguous":
            return [
                ResolvedPlace(name="후보1", lat=37.1, lon=127.1),
                ResolvedPlace(name="후보2", lat=37.2, lon=127.2),
            ]
        return [ORIGIN if query == "origin" else DEST]

    def search_transit_route(self, origin, destination, departure_at: datetime) -> RouteCandidate:
        self.route_calls.append(departure_at)
        duration = self.duration_minutes * 60
        return RouteCandidate(
            depart_at=departure_at,
            arrive_at=departure_at + timedelta(seconds=duration),
            duration_seconds=duration,
            transfer_count=1,
            total_walk_time_seconds=300,
            route_summary="도보 -> 지하철 1호선 -> 도보",
            route_signature="SUBWAY:1:origin>dest",
            legs=[],
        )


def test_event_at_applies_15_minute_buffer_and_selects_latest_qualifying() -> None:
    client = FakeClient(duration_minutes=20)
    planner = Planner(client)
    request = PlanRequest.model_validate(
        {
            "origin": {"lat": ORIGIN.lat, "lon": ORIGIN.lon, "label": ORIGIN.name},
            "destination": {"lat": DEST.lat, "lon": DEST.lon, "label": DEST.name},
            "event_at": "2026-06-06 12:00",
        }
    )

    result = planner.plan(request)

    recommended = next(candidate for candidate in result.candidates if candidate.kind == "recommended")
    assert result.target_arrival_at == datetime(2026, 6, 6, 11, 45, tzinfo=DEFAULT_TZ)
    assert recommended.depart_at == datetime(2026, 6, 6, 11, 25, tzinfo=DEFAULT_TZ)
    assert recommended.arrive_at == datetime(2026, 6, 6, 11, 45, tzinfo=DEFAULT_TZ)
    assert [candidate.kind for candidate in result.candidates] == ["recommended"]
    assert result.search_strategy == "quota_safe_target_arrival_single_lookup"
    assert result.route_api_calls_used == 1
    assert client.route_calls == [datetime(2026, 6, 6, 9, 45, tzinfo=DEFAULT_TZ)]


def test_arrive_by_has_no_extra_buffer() -> None:
    planner = Planner(FakeClient(duration_minutes=20))
    request = PlanRequest.model_validate(
        {
            "origin": {"lat": ORIGIN.lat, "lon": ORIGIN.lon},
            "destination": {"lat": DEST.lat, "lon": DEST.lon},
            "arrive_by": "2026-06-06 12:00",
        }
    )

    result = planner.plan(request)

    recommended = next(candidate for candidate in result.candidates if candidate.kind == "recommended")
    assert result.arrival_buffer_minutes == 0
    assert recommended.depart_at == datetime(2026, 6, 6, 11, 40, tzinfo=DEFAULT_TZ)
    assert result.search_strategy == "quota_safe_target_arrival_single_lookup"


def test_depart_at_returns_single_fixed_candidate() -> None:
    planner = Planner(FakeClient(duration_minutes=40))
    request = PlanRequest.model_validate(
        {
            "origin": {"lat": ORIGIN.lat, "lon": ORIGIN.lon},
            "destination": {"lat": DEST.lat, "lon": DEST.lon},
            "depart_at": "2026-06-06 09:00",
        }
    )

    result = planner.plan(request)

    assert result.target_arrival_at is None
    assert len(result.candidates) == 1
    assert result.candidates[0].kind == "fixed"
    assert result.candidates[0].arrive_at == datetime(2026, 6, 6, 9, 40, tzinfo=DEFAULT_TZ)


def test_ambiguous_place_without_selector_returns_structured_error() -> None:
    planner = Planner(FakeClient())
    request = PlanRequest.model_validate(
        {
            "origin": "ambiguous",
            "destination": {"lat": DEST.lat, "lon": DEST.lon},
            "depart_at": "2026-06-06 09:00",
        }
    )

    with pytest.raises(OpenGilError) as exc:
        planner.plan(request)

    assert exc.value.code == PLACE_AMBIGUOUS
    assert len(exc.value.details["candidates"]) == 2
