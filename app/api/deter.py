from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.security import require_api_token
from app.services.deter import nearby

router = APIRouter(prefix="/deter", tags=["deter"], dependencies=[Depends(require_api_token)])


class DeterResponse(BaseModel):
    source: str
    coverage: str
    covered: bool
    fetched_at: datetime
    period_start: date
    period_end: date
    records: int
    rejected: int
    radius_m: int
    classes: list[dict]
    total: int
    stale: bool


@router.get("/nearby", response_model=DeterResponse)
def nearby_alerts(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_m: int = 1000,
):
    """Last 365 days of public DETER Amazônia notices. Not a PRODES deforestation rate."""
    if radius_m not in (500, 1000, 5000):
        raise HTTPException(422, "Raio deve ser 500, 1000 ou 5000 metros.")
    try:
        return nearby(latitude, longitude, radius_m)
    except Exception as error:
        raise HTTPException(503, "DETER temporariamente indisponível.") from error
