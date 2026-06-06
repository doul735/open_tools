from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
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
from .timeutils import candidate_departures, parse_local_datetime
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
        else:
            buffer_minutes = 15 if request.time_mode == "event_at" else 0
            target_arrival = requested_time - timedelta(minutes=buffer_minutes)
            candidates = self._target_arrival_candidates(origin, destination, target_arrival)

        return PlanResult(
            origin=origin,
            destination=destination,
            time_mode=request.time_mode,
            requested_time=requested_time,
            target_arrival_at=target_arrival,
            arrival_buffer_minutes=buffer_minutes,
            candidates=candidates,
            verification_links=build_verification_links(origin, destination),
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

    def _target_arrival_candidates(
        self,
        origin: ResolvedPlace,
        destination: ResolvedPlace,
        target_arrival,
    ) -> list[RouteCandidate]:
        probes = candidate_departures(target_arrival, hours=3, step_minutes=5)
        found: list[RouteCandidate] = []
        blocking_error: OpenGilError | None = None

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.client.search_transit_route, origin, destination, depart_at): depart_at
                for depart_at in probes
            }
            for future in as_completed(futures):
                try:
                    candidate = future.result()
                except OpenGilError as exc:
                    if exc.code == ROUTE_NOT_FOUND:
                        continue
                    blocking_error = exc
                    break
                candidate.meets_target = candidate.arrive_at <= target_arrival
                found.append(candidate)

        if blocking_error is not None:
            raise blocking_error
        if not found:
            raise OpenGilError(
                ROUTE_NOT_FOUND,
                "탐색 범위 안에서 대중교통 경로를 찾지 못했습니다.",
                "출발지/도착지를 더 구체적으로 입력하거나 더 이른 시간을 시도하세요.",
            )

        deduped = _dedupe_candidates(found)
        qualifying = [candidate for candidate in deduped if candidate.arrive_at <= target_arrival]
        if not qualifying:
            raise OpenGilError(
                ROUTE_NOT_FOUND,
                "목표 도착시각까지 도착하는 대중교통 후보를 찾지 못했습니다.",
                "더 이른 출발 가능 시간을 입력하거나 도착 기준을 조정하세요.",
                details={
                    "target_arrival_at": target_arrival.isoformat(),
                    "earliest_candidate_arrival_at": min(c.arrive_at for c in deduped).isoformat(),
                },
            )

        recommended = max(qualifying, key=lambda candidate: candidate.depart_at)
        selected: list[RouteCandidate] = []
        rec_index = deduped.index(recommended)
        if rec_index > 0:
            previous = deduped[rec_index - 1].model_copy()
            previous.kind = "previous"
            selected.append(previous)
        recommended_copy = recommended.model_copy()
        recommended_copy.kind = "recommended"
        selected.append(recommended_copy)
        if rec_index + 1 < len(deduped):
            next_candidate = deduped[rec_index + 1].model_copy()
            next_candidate.kind = "next"
            selected.append(next_candidate)
        return selected


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


def _dedupe_candidates(candidates: list[RouteCandidate]) -> list[RouteCandidate]:
    by_key: dict[tuple[str, str], RouteCandidate] = {}
    for candidate in sorted(candidates, key=lambda item: item.depart_at):
        key = (candidate.route_signature, candidate.arrive_at.isoformat(timespec="minutes"))
        existing = by_key.get(key)
        if existing is None or candidate.depart_at > existing.depart_at:
            by_key[key] = candidate
    return sorted(by_key.values(), key=lambda item: item.depart_at)
