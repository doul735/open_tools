from datetime import datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from open_gil import cli
from open_gil.models import PlanResult, ResolvedPlace, RouteCandidate, VerificationLinks
from open_gil.timeutils import DEFAULT_TZ


runner = CliRunner()


def test_plan_json_reports_missing_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TMAP_API_KEY", raising=False)
    monkeypatch.setenv("OPEN_GIL_CONFIG_PATH", str(tmp_path / "missing-config.json"))

    result = runner.invoke(
        cli.app,
        [
            "plan",
            "--json",
            "--origin-lat",
            "37.1",
            "--origin-lon",
            "127.1",
            "--destination-lat",
            "37.2",
            "--destination-lon",
            "127.2",
            "--depart-at",
            "2026-06-06 09:00",
        ],
    )

    assert result.exit_code == 1
    assert '"status": "error"' in result.stdout
    assert "OPEN_GIL_AUTH_MISSING" in result.stdout


def test_plan_reads_stdin_json_and_outputs_success(monkeypatch) -> None:
    class DummyClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def close(self) -> None:
            pass

    class DummyPlanner:
        def __init__(self, client, place_selector=None) -> None:
            self.client = client

        def plan(self, request):
            departure = datetime(2026, 6, 6, 9, 0, tzinfo=DEFAULT_TZ)
            candidate = RouteCandidate(
                kind="fixed",
                depart_at=departure,
                arrive_at=departure + timedelta(minutes=30),
                duration_seconds=1800,
                route_summary="도보 -> 지하철 2호선",
                route_signature="SUBWAY:2:a>b",
            )
            return PlanResult(
                origin=ResolvedPlace(name="출발", lat=37.1, lon=127.1),
                destination=ResolvedPlace(name="도착", lat=37.2, lon=127.2),
                time_mode=request.time_mode,
                requested_time=departure,
                arrival_buffer_minutes=0,
                candidates=[candidate],
                verification_links=VerificationLinks(naver_maps="nmap://route/public", kakao_map="kakao"),
            )

    monkeypatch.setattr(cli, "load_api_key", lambda: "key")
    monkeypatch.setattr(cli, "TMapClient", DummyClient)
    monkeypatch.setattr(cli, "Planner", DummyPlanner)

    result = runner.invoke(
        cli.app,
        ["plan", "--json"],
        input='{"origin":{"lat":37.1,"lon":127.1},"destination":{"lat":37.2,"lon":127.2},"depart_at":"2026-06-06 09:00"}',
    )

    assert result.exit_code == 0
    assert '"status": "ok"' in result.stdout
    assert '"time_mode": "depart_at"' in result.stdout
