import os
from datetime import datetime

import pytest

from open_gil.config import load_api_key
from open_gil.models import ResolvedPlace
from open_gil.timeutils import DEFAULT_TZ
from open_gil.tmap import TMapClient


@pytest.mark.skipif(not os.environ.get("TMAP_API_KEY"), reason="TMAP_API_KEY is not set")
def test_live_tmap_transit_route() -> None:
    client = TMapClient(load_api_key())
    try:
        candidate = client.search_transit_route(
            ResolvedPlace(name="강남역", lat=37.497952, lon=127.027619),
            ResolvedPlace(name="서울역", lat=37.554678, lon=126.970606),
            datetime(2026, 6, 6, 9, 0, tzinfo=DEFAULT_TZ),
        )
    finally:
        client.close()

    assert candidate.duration_seconds > 0

