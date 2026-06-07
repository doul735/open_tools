import json
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
        def __init__(self, client, place_selector=None, place_fallbacks=None) -> None:
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
    monkeypatch.setattr(cli, "load_kakao_rest_api_key", lambda: None)
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


def test_config_set_kakao_key_writes_config(monkeypatch, tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    monkeypatch.setenv("OPEN_GIL_CONFIG_PATH", str(config))

    result = runner.invoke(cli.app, ["config", "set-kakao-key", "kakao-key"])

    assert result.exit_code == 0
    assert "Kakao REST API 키를 저장했습니다" in result.stdout
    assert '"kakao_rest_api_key": "kakao-key"' in config.read_text(encoding="utf-8")


def test_config_show_explains_missing_tmap_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("TMAP_API_KEY", raising=False)
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    monkeypatch.setenv("OPEN_GIL_CONFIG_PATH", str(tmp_path / "missing-config.json"))

    result = runner.invoke(cli.app, ["config", "show"])

    assert result.exit_code == 0
    assert "TMAP API 키: 없음" in result.stdout
    assert "TMAP API 키가 없어 아직 경로 계산을 시작할 수 없습니다." in result.stdout
    assert 'export TMAP_API_KEY="발급받은_appKey"' in result.stdout
    assert "open-gil config set-key" in result.stdout


def test_config_show_json_does_not_expose_key_values(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TMAP_API_KEY", "secret-tmap-value")
    monkeypatch.setenv("KAKAO_REST_API_KEY", "secret-kakao-value")
    monkeypatch.setenv("OPEN_GIL_CONFIG_PATH", str(tmp_path / "missing-config.json"))

    result = runner.invoke(cli.app, ["config", "show", "--json"])

    assert result.exit_code == 0
    assert "secret-tmap-value" not in result.stdout
    assert "secret-kakao-value" not in result.stdout
    data = json.loads(result.stdout)
    assert data["status"] == "ok"
    assert data["data"]["tmap_api_key"] == {"configured": True, "source": "environment"}
    assert data["data"]["kakao_rest_api_key"] == {"configured": True, "source": "environment"}
