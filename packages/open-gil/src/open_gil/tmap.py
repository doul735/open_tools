from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

import httpx

from .cache import RouteCache, cache_key
from .errors import (
    AUTH_FORBIDDEN,
    API_ERROR,
    AUTH_INVALID,
    PLACE_NOT_FOUND,
    QUOTA_EXCEEDED,
    ROUTE_NOT_FOUND,
    OpenGilError,
)
from .models import ResolvedPlace, RouteCandidate, RouteLeg
from .timeutils import tmap_search_dttm


SK_OPEN_API_BASE = "https://apis.openapi.sk.com"


class TMapClient:
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
        params = {
            "version": "1",
            "searchKeyword": query,
            "searchType": "all",
            "searchtypCd": "A",
            "reqCoordType": "WGS84GEO",
            "resCoordType": "WGS84GEO",
            "radius": "0",
            "page": "1",
            "count": str(count),
            "multiPoint": "Y",
            "poiGroupYn": "N",
        }
        data = self._request_json("GET", f"{SK_OPEN_API_BASE}/tmap/pois", params=params)
        places = parse_poi_response(data)
        if not places:
            raise OpenGilError(
                PLACE_NOT_FOUND,
                f"장소를 찾을 수 없습니다: {query}",
                "장소명을 더 구체적으로 입력하거나 좌표를 직접 입력하세요.",
            )
        return places[:count]

    def search_transit_route(
        self,
        origin: ResolvedPlace,
        destination: ResolvedPlace,
        departure_at: datetime,
    ) -> RouteCandidate:
        payload = {
            "startX": f"{origin.lon:.8f}",
            "startY": f"{origin.lat:.8f}",
            "endX": f"{destination.lon:.8f}",
            "endY": f"{destination.lat:.8f}",
            "count": 1,
            "lang": 0,
            "format": "json",
            "searchDttm": tmap_search_dttm(departure_at),
        }
        key = cache_key("transit/routes", payload)
        cached = self.cache.get(key) if self.cache else None
        if cached is not None:
            data = cached
        else:
            data = self._request_json("POST", f"{SK_OPEN_API_BASE}/transit/routes", json=payload)
            if self.cache:
                self.cache.set(key, data)

        return parse_transit_response(data, departure_at)

    def _request_json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        headers = kwargs.pop("headers", {})
        headers.update({"appKey": self.api_key, "Accept": "application/json"})
        if method.upper() == "POST":
            headers.setdefault("Content-Type", "application/json")

        last_error: OpenGilError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.request(method, url, headers=headers, **kwargs)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = OpenGilError(
                    API_ERROR,
                    "TMAP API에 연결하지 못했습니다.",
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
                    "TMAP API 응답을 JSON으로 해석할 수 없습니다.",
                    "잠시 후 다시 시도하거나 --debug로 응답 정보를 확인하세요.",
                    debug_detail=response.text[:500],
                    http_status=response.status_code,
                ) from exc

            if not isinstance(data, dict):
                raise OpenGilError(API_ERROR, "TMAP API 응답 형식이 예상과 다릅니다.")
            return data

        if last_error:
            raise last_error
        raise OpenGilError(API_ERROR, "TMAP API 호출에 실패했습니다.")


def parse_poi_response(data: dict[str, Any]) -> list[ResolvedPlace]:
    root = data.get("searchPoiInfo", data)
    pois_root = root.get("pois", root.get("poi", []))
    pois = pois_root.get("poi", []) if isinstance(pois_root, dict) else pois_root
    if isinstance(pois, dict):
        pois = [pois]
    if not isinstance(pois, list):
        return []

    results: list[ResolvedPlace] = []
    for item in pois:
        if not isinstance(item, dict):
            continue
        lat = _first_float(item, "frontLat", "noorLat", "lat", "latitude")
        lon = _first_float(item, "frontLon", "noorLon", "lon", "lng", "longitude")
        name = str(item.get("name") or item.get("poiName") or "").strip()
        if lat is None or lon is None or not name:
            continue
        results.append(
            ResolvedPlace(
                name=name,
                lat=lat,
                lon=lon,
                address=_poi_address(item),
                poi_id=str(item.get("id") or item.get("poiId") or "") or None,
                source="tmap_poi",
            )
        )
    return results


