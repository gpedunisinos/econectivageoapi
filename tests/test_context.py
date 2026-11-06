from app.config import Settings
from app.providers.raster import LandCoverContext
from app.services.context import EnvironmentalContextService


class FakeVectorProvider:
    def biome_at(self, latitude: float, longitude: float) -> str:
        return "Mata Atlântica"

    def water_distance(self, latitude: float, longitude: float) -> float:
        return 240

    def population_density(self, latitude: float, longitude: float) -> float:
        return 4270


class FakeRasterProvider:
    def land_cover(self, latitude: float, longitude: float) -> LandCoverContext:
        return LandCoverContext("Área urbanizada", 18.2, 61)

    def altitude(self, latitude: float, longitude: float) -> float:
        return 732

    def slope(self, latitude: float, longitude: float) -> float:
        return 8.4


class FailingVectorProvider(FakeVectorProvider):
    def water_distance(self, latitude: float, longitude: float) -> float:
        raise RuntimeError("base em manutenção")


def test_builds_versioned_context_from_all_providers() -> None:
    service = EnvironmentalContextService(
        Settings(
            _env_file=None,
            api_token="test-token",
            biomes_enabled=True,
            hydrography_enabled=True,
            population_enabled=True,
        ),
        vector_provider=FakeVectorProvider(),  # type: ignore[arg-type]
        raster_provider=FakeRasterProvider(),  # type: ignore[arg-type]
    )

    context = service.build(-29.9, -51.1)

    assert context.biome == "Mata Atlântica"
    assert context.land_cover == "Área urbanizada"
    assert context.vegetation_percent == 18.2
    assert context.water_distance_m == 240
    assert context.altitude_m == 732
    assert context.slope_percent == 8.4
    assert context.built_up_percent == 61
    assert context.population_density_km2 == 4270
    assert context.sources["land_cover"]["layer_id"] == "land-cover"
    assert context.warnings == []


def test_partial_provider_failure_does_not_discard_other_results() -> None:
    service = EnvironmentalContextService(
        Settings(
            _env_file=None,
            api_token="test-token",
            biomes_enabled=True,
            hydrography_enabled=True,
            population_enabled=True,
        ),
        vector_provider=FailingVectorProvider(),  # type: ignore[arg-type]
        raster_provider=FakeRasterProvider(),  # type: ignore[arg-type]
    )

    context = service.build(-29.9, -51.1)

    assert context.biome == "Mata Atlântica"
    assert context.water_distance_m is None
    assert context.land_cover == "Área urbanizada"
    assert any("Hidrografia indisponível" in warning for warning in context.warnings)
