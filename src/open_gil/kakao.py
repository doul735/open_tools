from __future__ import annotations

import re
import time
from typing import Any

import httpx

from .cache import RouteCache, cache_key
from .errors import (
    API_ERROR,
    AUTH_FORBIDDEN,
    AUTH_INVALID,
    PLACE_NOT_FOUND,
    QUOTA_EXCEEDED,
    OpenGilError,
)
from .models import ResolvedPlace


KAKAO_LOCAL_BASE = "https://dapi.kakao.com"


class KakaoLocalClient:
    def __init__(
        self,
        api_key: str,
        *,
        http_client: httpx.Client | None = None,
        cache: RouteCache | None = None,
        timeout: float = 10.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key
        self._client = http_client or httpx.Client(timeout=timeout)
        self._owns_client = http_client is None
        self.cache = cache or RouteCache()
        self.max_retries = max_retries

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def search_poi(self, query: str, *, count: int = 5) -> list[ResolvedPlace]:
        size = max(1, min(count, 15))
        methods = (
            (self.search_address, self.search_keyword)
            if _looks_like_address(query)
            else (self.search_keyword, self.search_address)
        )
        for method in methods:
            places = method(query, count=size)
            if places:
                return places[:count]
        raise OpenGilError(
            PLACE_NOT_FOUND,
            f"Kakao Local에서 장소를 찾을 수 없습니다: {query}",
            "장소명을 더 구체적으로 입력하거나 좌표를 직접 입력하세요.",
        )

    def search_keyword(self, query: str, *, count: int = 5) -> list[ResolvedPlace]:
        params = {"query": query, "size": str(max(1, min(count, 15)))}
        data = self._request_json("GET", f"{KAKAO_LOCAL_BASE}/v2/local/search/keyword.json", params=params)
        return parse_keyword_response(data)

    def search_address(self, query: str, *, count: int = 5) -> list[ResolvedPlace]:
        params = {"query": query, "size": str(max(1, min(count, 30)))}
        data = self._request_json("GET", f"{KAKAO_LOCAL_BASE}/v2/local/search/address.json", params=params)
        return parse_address_response(data, query=query)

    def _request_json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        key = cache_key("kakao" + httpx.URL(url).path, kwargs.get("params", {}))
        cached = self.cache.get(key) if self.cache else None
        if cached is not None:
            return cached

        headers = kwargs.pop("headers", {})
        headers.update({"Authorization": f"KakaoAK {self.api_key}", "Accept": "application/json"})

        last_error: OpenGilError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.request(method, url, headers=headers, **kwargs)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = OpenGilError(
                    API_ERROR,
                    "Kakao Local API에 연결하지 못했습니다.",
                    "네트워크 상태를 확인한 뒤 다시 실행하세요.",
                    debug_detail=str(exc),
                )
                if attempt < self.max_retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise last_error from exc

            if 500 <= response.status_code <= 599 and attempt < self.max_retries:
                time.sleep(0.2 * (attempt + 1))
                continue

            if response.status_code >= 400:
                raise _error_from_response(response)

            try:
                data = response.json()
            except ValueError as exc:
                raise OpenGilError(
                    API_ERROR,
                    "Kakao Local API 응답을 JSON으로 해석할 수 없습니다.",
                    "잠시 후 다시 시도하거나 --debug로 응답 정보를 확인하세요.",
                    debug_detail=response.text[:500],
                    http_status=response.status_code,
                ) from exc

            if not isinstance(data, dict):
                raise OpenGilError(API_ERROR, "Kakao Local API 응답 형식이 예상과 다릅니다.")
            if self.cache:
                self.cache.set(key, data)
            return data

        if last_error:
            raise last_error
        raise OpenGilError(API_ERROR, "Kakao Local API 호출에 실패했습니다.")


def parse_keyword_response(data: dict[str, Any]) -> list[ResolvedPlace]:
    documents = data.get("documents", [])
    if not isinstance(documents, list):
        return []

    places: list[ResolvedPlace] = []
    for item in documents:
        if not isinstance(item, dict):
            continue
        place = _place_from_kakao_document(
            item,
            name=str(item.get("place_name") or "").strip(),
            address=str(item.get("road_address_name") or item.get("address_name") or "").strip() or None,
            poi_id=str(item.get("id") or "").strip() or None,
            source="kakao_local_keyword",
        )
        if place:
            places.append(place)
    return places


def parse_address_response(data: dict[str, Any], *, query: str) -> list[ResolvedPlace]:
    documents = data.get("documents", [])
    if not isinstance(documents, list):
        return []

    places: list[ResolvedPlace] = []
    for item in documents:
        if not isinstance(item, dict):
            continue
        road_address = item.get("road_address") if isinstance(item.get("road_address"), dict) else {}
        address = item.get("address") if isinstance(item.get("address"), dict) else {}
        building_name = str(road_address.get("building_name") or "").strip()
        address_name = str(
            road_address.get("address_name")
            or item.get("address_name")
            or address.get("address_name")
            or ""
        ).strip()
        place = _place_from_kakao_document(
            item,
            name=building_name or address_name or query,
            address=address_name or None,
            poi_id=None,
            source="kakao_local_address",
        )
        if place:
            places.append(place)
    return places


def _place_from_kakao_document(
    item: dict[str, Any],
    *,
    name: str,
    address: str | None,
    poi_id: str | None,
    source: str,
) -> ResolvedPlace | None:
    lat = _float(item.get("y"))
    lon = _float(item.get("x"))
    if lat is None or lon is None or not name:
        return None
    return ResolvedPlace(
        name=name,
        lat=lat,
        lon=lon,
        address=address,
        poi_id=poi_id,
        source=source,
    )


def _looks_like_address(query: str) -> bool:
    return bool(
        re.search(r"\d", query)
        or re.search(r"(시|군|구|읍|면|동|리)\s", query)
        or re.search(r"(로|길|번길)\s*\d", query)
    )


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _error_from_response(response: httpx.Response) -> OpenGilError:
    message = _response_message(response)
    lower = message.lower()
    if response.status_code == 429 or any(token in lower for token in ("quota", "limit exceeded", "too many")):
        return OpenGilError(
            QUOTA_EXCEEDED,
            "Kakao Local API 호출 한도를 초과했습니다.",
            "Kakao Developers 쿼터를 확인하거나 잠시 후 다시 시도하세요.",
            debug_detail=message,
            http_status=response.status_code,
        )
    if response.status_code == 403:
        return OpenGilError(
            AUTH_FORBIDDEN,
            "Kakao Local API 호출 권한이 없습니다.",
            "Kakao REST API 키와 Local API 사용 권한, 앱 설정 제한을 확인하세요.",
            debug_detail=message,
            http_status=response.status_code,
        )
    if response.status_code == 401:
        return OpenGilError(
            AUTH_INVALID,
            "Kakao Local API 키가 유효하지 않습니다.",
            "KAKAO_REST_API_KEY 값 또는 open-gil config set-kakao-key로 저장한 키를 확인하세요.",
            debug_detail=message,
            http_status=response.status_code,
        )
    return OpenGilError(
        API_ERROR,
        "Kakao Local API 호출에 실패했습니다.",
        "응답 상태와 요청 값을 확인하세요.",
        debug_detail=message,
        http_status=response.status_code,
    )


def _response_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:500] or response.reason_phrase
    if isinstance(data, dict):
        for key in ("message", "msg", "error", "error_description"):
            value = data.get(key)
            if value:
                return str(value)
    return str(data)[:500]
