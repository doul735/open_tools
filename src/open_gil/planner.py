from __future__ import annotations

from datetime import timedelta
from typing import Callable

from pydantic import ValidationError

from .errors import (
    INPUT_INVALID,
    PLACE_AMBIGUOUS,
    ROUTE_NOT_FOUND,
    OpenGilError,
)
from .links import build_verification_links
from .models import PlanRequest, PlanResult, PlaceInput, ResolvedPlace, RouteCandidate
from .timeutils import parse_local_datetime
from .tmap import TMapClient


PlaceSelector = Callable[[str, str, list[ResolvedPlace]], ResolvedPlace]


class Planner:
    def __init__(
        self,
        client: TMapClient,
        *,
        place_selector: PlaceSelector | None = None,
        max_workers: int = 4,
    ) -> None:
        self.client = client
        self.place_selector = place_selector
        self.max_workers = max_workers

    def plan(self, request: PlanRequest) -> PlanResult:
        origin = self._resolve_place(request.origin, role="출발지")
        destination = self._resolve_place(request.destination, role="도착지")
        requested_time = parse_local_datetime(request.time_value)

        if request.time_mode == "depart_at":
            candidate = self.client.search_transit_route(origin, destination, requested_time)
            candidate.kind = "fixed"
            candidate.meets_target = None
            candidates = [candidate]
            target_arrival = None
            buffer_minutes = 0
            search_strategy = "fixed_departure_single_lookup"
            planning_note = None
        else:
            buffer_minutes = 15 if request.time_mode == "event_at" else 0
            target_arrival = requested_time - timedelta(minutes=buffer_minutes)
            candidates = [self._quota_safe_target_candidate(origin, destination, target_arrival)]
            search_strategy = "quota_safe_target_arrival_single_lookup"
            planning_note = (
                "하루 호출 제한을 고려해 TMAP 경로 조회 1회로 총 소요시간을 받아 목표 도착시각에서 역산했습니다. "
                "이전/다음 수단 전수 탐색은 실행하지 않았습니다."
            )

        return PlanResult(
            origin=origin,
            destination=destination,
            time_mode=request.time_mode,
            requested_time=requested_time,
            target_arrival_at=target_arrival,
            arrival_buffer_minutes=buffer_minutes,
            candidates=candidates,
            verification_links=build_verification_links(origin, destination),
            search_strategy=search_strategy,
            route_api_calls_used=1,
            planning_note=planning_note,
        )

    def _resolve_place(self, place: PlaceInput, *, role: str) -> ResolvedPlace:
        if place.has_coordinates:
            assert place.lat is not None and place.lon is not None
            return ResolvedPlace(
                name=place.display_label,
                lat=place.lat,
                lon=place.lon,
                source="input_coordinates",
            )

        assert place.name is not None
        candidates = self.client.search_poi(place.name, count=5)
        if len(candidates) == 1:
            return candidates[0]
        if self.place_selector:
            return self.place_selector(role, place.name, candidates)
        raise OpenGilError(
            PLACE_AMBIGUOUS,
            f"{role} 장소 후보가 여러 개입니다: {place.name}",
            "후보 중 하나를 선택하거나 좌표를 직접 입력하세요.",
            details={"role": role, "query": place.name, "candidates": [c.model_dump() for c in candidates]},
        )

    def _quota_safe_target_candidate(
        self,
        origin: ResolvedPlace,
        destination: ResolvedPlace,
        target_arrival,
    ) -> RouteCandidate:
        probe_departure = target_arrival - timedelta(hours=2)
        candidate = self.client.search_transit_route(origin, destination, probe_departure)
        recommended_departure = target_arrival - timedelta(seconds=candidate.duration_seconds)
        recommended = candidate.model_copy(
            update={
                "kind": "recommended",
                "depart_at": recommended_departure,
                "arrive_at": target_arrival,
                "meets_target": True,
                "service_notes": [
                    *candidate.service_notes,
                    "단일 TMAP 조회 기반 역산 추천입니다. 이전/다음 수단은 조회하지 않았습니다.",
                ],
            }
        )
        return recommended


def plan_request_from_mapping(data: dict) -> PlanRequest:
    try:
        return PlanRequest.model_validate(data)
    except ValidationError as exc:
        raise OpenGilError(
            INPUT_INVALID,
            "입력값 형식이 올바르지 않습니다.",
            "origin, destination, 그리고 depart_at/event_at/arrive_by 중 하나를 입력하세요.",
            debug_detail=str(exc),
        ) from exc
