from io import BytesIO

import numpy as np
from PIL import Image

from app.config import Settings
from app.services.tiles import (
    RasterTileService,
    _rgba_categorical,
    _rgba_continuous,
    tile_intersects_bounds,
    transparent_tile,
)


def test_categorical_tile_applies_color_and_transparency() -> None:
    data = np.array([[24, 3], [99, 24]], dtype=np.uint8)
    mask = np.array([[255, 255], [0, 255]], dtype=np.uint8)

    rgba = _rgba_categorical(data, mask, {24: "#d4271e", 3: "#1f8d49"})

    assert tuple(rgba[0, 0, :3]) == (212, 39, 30)
    assert tuple(rgba[0, 1, :3]) == (31, 141, 73)
    assert rgba[1, 0, 3] == 0


def test_continuous_tile_interpolates_palette() -> None:
    data = np.array([[0.0, 50.0, 100.0]])
    mask = np.array([[255, 255, 255]], dtype=np.uint8)

    rgba = _rgba_continuous(data, mask, [(0, "#000000"), (100, "#ffffff")])

    assert tuple(rgba[0, 0, :3]) == (0, 0, 0)
    assert tuple(rgba[0, 2, :3]) == (255, 255, 255)
    assert 126 <= rgba[0, 1, 0] <= 128


def test_rejects_tiles_outside_brazil_before_opening_raster(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        api_token="test-token",
        mapbiomas_cog_url="/file/that/must/not/be/opened.tif",
        raster_tile_cache_dir=str(tmp_path),
    )

    content = RasterTileService(settings).render("land-cover", 7, 0, 0)

    image = np.asarray(Image.open(BytesIO(content)))
    assert np.count_nonzero(image) == 0


def test_tile_bounds_cover_brazil_but_not_other_territories() -> None:
    assert tile_intersects_bounds(7, 43, 73) is True
    assert tile_intersects_bounds(7, 0, 0) is False


def test_persistent_cache_avoids_rendering_same_tile_twice(tmp_path, monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        api_token="test-token",
        mapbiomas_cog_url="configured.tif",
        raster_tile_cache_dir=str(tmp_path),
    )
    service = RasterTileService(settings)
    calls = 0

    def fake_render(layer_id: str, z: int, x: int, y: int) -> bytes:
        nonlocal calls
        calls += 1
        return transparent_tile()

    monkeypatch.setattr(service, "_render_uncached", fake_render)

    first = service.render("land-cover", 7, 43, 73)
    second = RasterTileService(settings).render("land-cover", 7, 43, 73)

    assert first == second
    assert calls == 1
    assert (tmp_path / "v1/land-cover/7/43/73.png").exists()


def test_elevation_uses_visual_cog_when_configured(tmp_path, monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        api_token="test-token",
        elevation_cog_url="native.vrt",
        elevation_tile_cog_url="visual.tif",
        raster_tile_cache_dir=str(tmp_path),
    )
    opened_sources: list[str] = []

    class FakeReader:
        def __init__(self, source: str) -> None:
            opened_sources.append(source)

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def tile(self, x: int, y: int, z: int, tilesize: int):
            return type(
                "Tile",
                (),
                {
                    "data": np.zeros((1, 256, 256), dtype=np.float32),
                    "mask": np.full((256, 256), 255, dtype=np.uint8),
                },
            )()

    monkeypatch.setattr("app.services.tiles.COGReader", FakeReader)

    RasterTileService(settings).render("elevation", 7, 43, 73)

    assert opened_sources == ["visual.tif"]
