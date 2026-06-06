from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any


CACHE_ENV = "OPEN_GIL_CACHE_PATH"


def cache_path() -> Path:
    override = os.environ.get(CACHE_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "open-gil" / "routes.json"


def cache_key(endpoint: str, payload: dict[str, Any]) -> str:
    body = json.dumps({"endpoint": endpoint, "payload": payload}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class RouteCache:
    def __init__(self, path: Path | None = None, *, ttl_seconds: int = 600, enabled: bool = True) -> None:
        self.path = path or cache_path()
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled
        self._lock = threading.Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        with self._lock:
            data = self._read()
            item = data.get(key)
            if not item:
                return None
            if float(item.get("expires_at", 0)) < time.time():
                data.pop(key, None)
                self._write(data)
                return None
            value = item.get("value")
            return value if isinstance(value, dict) else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        if not self.enabled:
            return
        with self._lock:
            data = self._read()
            data[key] = {"expires_at": time.time() + self.ttl_seconds, "value": value}
            self._write(data)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        if os.name == "posix":
            self.path.chmod(0o600)

