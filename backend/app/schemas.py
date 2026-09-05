from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

MAX_VERTICES = 500  # Nofence US limit
MAX_ACRES = 10_000  # Nofence US limit


class HerdIn(BaseModel):
    species: Literal["cattle", "sheep", "goats"] = "cattle"
    head: int = Field(gt=0, le=20_000)
    avg_weight_lb: float | None = Field(default=None, gt=0, le=3000)


class PlanRequest(BaseModel):
    pasture: dict  # GeoJSON Polygon geometry, WGS84
    water: list[float] | None = None  # [lon, lat]
    herd: HerdIn
    utilization: float = Field(default=0.5, gt=0, le=1)
    n_strips: int | None = Field(default=None, ge=1, le=30)
    target_days_per_strip: float = Field(default=5.0, gt=0, le=60)
    start_date: dt.date | None = None
    source: Literal["synthetic", "rap"] = "synthetic"
    rap_year: int | None = None
    growth_lb_ac_day: float | None = Field(default=None, ge=0)

    @field_validator("pasture")
    @classmethod
    def _check_polygon(cls, v: dict) -> dict:
        if v.get("type") not in ("Polygon", "MultiPolygon"):
            raise ValueError("pasture must be a GeoJSON Polygon geometry")
        coords = v.get("coordinates") or []
        ring = coords[0] if v["type"] == "Polygon" else (coords[0][0] if coords else [])
        if len(ring) - 1 > MAX_VERTICES:
            raise ValueError(f"pasture has {len(ring) - 1} vertices; the limit is {MAX_VERTICES}")
        return v


class StripOut(BaseModel):
    index: int
    geometry: dict
    area_ac: float
    forage_lb: float
    forage_lb_ac: float
    grazing_days: float
    start: dt.date
    end: dt.date
    rest_days_needed: float | None
    ready_again: dt.date | None
    confidence: Literal["high", "medium", "low"]
    confidence_reasons: list[str]
    tree_cover_pct: float
    shrub_cover_pct: float
    parts: int


class PlanOut(BaseModel):
    mode: Literal["forage", "area"]
    strips: list[StripOut]
    total_days: float
    days_min: float
    days_max: float


class PastureOut(BaseModel):
    area_ac: float
    forage_lb_total: float
    forage_lb_ac_mean: float
    grazing_days_total: float
    vertices: int
    over_size_limit: bool


class PlanResponse(BaseModel):
    pasture: PastureOut
    herd: dict[str, Any]
    assumptions: dict[str, Any]
    source: dict[str, Any]
    equal_forage: PlanOut
    equal_area: PlanOut
    raster: dict[str, Any]
    rotation_check: dict[str, Any]
    notes: list[str]
    warnings: list[str]
