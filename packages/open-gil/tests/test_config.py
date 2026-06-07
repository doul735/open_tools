import json
import os
import stat
from pathlib import Path

from open_gil.config import load_api_key, load_kakao_rest_api_key, save_api_key, save_kakao_rest_api_key


def test_env_api_key_wins(monkeypatch, tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    save_api_key("file-key", path=config)
    monkeypatch.setenv("TMAP_API_KEY", "env-key")

    assert load_api_key(path=config) == "env-key"


def test_save_api_key_sets_0600(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TMAP_API_KEY", raising=False)
    config = tmp_path / "config.json"

    save_api_key("file-key", path=config)

    assert json.loads(config.read_text(encoding="utf-8"))["tmap_api_key"] == "file-key"
    if os.name == "posix":
        assert stat.S_IMODE(config.stat().st_mode) == 0o600
    assert load_api_key(path=config) == "file-key"


def test_kakao_rest_api_key_env_wins(monkeypatch, tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    save_kakao_rest_api_key("file-kakao-key", path=config)
    monkeypatch.setenv("KAKAO_REST_API_KEY", "env-kakao-key")

    assert load_kakao_rest_api_key(path=config) == "env-kakao-key"


def test_config_preserves_multiple_keys(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TMAP_API_KEY", raising=False)
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    config = tmp_path / "config.json"

    save_api_key("tmap-key", path=config)
    save_kakao_rest_api_key("kakao-key", path=config)
    save_api_key("new-tmap-key", path=config)

    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["tmap_api_key"] == "new-tmap-key"
    assert data["kakao_rest_api_key"] == "kakao-key"
    assert load_api_key(path=config) == "new-tmap-key"
    assert load_kakao_rest_api_key(path=config) == "kakao-key"
