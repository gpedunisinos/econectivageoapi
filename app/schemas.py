from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ContextRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ContextResponse(BaseModel):
    biome: str | None = None
    land_cover: str | None = None
    vegetation_percent: float | None = None
    water_distance_m: float | None = None
    altitude_m: float | None = None
    slope_percent: float | None = None
    built_up_percent: float | None = None
    population_density_km2: float | None = None
    sources: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime
    warnings: list[str] = Field(default_factory=list)


class LegendItem(BaseModel):
    value: int | float | str
    label: str
    color: str


class LayerSource(BaseModel):
    name: str
    version: str
    url: str


class LayerDefinition(BaseModel):
    id: str
    name: str
    description: str
    data_type: Literal["raster", "vector"]
    tile_format: Literal["png", "jpg", "pbf"]
    tile_url: str
    map_role: Literal["basemap", "overlay"] = "overlay"
    attribution: str = ""
    default_opacity: float = Field(ge=0, le=1)
    min_zoom: int
    max_zoom: int
    available: bool
    legend: list[LegendItem]
    source: LayerSource


class HealthResponse(BaseModel):
    status: str
    version: str
    database: bool
    configured_layers: list[str]
