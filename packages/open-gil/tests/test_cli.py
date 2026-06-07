import json
from datetime import datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from open_gil import cli
from open_gil.models import PlanResult, ResolvedPlace, RouteCandidate, VerificationLinks
from open_gil.timeutils import DEFAULT_TZ


runner = CliRunner()


def test_version_option() -> None:
    result = runner.invoke(cli.app, ["--version"])

    assert result.exit_code == 0
    assert "open-gil 0.1.5" in result.stdout


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
    assert "TMAP API 키(필수): 없음" in result.stdout
    assert "Kakao REST API 키(선택): 없음" in result.stdout
    assert "Kakao REST API 키는 선택 사항입니다." in result.stdout
    assert "TMAP API 키가 없어 아직 경로 계산을 시작할 수 없습니다." in result.stdout
    assert 'export TMAP_API_KEY="발급받은_appKey"' in result.stdout
    assert "open-gil setup" in result.stdout


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


def test_setup_prompts_for_tmap_key_without_echoing_value(monkeypatch, tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    monkeypatch.delenv("TMAP_API_KEY", raising=False)
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    monkeypatch.setenv("OPEN_GIL_CONFIG_PATH", str(config))

    result = runner.invoke(cli.app, ["setup"], input="new-secret-key\n")

    assert result.exit_code == 0
    assert "채팅창에 붙여넣지 마세요" in result.stdout
    assert "TMAP API 키를 저장했습니다" in result.stdout
    assert "new-secret-key" not in result.stdout
    assert '"tmap_api_key": "new-secret-key"' in config.read_text(encoding="utf-8")


def test_setup_does_not_expose_existing_env_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TMAP_API_KEY", "existing-secret-key")
    monkeypatch.setenv("OPEN_GIL_CONFIG_PATH", str(tmp_path / "missing-config.json"))

    result = runner.invoke(cli.app, ["setup"])

    assert result.exit_code == 0
    assert "이미 경로 계산에 필요한 필수 키가 설정되어 있습니다." in result.stdout
    assert "환경변수는 로컬 설정 파일보다 우선합니다." in result.stdout
    assert "unset TMAP_API_KEY 후 open-gil setup" in result.stdout
    assert "existing-secret-key" not in result.stdout


def test_setup_repairs_invalid_config(monkeypatch, tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text("{not-json", encoding="utf-8")
    monkeypatch.delenv("TMAP_API_KEY", raising=False)
    monkeypatch.setenv("OPEN_GIL_CONFIG_PATH", str(config))

    result = runner.invoke(cli.app, ["setup"], input="replacement-key\n")

    assert result.exit_code == 0
    assert "기존 설정 파일을 JSON으로 읽을 수 없어 새 설정 파일로 다시 저장합니다." in result.stdout
    assert "replacement-key" not in result.stdout
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data == {"tmap_api_key": "replacement-key"}
