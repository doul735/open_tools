from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .errors import ok_envelope
from .models import PlanResult, RouteCandidate, RouteLeg


def result_json(result: PlanResult) -> str:
    payload = ok_envelope(result.model_dump(mode="json"))
    return json.dumps(payload, ensure_ascii=False, indent=2)


def error_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def format_plan_text(result: PlanResult) -> str:
    lines: list[str] = []
    lines.append(f"{result.origin.name} -> {result.destination.name}")
    if result.time_mode == "depart_at":
        lines.append(f"기준: {_fmt_dt(result.requested_time)} 출발")
    elif result.time_mode == "event_at":
        assert result.target_arrival_at is not None
        lines.append(
            f"기준: {_fmt_dt(result.requested_time)} 일정 시작, 목표 도착 {_fmt_dt(result.target_arrival_at)}"
        )
    else:
        assert result.target_arrival_at is not None
        lines.append(f"기준: {_fmt_dt(result.target_arrival_at)}까지 도착")

    lines.append("")
    for candidate in result.candidates:
        lines.extend(_format_candidate(candidate))
        lines.append("")

    recommended = next((candidate for candidate in result.candidates if candidate.kind == "recommended"), None)
    if recommended is None and result.candidates:
        recommended = result.candidates[0]
    if recommended:
        lines.append("추천 경로 상세")
        for index, line in enumerate(
            _format_legs(
                recommended.legs,
                origin_name=result.origin.name,
                destination_name=result.destination.name,
            ),
            start=1,
        ):
            lines.append(f"{index}. {line}")
        if recommended.service_notes:
            for note in recommended.service_notes:
                lines.append(f"- 운행 참고: {note}")
        lines.append("")

    if result.planning_note:
        lines.append(f"탐색 방식: {result.planning_note}")
        lines.append("")

    coordinate_note = _coordinate_source_note(result)
    if coordinate_note:
        lines.append(coordinate_note)
        lines.append("")

    lines.append("확인 링크")
    lines.append(f"- 네이버지도: {result.verification_links.naver_maps}")
    lines.append(f"- 카카오맵: {result.verification_links.kakao_map}")
    lines.append("")
    lines.append(result.disclaimer)
    return "\n".join(lines).rstrip() + "\n"


def _coordinate_source_note(result: PlanResult) -> str | None:
    sources: list[str] = []
    if result.origin.source.startswith("kakao_local"):
        sources.append(f"출발지 {_source_label(result.origin.source)}")
    if result.destination.source.startswith("kakao_local"):
        sources.append(f"도착지 {_source_label(result.destination.source)}")
    if not sources:
        return None
    return (
        "좌표 확인: "
        + ", ".join(sources)
        + ". 경로/시간/요금/환승 계산은 TMAP Transit API 결과만 사용했습니다."
    )


def _source_label(source: str) -> str:
    return {
        "kakao_local_keyword": "Kakao Local 키워드 검색",
        "kakao_local_address": "Kakao Local 주소 검색",
    }.get(source, source)


def _format_candidate(candidate: RouteCandidate) -> list[str]:
    label = {
        "previous": "이전 수단",
        "recommended": "추천",
        "next": "다음 수단",
        "fixed": "고정 출발",
        "candidate": "후보",
    }[candidate.kind]
    target_note = ""
    if candidate.meets_target is True:
        target_note = "목표 도착 가능"
    elif candidate.meets_target is False:
        target_note = "목표보다 늦을 수 있음"
    parts = [
        f"{label}: {_fmt_dt(candidate.depart_at)} 출발 -> {_fmt_dt(candidate.arrive_at)} 도착",
        f"소요 {_fmt_duration(candidate.duration_seconds)}",
    ]
    if candidate.transfer_count is not None:
        parts.append(f"환승 {candidate.transfer_count}회")
    if candidate.total_walk_time_seconds is not None:
        parts.append(f"도보 {_fmt_duration(candidate.total_walk_time_seconds)}")
    if candidate.total_fare is not None:
        parts.append(f"요금 {candidate.total_fare:,}원")
    if target_note:
        parts.append(target_note)
    return [" / ".join(parts), f"  경로: {_display_route_summary(candidate)}"]


def _format_legs(legs: list[RouteLeg], *, origin_name: str, destination_name: str) -> list[str]:
    lines: list[str] = []
    for index, leg in enumerate(legs):
        previous_leg = legs[index - 1] if index > 0 else None
        next_leg = legs[index + 1] if index + 1 < len(legs) else None
        formatted = _format_leg_with_context(
            leg,
            previous_leg,
            next_leg,
            origin_name=origin_name,
            destination_name=destination_name,
        )
        if formatted:
            lines.append(formatted)
    return lines


