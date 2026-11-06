from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.config import get_settings
from app.database import database_available
from app.layers import build_layer_catalog, get_layer
from app.providers.vector_tiles import VectorTileProvider
from app.schemas import ContextRequest, ContextResponse, HealthResponse, LayerDefinition
from app.security import require_api_token
from app.services.context import EnvironmentalContextService
from app.services.esri_tiles import EsriTileService
from app.services.tiles import RasterTileService, transparent_tile
from app.services.vector_raster_tiles import VectorRasterTileService

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    settings = get_settings()
    configured = [layer.id for layer in build_layer_catalog(settings) if layer.available]
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        database=database_available(),
        configured_layers=configured,
    )


@router.post(
    "/context",
    response_model=ContextResponse,
    tags=["context"],
    dependencies=[Depends(require_api_token)],
)
def context(payload: ContextRequest) -> ContextResponse:
    settings = get_settings()
    return EnvironmentalContextService(settings).build(payload.latitude, payload.longitude)


@router.get(
    "/layers",
    response_model=list[LayerDefinition],
    tags=["layers"],
    dependencies=[Depends(require_api_token)],
)
def layers() -> list[LayerDefinition]:
    return build_layer_catalog(get_settings())


@router.get(
    "/tiles/{layer_id}/{z}/{x}/{y}.png",
    tags=["tiles"],
    dependencies=[Depends(require_api_token)],
    response_class=Response,
)
def raster_tile(layer_id: str, z: int, x: int, y: int) -> Response:
    settings = get_settings()
    layer = get_layer(settings, layer_id)
    if not layer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camada inexistente")
    if not layer.available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camada não configurada",
        )
    if z < layer.min_zoom:
        return Response(
            content=transparent_tile(),
            media_type="image/png",
            headers={"Cache-Control": f"public, max-age={settings.raster_cache_max_age}"},
        )
    if z > layer.max_zoom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zoom não suportado")
    try:
        if layer.data_type == "raster":
            content = RasterTileService(settings).render(layer_id, z, x, y)
        else:
            content = VectorRasterTileService(settings).render(layer_id, z, x, y)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Não foi possível renderizar o tile: {error}",
        ) from error
    return Response(
        content=content,
        media_type="image/png",
        headers={"Cache-Control": f"public, max-age={settings.raster_cache_max_age}"},
    )


@router.get(
    "/tiles/satellite/{z}/{x}/{y}.jpg",
    tags=["tiles"],
    dependencies=[Depends(require_api_token)],
    response_class=Response,
)
def satellite_tile(z: int, x: int, y: int) -> Response:
    settings = get_settings()
    layer = get_layer(settings, "satellite")
    if not layer or not layer.available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mapa-base de satélite não configurado",
        )
    try:
        content, content_type, upstream_cache = EsriTileService(settings).fetch(z, x, y)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Não foi possível carregar o tile de satélite: {error}",
        ) from error
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": upstream_cache or f"public, max-age={settings.raster_cache_max_age}"
        },
    )


@router.get(
    "/vector-tiles/{layer_id}/{z}/{x}/{y}.pbf",
    tags=["tiles"],
    dependencies=[Depends(require_api_token)],
    response_class=Response,
)
def vector_tile(layer_id: str, z: int, x: int, y: int) -> Response:
    settings = get_settings()
    layer = get_layer(settings, layer_id)
    if not layer or layer.data_type != "vector":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camada inexistente")
    try:
        content = VectorTileProvider(settings).render(layer_id, z, x, y)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Não foi possível renderizar o tile vetorial: {error}",
        ) from error
    return Response(
        content=content,
        media_type="application/vnd.mapbox-vector-tile",
        headers={"Cache-Control": f"public, max-age={settings.raster_cache_max_age}"},
    )
