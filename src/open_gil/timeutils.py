from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .errors import OpenGilError, TIME_INVALID


DEFAULT_TZ = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    return datetime.now(DEFAULT_TZ)


def parse_local_datetime(value: str | datetime, *, now: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=DEFAULT_TZ)
        return value.astimezone(DEFAULT_TZ)

    raw = str(value).strip()
    if not raw:
        raise _invalid_time(value)

    iso_raw = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_raw)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=DEFAULT_TZ)
        return parsed.astimezone(DEFAULT_TZ)

    for fmt in ("%Y%m%d%H%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=DEFAULT_TZ)
        except ValueError:
            pass

    dated_korean = re.fullmatch(
        r"(\d{4}-\d{2}-\d{2})\s*(오전|오후)?\s*(\d{1,2})(?:[:시]\s*(\d{1,2}))?\s*분?",
        raw,
    )
    if dated_korean:
        date_part, meridiem, hour_raw, minute_raw = dated_korean.groups()
        hour = _apply_meridiem(int(hour_raw), meridiem)
        minute = int(minute_raw or 0)
        try:
            return datetime.strptime(date_part, "%Y-%m-%d").replace(
                hour=hour, minute=minute, tzinfo=DEFAULT_TZ
            )
        except ValueError as exc:
            raise _invalid_time(value) from exc

    time_only = re.fullmatch(
        r"(오전|오후)?\s*(\d{1,2})(?:[:시]\s*(\d{1,2}))?\s*분?",
        raw,
    )
    if time_only:
        meridiem, hour_raw, minute_raw = time_only.groups()
        hour = _apply_meridiem(int(hour_raw), meridiem)
        minute = int(minute_raw or 0)
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise _invalid_time(value)
        base = now or now_kst()
        return base.astimezone(DEFAULT_TZ).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

    raise _invalid_time(value)


def tmap_search_dttm(value: datetime) -> str:
    return value.astimezone(DEFAULT_TZ).strftime("%Y%m%d%H%M")


def candidate_departures(target_arrival: datetime, *, hours: int = 3, step_minutes: int = 5) -> list[datetime]:
    start = target_arrival - timedelta(hours=hours)
    count = int((hours * 60) / step_minutes) + 1
    return [start + timedelta(minutes=step_minutes * index) for index in range(count)]


def _apply_meridiem(hour: int, meridiem: str | None) -> int:
    if meridiem == "오전":
        if hour == 12:
            return 0
        return hour
    if meridiem == "오후":
        if hour < 12:
            return hour + 12
        return hour
    return hour


def _invalid_time(value: object) -> OpenGilError:
    return OpenGilError(
        TIME_INVALID,
        f"시간 값을 해석할 수 없습니다: {value}",
        "예: 13:00, 2026-06-06 13:00, 202606061300 형식으로 입력하세요.",
    )