def parse_transit_response(data: dict[str, Any], departure_at: datetime) -> RouteCandidate:
    itineraries = (
        data.get("metaData", {})
        .get("plan", {})
        .get("itineraries", [])
    )
    if isinstance(itineraries, dict):
        itineraries = [itineraries]
    if not itineraries:
        raise OpenGilError(
            ROUTE_NOT_FOUND,
            "TMAP에서 대중교통 경로를 찾지 못했습니다.",
            "출발지/도착지를 더 구체적으로 입력하거나 다른 시간을 시도하세요.",
        )

    top = itineraries[0]
    if not isinstance(top, dict):
        raise OpenGilError(API_ERROR, "TMAP 경로 응답 형식이 예상과 다릅니다.")

    total_time = _int(top.get("totalTime"))
    if total_time is None:
        raise OpenGilError(API_ERROR, "TMAP 경로 응답에 총 소요시간이 없습니다.")

    legs = [_parse_leg(leg) for leg in top.get("legs", []) if isinstance(leg, dict)]
    signature = _route_signature(legs)
    service_notes = [
        f"{leg.route_name or leg.mode} 운행 종료 가능"
        for leg in legs
        if leg.service == 0 and leg.mode != "WALK"
    ]

    fare = None
    regular = top.get("fare", {}).get("regular", {}) if isinstance(top.get("fare"), dict) else {}
    if isinstance(regular, dict):
        fare = _int(regular.get("totalFare"))

    return RouteCandidate(
        depart_at=departure_at,
        arrive_at=departure_at + timedelta(seconds=total_time),
        duration_seconds=total_time,
        transfer_count=_int(top.get("transferCount")),
        total_walk_time_seconds=_int(top.get("totalWalkTime")),
        total_walk_distance_meters=_int(top.get("totalWalkDistance")),
        total_distance_meters=_int(top.get("totalDistance")),
        total_fare=fare,
        route_summary=_route_summary(legs),
        route_signature=signature,
        legs=legs,
        service_notes=service_notes,
    )


def _parse_leg(leg: dict[str, Any]) -> RouteLeg:
    lane = _first_lane(leg.get("lane"))
    route_name = leg.get("route") or (lane.get("route") if lane else None)
    route_id = leg.get("routeId") or (lane.get("routeId") if lane else None)
    service = leg.get("service")
    if service is None and lane:
        service = lane.get("service")
    start = leg.get("start", {}) if isinstance(leg.get("start"), dict) else {}
    end = leg.get("end", {}) if isinstance(leg.get("end"), dict) else {}
    return RouteLeg(
        mode=str(leg.get("mode") or "UNKNOWN"),
        route_name=str(route_name).strip() if route_name else None,
        route_id=str(route_id).strip() if route_id else None,
        start_name=str(start.get("name")).strip() if start.get("name") else None,
        end_name=str(end.get("name")).strip() if end.get("name") else None,
        section_time_seconds=_int(leg.get("sectionTime")),
        distance_meters=_int(leg.get("distance")),
        service=_int(service),
    )


def _first_lane(raw: Any) -> dict[str, Any]:
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        return raw[0]
    if isinstance(raw, dict):
        return raw
    return {}


def _route_signature(legs: list[RouteLeg]) -> str:
    parts: list[str] = []
    for leg in legs:
        if leg.mode == "WALK":
            continue
        line = leg.route_id or leg.route_name or ""
        parts.append(f"{leg.mode}:{line}:{leg.start_name or ''}>{leg.end_name or ''}")
    if not parts:
        parts = [f"{leg.mode}:{leg.start_name or ''}>{leg.end_name or ''}" for leg in legs]
    return "|".join(parts) or "unknown"


