from app.config import Settings
from app.layers import build_layer_catalog


def test_catalog_reports_only_configured_layers_as_available() -> None:
    settings = Settings(
        _env_file=None,
        api_token="test-token",
        mapbiomas_cog_url="/data/mapbiomas.tif",
        biomes_enabled=True,
    )

    layers = {layer.id: layer for layer in build_layer_catalog(settings)}

    assert layers["land-cover"].available is True
    assert layers["vegetation"].available is True
    assert layers["biomes"].available is True
    assert layers["slope"].available is False
    assert layers["hydrography"].available is False
    assert layers["satellite"].available is False
    assert layers["land-cover"].legend
    assert layers["land-cover"].min_zoom == 7
    assert layers["vegetation"].min_zoom == 7
    assert layers["elevation"].min_zoom == 7
    assert layers["slope"].min_zoom == 7


def test_catalog_exposes_png_templates_for_all_layers() -> None:
    settings = Settings(_env_file=None, api_token="test-token")
    layers = {layer.id: layer for layer in build_layer_catalog(settings)}

    assert layers["land-cover"].tile_url.endswith("/{z}/{x}/{y}.png")
    assert layers["hydrography"].tile_url.endswith("/{z}/{x}/{y}.png")
    assert layers["hydrography"].tile_format == "png"
    assert layers["satellite"].map_role == "basemap"
    assert layers["satellite"].tile_format == "jpg"


def test_satellite_is_available_only_with_enabled_token() -> None:
    settings = Settings(
        _env_file=None,
        api_token="test-token",
        esri_basemap_enabled=True,
        esri_basemap_token="esri-test-token",
    )
    layers = {layer.id: layer for layer in build_layer_catalog(settings)}
    assert layers["satellite"].available is True
