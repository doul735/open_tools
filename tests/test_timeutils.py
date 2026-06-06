from datetime import datetime

from open_gil.timeutils import DEFAULT_TZ, parse_local_datetime, tmap_search_dttm


def test_parse_date_less_time_uses_today() -> None:
    now = datetime(2026, 6, 6, 8, 0, tzinfo=DEFAULT_TZ)

    parsed = parse_local_datetime("13:05", now=now)

    assert parsed == datetime(2026, 6, 6, 13, 5, tzinfo=DEFAULT_TZ)


def test_parse_korean_pm_time() -> None:
    parsed = parse_local_datetime("2026-06-06 오후 1시 30분")

    assert parsed == datetime(2026, 6, 6, 13, 30, tzinfo=DEFAULT_TZ)


def test_tmap_search_dttm_format() -> None:
    parsed = datetime(2026, 6, 6, 13, 5, tzinfo=DEFAULT_TZ)

    assert tmap_search_dttm(parsed) == "202606061305"


