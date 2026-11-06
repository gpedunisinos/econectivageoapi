from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

from app.config import Settings
from app.providers.raster import RasterProvider
from app.providers.vector import VectorProvider
from app.schemas import ContextResponse

T = TypeVar("T")


class EnvironmentalContextService:
    def __init__(
        self,
        settings: Settings,
        vector_provider: VectorProvider | None = None,
        raster_provider: RasterProvider | None = None,
    ) -> None:
        self.settings = settings
        self.vector = vector_provider or VectorProvider(settings)
        self.raster = raster_provider or RasterProvider(settings)

    @staticmethod
    def _safe(label: str, callback: Callable[[], T], warnings: list[str]) -> T | None:
        try:
            return callback()
        except Exception as error:
            warnings.append(f"{label} indisponível: {error}")
            return None

    def build(self, latitude: float, longitude: float) -> ContextResponse:
        warnings: list[str] = []
        sources: dict[str, Any] = {}

        biome = (
            self._safe("Bioma", lambda: self.vector.biome_at(latitude, longitude), warnings)
            if self.settings.biomes_enabled
            else None
        )
        if not self.settings.biomes_enabled:
            warnings.append("Bioma não configurado")
        if biome:
            sources["biome"] = {
                "layer_id": "biomes",
                "dataset": "IBGE — Biomas e Sistema Costeiro-Marinho",
                "version": "1:250.000",
            }

        land = self._safe(
            "Cobertura do solo",
            lambda: self.raster.land_cover(latitude, longitude),
            warnings,
        )
        if land and land.land_cover:
            sources["land_cover"] = {
                "layer_id": "land-cover",
                "dataset": "MapBiomas Brasil 10 m",
                "version": "collection-4-2025",
                "radius_m": self.settings.land_cover_radius_m,
            }

        altitude = self._safe(
            "Altitude", lambda: self.raster.altitude(latitude, longitude), warnings
        )
        if altitude is not None:
            sources["altitude"] = {
                "layer_id": "elevation",
                "dataset": "TOPODATA/INPE",
                "version": "MDE nacional derivado SRTM",
            }

        slope = self._safe("Declividade", lambda: self.raster.slope(latitude, longitude), warnings)
        if slope is not None:
            sources["slope"] = {
                "layer_id": "slope",
                "dataset": "TOPODATA/INPE",
                "version": "Derivada geomorfométrica nacional",
                "radius_m": self.settings.slope_radius_m,
            }

        water_distance = (
            self._safe(
                "Hidrografia",
                lambda: self.vector.water_distance(latitude, longitude),
                warnings,
            )
            if self.settings.hydrography_enabled
            else None
        )
        if not self.settings.hydrography_enabled:
            warnings.append("Hidrografia não configurada")
        if water_distance is not None:
            sources["hydrography"] = {
                "layer_id": "hydrography",
                "dataset": "ANA — BHO Multiescalas",
                "version": "6",
            }

        density = (
            self._safe(
                "Densidade populacional",
                lambda: self.vector.population_density(latitude, longitude),
                warnings,
            )
            if self.settings.population_enabled
            else None
        )
        if not self.settings.population_enabled:
            warnings.append("Densidade populacional não configurada")
        if density is not None:
            sources["population"] = {
                "layer_id": "population-density",
                "dataset": "IBGE — Censo Demográfico",
                "version": "2022",
            }

        return ContextResponse(
            biome=biome,
            land_cover=land.land_cover if land else None,
            vegetation_percent=land.vegetation_percent if land else None,
            water_distance_m=water_distance,
            altitude_m=altitude,
            slope_percent=slope,
            built_up_percent=land.built_up_percent if land else None,
            population_density_km2=density,
            sources=sources,
            generated_at=datetime.now(UTC),
            warnings=warnings,
        )
