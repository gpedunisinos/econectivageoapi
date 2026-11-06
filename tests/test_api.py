from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.schemas import ContextResponse
from app.services.context import EnvironmentalContextService
from app.services.tiles import RasterTileService


def test_requires_bearer_token() -> None:
    client = TestClient(app)
    response = client.get("/layers")
    assert response.status_code == 401


def test_returns_layer_catalog_with_valid_token(monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "test-token")
    get_settings.cache_clear()
    client = TestClient(app)

    response = client.get("/layers", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert any(layer["id"] == "land-cover" for layer in response.json())
    get_settings.cache_clear()


def test_context_contract(monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "test-token")
    get_settings.cache_clear()

    def fake_build(self, latitude: float, longitude: float) -> ContextResponse:
        assert latitude == -29.9
        assert longitude == -51.1
        return ContextResponse(
            biome="Mata Atlântica",
            land_cover="Área urbanizada",
            generated_at=datetime.now(UTC),
        )

    monkeypatch.setattr(EnvironmentalContextService, "build", fake_build)
    client = TestClient(app)
    response = client.post(
        "/context",
        headers={"Authorization": "Bearer test-token"},
        json={"latitude": -29.9, "longitude": -51.1},
    )

    assert response.status_code == 200
    assert response.json()["biome"] == "Mata Atlântica"
    get_settings.cache_clear()


def test_rejects_invalid_coordinates(monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "test-token")
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.post(
        "/context",
        headers={"Authorization": "Bearer test-token"},
        json={"latitude": -120, "longitude": -51.1},
    )
    assert response.status_code == 422
    get_settings.cache_clear()


def test_raster_below_minimum_zoom_returns_transparent_without_rendering(monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "test-token")
    monkeypatch.setenv("MAPBIOMAS_COG_URL", "configured.tif")
    get_settings.cache_clear()

    def must_not_render(self, layer_id: str, z: int, x: int, y: int) -> bytes:
        raise AssertionError("Raster não deve ser aberto abaixo do zoom mínimo")

    monkeypatch.setattr(RasterTileService, "render", must_not_render)
    client = TestClient(app)
    response = client.get(
        "/tiles/land-cover/6/21/36.png",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    get_settings.cache_clear()
