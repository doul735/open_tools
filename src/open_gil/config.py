from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from .errors import AUTH_MISSING, INPUT_INVALID, OpenGilError


CONFIG_ENV = "OPEN_GIL_CONFIG_PATH"
API_KEY_ENV = "TMAP_API_KEY"


def config_path() -> Path:
    override = os.environ.get(CONFIG_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "open-gil" / "config.json"


def save_api_key(api_key: str, *, path: Path | None = None) -> Path:
    cleaned = api_key.strip()
    if not cleaned:
        raise OpenGilError(INPUT_INVALID, "빈 API 키는 저장할 수 없습니다.")

    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"tmap_api_key": cleaned}, ensure_ascii=False, indent=2), encoding="utf-8")
    _chmod_600(target)
    return target


def load_api_key(*, path: Path | None = None) -> str:
    env_key = os.environ.get(API_KEY_ENV)
    if env_key and env_key.strip():
        return env_key.strip()

    target = path or config_path()
    if target.exists():
        _ensure_private(target)
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise OpenGilError(
                INPUT_INVALID,
                f"설정 파일을 JSON으로 읽을 수 없습니다: {target}",
                "open-gil config set-key 명령으로 API 키를 다시 저장하세요.",
                debug_detail=str(exc),
            ) from exc
        key = str(data.get("tmap_api_key", "")).strip()
        if key:
            return key

    raise OpenGilError(
        AUTH_MISSING,
        "TMAP API 키가 설정되어 있지 않습니다.",
        "TMAP_API_KEY 환경변수를 설정하거나 open-gil config set-key 명령으로 저장하세요.",
    )


def _ensure_private(path: Path) -> None:
    if os.name == "posix":
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode != 0o600:
            _chmod_600(path)


def _chmod_600(path: Path) -> None:
    if os.name == "posix":
        path.chmod(0o600)

