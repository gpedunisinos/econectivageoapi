import sqlite3
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.config import get_settings
from app.security import require_api_token
from app.services.biodiversity import BiodiversityService, BiodiversityUnavailable

router = APIRouter(
    prefix="/biodiversity", tags=["biodiversity"], dependencies=[Depends(require_api_token)]
)


class Observation(BaseModel):
    id: int
    taxon_id: int
    scientific_name: str
    common_name: str | None
    observed_on: date | None
    latitude: float
    longitude: float
    approximate_location: bool
    accuracy_m: float | None
    url: str
    photo_url: str
    photo_attribution: str
    photo_license: str
    distance_m: int | None = None


class BiodiversityResponse(BaseModel):
    source: str
    fetched_at: datetime
    cached: bool
    radius_m: int | None
    limit: int
    sampled_records: int
    total_matching_observations: int
    limited: bool
    observations: list[Observation]


def query_service(**kwargs):
    try:
        return BiodiversityService(get_settings()).query(**kwargs)
    except (BiodiversityUnavailable, sqlite3.Error, OSError) as error:
        raise HTTPException(503, "Fauna temporariamente indisponível. Tente novamente.") from error


@router.get("/nearby", response_model=BiodiversityResponse)
def nearby(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_m: int = Query(default=1000, json_schema_extra={"enum": [500, 1000, 5000]}),
):
    """Up to 12 species from a sample of the 200 latest public, licensed fauna observations."""
    if radius_m not in (500, 1000, 5000):
        raise HTTPException(422, "Raio deve ser 500, 1000 ou 5000 metros.")
    return query_service(latitude=latitude, longitude=longitude, radius_m=radius_m)


@router.get("/observations", response_model=BiodiversityResponse)
def observations(
    north: float = Query(ge=-90, le=90),
    south: float = Query(ge=-90, le=90),
    east: float = Query(ge=-180, le=180),
    west: float = Query(ge=-180, le=180),
):
    """Up to 100 public observations in a viewport of at most 3 degrees per axis."""
    if not 0 < north - south <= 3 or not 0 < east - west <= 3:
        raise HTTPException(422, "Aproxime o mapa para visualizar a fauna (área máxima de 3°).")
    return query_service(north=north, south=south, east=east, west=west)
