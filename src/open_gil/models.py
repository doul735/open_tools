from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _snake_key(key: str) -> str:
    key = key.replace("-", "_")
    return re.sub(r"(?<!^)([A-Z])", r"_\1", key).lower()


class Coordinates(BaseModel):
    lat: float
    lon: float

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("lat must be between -90 and 90")
        return value

    @field_validator("lon")
    @classmethod
    def validate_lon(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("lon must be between -180 and 180")
        return value


class PlaceInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    label: str | None = None
    lat: float | None = None
    lon: float | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, raw: Any) -> Any:
        if isinstance(raw, str):
            return {"name": raw}
        if isinstance(raw, dict):
            data = {_snake_key(str(k)): v for k, v in raw.items()}
            if "lng" in data and "lon" not in data:
                data["lon"] = data["lng"]
            if "longitude" in data and "lon" not in data:
                data["lon"] = data["longitude"]
            if "latitude" in data and "lat" not in data:
                data["lat"] = data["latitude"]
            if "title" in data and "label" not in data:
                data["label"] = data["title"]
            return data
        return raw

    @model_validator(mode="after")
    def validate_place(self) -> "PlaceInput":
        has_coords = self.lat is not None and self.lon is not None
        has_partial_coords = self.lat is not None or self.lon is not None
        if has_partial_coords and not has_coords:
            raise ValueError("lat and lon must be provided together")
        if not has_coords and not self.name:
            raise ValueError("place name or coordinates are required")
        return self

    @property
    def has_coordinates(self) -> bool:
        return self.lat is not None and self.lon is not None

    @property
    def display_label(self) -> str:
        return self.label or self.name or "좌표"


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    origin: PlaceInput
    destination: PlaceInput
    depart_at: str | datetime | None = None
    event_at: str | datetime | None = None
    arrive_by: str | datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        data = {_snake_key(str(k)): v for k, v in raw.items()}

        for prefix in ("origin", "destination"):
            if prefix not in data:
                place: dict[str, Any] = {}
                for field in ("name", "label", "lat", "lon", "lng", "latitude", "longitude"):
                    key = f"{prefix}_{field}"
                    if key in data:
                        place[field] = data[key]
                if place:
                    data[prefix] = place

        return data

    @model_validator(mode="after")
    def validate_time_intent(self) -> "PlanRequest":
        selected = [
            name
            for name, value in (
                ("depart_at", self.depart_at),
                ("event_at", self.event_at),
                ("arrive_by", self.arrive_by),
            )
            if value is not None
        ]
        if len(selected) != 1:
            raise ValueError("exactly one of depart_at, event_at, arrive_by is required")
        return self

    @property
    def time_mode(self) -> Literal["depart_at", "event_at", "arrive_by"]:
        if self.depart_at is not None:
            return "depart_at"
        if self.event_at is not None:
            return "event_at"
        return "arrive_by"

    @property
    def time_value(self) -> str | datetime:
        value = getattr(self, self.time_mode)
        assert value is not None
        return value


class ResolvedPlace(BaseModel):
    name: str
    lat: float
    lon: float
    address: str | None = None
    poi_id: str | None = None
    source: str = "tmap"

    @property
    def coordinates(self) -> Coordinates:
        return Coordinates(lat=self.lat, lon=self.lon)


class RouteLeg(BaseModel):
    mode: str
    route_name: str | None = None
    route_id: str | None = None
    start_name: str | None = None
    end_name: str | None = None
    section_time_seconds: int | None = None
    distance_meters: int | None = None
    service: int | None = None


class VerificationLinks(BaseModel):
    naver_maps: str
    kakao_map: str


class RouteCandidate(BaseModel):
    kind: Literal["previous", "recommended", "next", "fixed", "candidate"] = "candidate"
    depart_at: datetime
    arrive_at: datetime
    duration_seconds: int
    transfer_count: int | None = None
    total_walk_time_seconds: int | None = None
    total_walk_distance_meters: int | None = None
    total_distance_meters: int | None = None
    total_fare: int | None = None
    route_summary: str
    route_signature: str
    legs: list[RouteLeg] = Field(default_factory=list)
    meets_target: bool | None = None
    service_notes: list[str] = Field(default_factory=list)


class PlanResult(BaseModel):
    origin: ResolvedPlace
    destination: ResolvedPlace
    time_mode: Literal["depart_at", "event_at", "arrive_by"]
    requested_time: datetime
    target_arrival_at: datetime | None = None
    arrival_buffer_minutes: int
    candidates: list[RouteCandidate]
    verification_links: VerificationLinks
    search_strategy: str = "single_lookup"
    route_api_calls_used: int = 1
    planning_note: str | None = None
    source: str = "TMAP Transit API"
    disclaimer: str = (
        "TMAP API 응답 기준입니다. 현장 지연, 운행 중단, 행사장 혼잡은 실제와 다를 수 있습니다."
    )
