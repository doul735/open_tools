from __future__ import annotations

from dataclasses import dataclass
from typing import Any


AUTH_MISSING = "OPEN_GIL_AUTH_MISSING"
AUTH_INVALID = "OPEN_GIL_AUTH_INVALID"
PLACE_AMBIGUOUS = "OPEN_GIL_PLACE_AMBIGUOUS"
PLACE_NOT_FOUND = "OPEN_GIL_PLACE_NOT_FOUND"
ROUTE_NOT_FOUND = "OPEN_GIL_ROUTE_NOT_FOUND"
API_ERROR = "OPEN_GIL_API_ERROR"
TIME_INVALID = "OPEN_GIL_TIME_INVALID"
INPUT_INVALID = "OPEN_GIL_INPUT_INVALID"


@dataclass
class OpenGilError(Exception):
    code: str
    message: str
    remediation: str | None = None
    details: dict[str, Any] | None = None
    debug_detail: str | None = None
    http_status: int | None = None

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)

    def to_dict(self, *, debug: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.remediation:
            payload["remediation"] = self.remediation
        if self.details:
            payload["details"] = self.details
        if debug:
            debug_payload: dict[str, Any] = {}
            if self.http_status is not None:
                debug_payload["http_status"] = self.http_status
            if self.debug_detail:
                debug_payload["detail"] = self.debug_detail
            if debug_payload:
                payload["debug"] = debug_payload
        return payload


def error_envelope(error: OpenGilError, *, debug: bool = False) -> dict[str, Any]:
    return {"status": "error", "error": error.to_dict(debug=debug)}


def ok_envelope(data: dict[str, Any]) -> dict[str, Any]:
    return {"status": "ok", "data": data}