def _display_route_summary(candidate: RouteCandidate) -> str:
    if not candidate.legs:
        return candidate.route_summary

    labels: list[str] = []
    for index, leg in enumerate(candidate.legs):
        previous_leg = candidate.legs[index - 1] if index > 0 else None
        next_leg = candidate.legs[index + 1] if index + 1 < len(candidate.legs) else None
        if _is_same_stop_transfer(leg, previous_leg, next_leg):
            labels.append("같은 정류장 환승")
        elif leg.mode == "WALK":
            labels.append("도보")
        else:
            labels.append(_vehicle_label(leg))
    return " -> ".join(labels)


def _format_leg_with_context(
    leg: RouteLeg,
    previous_leg: RouteLeg | None,
    next_leg: RouteLeg | None,
    *,
    origin_name: str,
    destination_name: str,
) -> str | None:
    if _is_zero_transfer_walk(leg) and previous_leg and next_leg:
        if _is_same_stop_transfer(leg, previous_leg, next_leg):
            station = leg.start_name or leg.end_name or previous_leg.end_name or next_leg.start_name or "같은 정류장"
            return (
                f"같은 정류장 환승: {station}에서 "
                f"{_vehicle_label(previous_leg)} 하차 후 {_vehicle_label(next_leg)} 탑승"
            )

    if leg.mode == "WALK":
        if _is_zero_transfer_walk(leg):
            return None
        place = _place_arrow(leg, origin_name=origin_name, destination_name=destination_name)
        detail = _walk_detail(leg)
        return f"도보: {place}{detail}"

    place = _boarding_arrow(leg, origin_name=origin_name, destination_name=destination_name)
    duration = f" ({_fmt_duration(leg.section_time_seconds)})" if leg.section_time_seconds else ""
    return f"{_vehicle_label(leg)}: {place}{duration}"


def _is_zero_transfer_walk(leg: RouteLeg) -> bool:
    return (
        leg.mode == "WALK"
        and (leg.distance_meters or 0) == 0
        and (leg.section_time_seconds or 0) == 0
        and bool(leg.start_name or leg.end_name)
    )


def _is_same_stop_transfer(
    leg: RouteLeg,
    previous_leg: RouteLeg | None,
    next_leg: RouteLeg | None,
) -> bool:
    return (
        _is_zero_transfer_walk(leg)
        and previous_leg is not None
        and next_leg is not None
        and previous_leg.mode != "WALK"
        and next_leg.mode != "WALK"
    )


def _vehicle_label(leg: RouteLeg) -> str:
    route = f" {leg.route_name}" if leg.route_name else ""
    return f"{_mode_ko(leg.mode)}{route}"


def _place_arrow(leg: RouteLeg, *, origin_name: str, destination_name: str) -> str:
    start = _display_place(leg.start_name, origin_name=origin_name, destination_name=destination_name)
    end = _display_place(leg.end_name, origin_name=origin_name, destination_name=destination_name)
    if leg.start_name == "출발지" and leg.end_name and end == origin_name:
        start = "입력 위치"
    return (
        f"{start} -> "
        f"{end}"
    )


def _boarding_arrow(leg: RouteLeg, *, origin_name: str, destination_name: str) -> str:
    return (
        f"{_display_place(leg.start_name, origin_name=origin_name, destination_name=destination_name)} 승차 -> "
        f"{_display_place(leg.end_name, origin_name=origin_name, destination_name=destination_name)} 하차"
    )


def _display_place(name: str | None, *, origin_name: str, destination_name: str) -> str:
    if name == "출발지":
        return origin_name
    if name == "도착지":
        return destination_name
    return name or "?"


def _walk_detail(leg: RouteLeg) -> str:
    details: list[str] = []
    if leg.section_time_seconds:
        details.append(_fmt_duration(leg.section_time_seconds))
    if leg.distance_meters:
        details.append(f"{leg.distance_meters}m")
    return f" ({', '.join(details)})" if details else ""


def _fmt_duration(seconds: int | None) -> str:
    if seconds is None:
        return "정보 없음"
    minutes = max(0, int(round(seconds / 60)))
    if minutes < 60:
        return f"{minutes}분"
    return f"{minutes // 60}시간 {minutes % 60}분"


def _fmt_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


def _mode_ko(mode: str) -> str:
    return {
        "WALK": "도보",
        "BUS": "버스",
        "SUBWAY": "지하철",
        "EXPRESSBUS": "고속/시외버스",
        "TRAIN": "기차",
        "AIRPLANE": "항공",
        "FERRY": "해운",
    }.get(mode, mode)