def _route_summary(legs: list[RouteLeg]) -> str:
    labels: list[str] = []
    for index, leg in enumerate(legs):
        previous_leg = legs[index - 1] if index > 0 else None
        next_leg = legs[index + 1] if index + 1 < len(legs) else None
        if (
            leg.mode == "WALK"
            and (leg.distance_meters or 0) == 0
            and (leg.section_time_seconds or 0) == 0
            and previous_leg
            and next_leg
            and previous_leg.mode != "WALK"
            and next_leg.mode != "WALK"
        ):
            labels.append("같은 정류장 환승")
        elif leg.mode == "WALK":
            labels.append("도보")
        elif leg.route_name:
            labels.append(f"{_mode_ko(leg.mode)} {leg.route_name}")
        else:
            labels.append(_mode_ko(leg.mode))
    return " -> ".join(labels) if labels else "경로 정보 없음"


def _mode_ko(mode: str) -> str:
    return {
        "WALK": "도보",
        "BUS": "버스",
        "SUBWAY": "지하철",
        "EXPRESSBUS": "고속/시외버스",
        "TRAIN": "기차",
        "AIRPLANE": "항공",
        "FERRY": "해운",
    }.get(mode, mode)


def _first_float(item: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return None


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _poi_address(item: dict[str, Any]) -> str | None:
    road = item.get("newAddressList", {})
    if isinstance(road, dict):
        new_address = road.get("newAddress")
        if isinstance(new_address, list) and new_address and isinstance(new_address[0], dict):
            full = new_address[0].get("fullAddressRoad")
            if full:
                return str(full)
    candidates = [
        item.get("roadName"),
        " ".join(
            str(item.get(key, "")).strip()
            for key in ("upperAddrName", "middleAddrName", "lowerAddrName", "detailAddrName")
            if item.get(key)
        ),
    ]
    for candidate in candidates:
        if candidate:
            return str(candidate)
    return None


def _error_from_response(response: httpx.Response) -> OpenGilError:
    message = _response_message(response)
    lower = message.lower()
    if response.status_code == 429 or any(token in lower for token in ("limit exceeded", "too many requests", "quota")):
        return OpenGilError(
            QUOTA_EXCEEDED,
            "TMAP API 호출 한도를 초과했습니다.",
            "오늘 남은 호출 한도가 없을 수 있습니다. 다음 한도 초기화 후 다시 시도하거나 TMAP 요금제/쿼터를 확인하세요.",
            debug_detail=message,
            http_status=response.status_code,
        )

    if response.status_code == 403:
        return OpenGilError(
            AUTH_FORBIDDEN,
            "TMAP API 호출 권한이 없습니다.",
            "TMAP 앱키에 현재 호출한 API 상품/권한이 활성화되어 있는지, 요금제/도메인/IP 제한이 있는지 확인하세요.",
            debug_detail=message,
            http_status=response.status_code,
        )

    if response.status_code == 401 or (
        response.status_code == 400 and ("key" in lower or "appkey" in lower or "auth" in lower)
    ):
        return OpenGilError(
            AUTH_INVALID,
            "TMAP API 키가 유효하지 않습니다.",
            "TMAP_API_KEY 값 또는 open-gil config set-key로 저장한 키를 확인하세요.",
            debug_detail=message,
            http_status=response.status_code,
        )

    if response.status_code == 404:
        return OpenGilError(
            ROUTE_NOT_FOUND,
            "TMAP API에서 요청한 경로 또는 장소를 찾지 못했습니다.",
            "장소명, 좌표, 시간을 확인한 뒤 다시 시도하세요.",
            debug_detail=message,
            http_status=response.status_code,
        )

    return OpenGilError(
        API_ERROR,
        f"TMAP API 호출이 실패했습니다: {message}",
        "입력값을 확인하고, 계속 실패하면 --debug로 상세 원인을 확인하세요.",
        debug_detail=response.text[:500],
        http_status=response.status_code,
    )


def _response_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:300] or f"HTTP {response.status_code}"
    if isinstance(data, dict):
        for key in ("message", "errorMessage", "error_description", "detail"):
            if data.get(key):
                return str(data[key])
        error = data.get("error")
        if isinstance(error, dict):
            for key in ("message", "errorMessage", "description"):
                if error.get(key):
                    return str(error[key])
        if isinstance(error, str):
            return error
    return f"HTTP {response.status_code}"
