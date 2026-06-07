from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

from . import __version__
from .config import (
    config_path,
    config_status,
    load_api_key,
    load_kakao_rest_api_key,
    save_api_key,
    save_kakao_rest_api_key,
)
from .errors import INPUT_INVALID, OpenGilError, error_envelope
from .formatters import error_json, format_plan_text, result_json
from .kakao import KakaoLocalClient
from .models import ResolvedPlace
from .planner import Planner, plan_request_from_mapping
from .tmap import TMapClient


app = typer.Typer(help="TMAP API 기반 대중교통 출발시간 추천 CLI", invoke_without_command=True)
config_app = typer.Typer(help="설정 관리")
app.add_typer(config_app, name="config")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="open-gil 버전 출력"),
) -> None:
    if version:
        typer.echo(f"open-gil {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@config_app.command("set-key")
def set_key(api_key: str | None = typer.Argument(None, help="TMAP API appKey")) -> None:
    """Store a TMAP API key in ~/.config/open-gil/config.json with 0600 permissions."""
    key = api_key or typer.prompt("TMAP API 키", hide_input=True)
    path = save_api_key(key)
    typer.echo(f"TMAP API 키를 저장했습니다: {path}")


@config_app.command("set-kakao-key")
def set_kakao_key(api_key: str | None = typer.Argument(None, help="Kakao REST API key")) -> None:
    """Store a Kakao REST API key for coordinate fallback with 0600 permissions."""
    key = api_key or typer.prompt("Kakao REST API 키", hide_input=True)
    path = save_kakao_rest_api_key(key)
    typer.echo(f"Kakao REST API 키를 저장했습니다: {path}")


@config_app.command("show")
def show_config(json_output: bool = typer.Option(False, "--json", help="JSON envelope 출력")) -> None:
    """Show API key configuration status without exposing key values."""
    try:
        status = config_status()
    except OpenGilError as exc:
        _emit_error(exc, json_output=json_output, debug=False)
        raise typer.Exit(1) from exc

    if json_output:
        typer.echo(json.dumps({"status": "ok", "data": status}, ensure_ascii=False, indent=2))
        return

    typer.echo(_format_config_status(status))


@config_app.command("status")
def status_config(json_output: bool = typer.Option(False, "--json", help="JSON envelope 출력")) -> None:
    """Alias for config show."""
    show_config(json_output=json_output)


@app.command("plan")
def plan(
    origin: str | None = typer.Option(None, "--origin", help="출발지 장소명"),
    destination: str | None = typer.Option(None, "--destination", help="도착지 장소명"),
    origin_lat: float | None = typer.Option(None, "--origin-lat", help="출발지 위도"),
    origin_lon: float | None = typer.Option(None, "--origin-lon", help="출발지 경도"),
    destination_lat: float | None = typer.Option(None, "--destination-lat", help="도착지 위도"),
    destination_lon: float | None = typer.Option(None, "--destination-lon", help="도착지 경도"),
    origin_label: str | None = typer.Option(None, "--origin-label", help="출발지 표시명"),
    destination_label: str | None = typer.Option(None, "--destination-label", help="도착지 표시명"),
    depart_at: str | None = typer.Option(None, "--depart-at", help="고정 출발 시각"),
    event_at: str | None = typer.Option(None, "--event-at", help="일정 시작 시각. 15분 전 도착을 목표로 함"),
    arrive_by: str | None = typer.Option(None, "--arrive-by", help="도착 마감 시각. 추가 버퍼 없음"),
    input_path: Path | None = typer.Option(None, "--input", "-i", help="JSON 입력 파일. '-'는 stdin"),
    json_output: bool = typer.Option(False, "--json", help="JSON envelope 출력"),
    debug: bool = typer.Option(False, "--debug", help="오류 상세 정보 포함"),
    no_cache: bool = typer.Option(False, "--no-cache", help="이번 실행에서 로컬 경로 캐시 비활성화"),
) -> None:
    try:
        request_data = _load_request_data(
            input_path=input_path,
            origin=origin,
            destination=destination,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            destination_lat=destination_lat,
            destination_lon=destination_lon,
            origin_label=origin_label,
            destination_label=destination_label,
            depart_at=depart_at,
            event_at=event_at,
            arrive_by=arrive_by,
        )
        request = plan_request_from_mapping(request_data)
        api_key = load_api_key()
        kakao_key = load_kakao_rest_api_key()
        client = TMapClient(api_key)
        place_fallbacks = []
        kakao_client = None
        if kakao_key:
            kakao_client = KakaoLocalClient(kakao_key)
            place_fallbacks.append(kakao_client)
        if no_cache and client.cache:
            client.cache.enabled = False
        if no_cache and kakao_client and kakao_client.cache:
            kakao_client.cache.enabled = False
        planner = Planner(
            client,
            place_selector=None if json_output else _interactive_place_selector,
            place_fallbacks=place_fallbacks,
        )
        try:
            result = planner.plan(request)
        finally:
            client.close()
            if kakao_client:
                kakao_client.close()

        if json_output:
            typer.echo(result_json(result))
        else:
            typer.echo(format_plan_text(result), nl=False)
    except OpenGilError as exc:
        _emit_error(exc, json_output=json_output, debug=debug)
        raise typer.Exit(1) from exc


def _load_request_data(
    *,
    input_path: Path | None,
    origin: str | None,
    destination: str | None,
    origin_lat: float | None,
    origin_lon: float | None,
    destination_lat: float | None,
    destination_lon: float | None,
    origin_label: str | None,
    destination_label: str | None,
    depart_at: str | None,
    event_at: str | None,
    arrive_by: str | None,
) -> dict[str, Any]:
    if input_path is not None:
        text = sys.stdin.read() if str(input_path) == "-" else input_path.read_text(encoding="utf-8")
        return _json_object(text)

    has_cli_input = any(
        value is not None
        for value in (
            origin,
            destination,
            origin_lat,
            origin_lon,
            destination_lat,
            destination_lon,
            depart_at,
            event_at,
            arrive_by,
        )
    )
    if not has_cli_input and not sys.stdin.isatty():
        text = sys.stdin.read()
        if text.strip():
            return _json_object(text)

    return {
        "origin": _place_payload(origin, origin_lat, origin_lon, origin_label),
        "destination": _place_payload(destination, destination_lat, destination_lon, destination_label),
        "depart_at": depart_at,
        "event_at": event_at,
        "arrive_by": arrive_by,
    }


def _place_payload(name: str | None, lat: float | None, lon: float | None, label: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if name:
        payload["name"] = name
    if label:
        payload["label"] = label
    if lat is not None:
        payload["lat"] = lat
    if lon is not None:
        payload["lon"] = lon
    return payload


def _json_object(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OpenGilError(
            INPUT_INVALID,
            "JSON 입력을 해석할 수 없습니다.",
            "올바른 JSON 객체를 --input 파일 또는 stdin으로 전달하세요.",
            debug_detail=str(exc),
        ) from exc
    if not isinstance(data, dict):
        raise OpenGilError(INPUT_INVALID, "JSON 입력은 객체여야 합니다.")
    return data


def _interactive_place_selector(role: str, query: str, candidates: list[ResolvedPlace]) -> ResolvedPlace:
    typer.echo(f"{role} '{query}' 후보가 여러 개입니다. 하나를 선택하세요.")
    for index, candidate in enumerate(candidates, start=1):
        address = f" - {candidate.address}" if candidate.address else ""
        typer.echo(f"{index}. {candidate.name}{address} ({candidate.lat:.6f}, {candidate.lon:.6f})")
    while True:
        choice = typer.prompt("번호", type=int)
        if 1 <= choice <= len(candidates):
            return candidates[choice - 1]
        typer.echo(f"1부터 {len(candidates)} 사이의 번호를 입력하세요.")


def _format_config_status(status: dict[str, Any]) -> str:
    tmap = status["tmap_api_key"]
    kakao = status["kakao_rest_api_key"]
    lines = [
        "open-gil 설정 상태",
        f"- 설정 파일: {status['config_path']}",
        f"- 설정 파일 존재: {'예' if status['config_exists'] else '아니오'}",
    ]
    if status.get("config_mode"):
        lines.append(f"- 설정 파일 권한: {status['config_mode']}")
    lines.extend(
        [
            f"- TMAP API 키(필수): {_configured_label(tmap)}",
            f"- Kakao REST API 키(선택): {_configured_label(kakao)} - 장소명 좌표 fallback용",
        ]
    )
    if not kakao["configured"]:
        lines.extend(
            [
                "",
                "Kakao REST API 키는 선택 사항입니다. 없어도 TMAP POI 장소 검색과 TMAP Transit 경로 계산은 시도할 수 있습니다.",
                "다만 TMAP POI 장소명 검색이 막히거나 실패할 때 Kakao Local 좌표 fallback을 사용할 수 없습니다.",
            ]
        )

    if not tmap["configured"]:
        lines.extend(
            [
                "",
                "TMAP API 키가 없어 아직 경로 계산을 시작할 수 없습니다.",
                "먼저 TMAP appKey를 발급한 뒤 아래 둘 중 하나로 설정하세요.",
                '1. 환경변수: export TMAP_API_KEY="발급받은_appKey"',
                "2. 로컬 저장: open-gil config set-key",
                "",
                "키 값은 화면에 표시하지 않으며, 로컬 설정 파일은 POSIX 환경에서 0600 권한으로 저장됩니다.",
            ]
        )
    return "\n".join(lines)


def _configured_label(value: dict[str, Any]) -> str:
    if not value["configured"]:
        return "없음"
    if value["source"] == "environment":
        return "설정됨 (환경변수)"
    if value["source"] == "config_file":
        return "설정됨 (로컬 설정 파일)"
    return "설정됨"


def _emit_error(error: OpenGilError, *, json_output: bool, debug: bool) -> None:
    if json_output:
        typer.echo(error_json(error_envelope(error, debug=debug)))
        return

    typer.echo(f"{error.code}: {error.message}", err=True)
    if error.remediation:
        typer.echo(f"해결 방법: {error.remediation}", err=True)
    if debug:
        detail = error.to_dict(debug=True).get("debug")
        if detail:
            typer.echo(f"debug: {json.dumps(detail, ensure_ascii=False)}", err=True)
    if error.code == "OPEN_GIL_AUTH_MISSING":
        typer.echo(f"설정 파일 경로: {config_path()}", err=True)
