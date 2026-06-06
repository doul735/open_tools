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
        for leg in recommended.legs:
            lines.append(f"- {_format_leg(leg)}")
        if recommended.service_notes:
            for note in recommended.service_notes:
                lines.append(f"- 운행 참고: {note}")
        lines.append("")

    if result.planning_note:
        lines.append(f"탐색 방식: {result.planning_note}")
        lines.append("")

    lines.append("확인 링크")
    lines.append(f"- 네이버지도: {result.verification_links.naver_maps}")
    lines.append(f"- 카카오맵: {result.verification_links.kakao_map}")
    lines.append("")
    lines.append(result.disclaimer)
    return "\n".join(lines).rstrip() + "\n"


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
    return [" / ".join(parts), f"  경로: {candidate.route_summary}"]


def _format_leg(leg: RouteLeg) -> str:
    route = f" {leg.route_name}" if leg.route_name else ""
    place = ""
    if leg.start_name or leg.end_name:
        place = f": {leg.start_name or '?'} -> {leg.end_name or '?'}"
    duration = f" ({_fmt_duration(leg.section_time_seconds)})" if leg.section_time_seconds else ""
    return f"{_mode_ko(leg.mode)}{route}{place}{duration}"


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
