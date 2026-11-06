from functools import lru_cache
from io import BytesIO
from os import getpid
from pathlib import Path
from threading import Lock, get_ident

import numpy as np
from morecantile import tms
from PIL import Image
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.io import COGReader

from app.config import Settings
from app.layers import MAPBIOMAS_CLASSES, VEGETATION_CLASSES

BRAZIL_DATA_BOUNDS = (-75.0, -34.0, -34.0, 6.0)
WEB_MERCATOR = tms.get("WebMercatorQuad")
_cache_locks = tuple(Lock() for _ in range(64))


def _hex_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[index : index + 2], 16) for index in (0, 2, 4))


def _rgba_categorical(data: np.ndarray, mask: np.ndarray, palette: dict[int, str]) -> np.ndarray:
    rgba = np.zeros((data.shape[0], data.shape[1], 4), dtype=np.uint8)
    for value, color in palette.items():
        selected = data == value
        rgba[selected, :3] = _hex_rgb(color)
        rgba[selected, 3] = 220
    rgba[mask == 0, 3] = 0
    return rgba


def _rgba_continuous(
    data: np.ndarray,
    mask: np.ndarray,
    stops: list[tuple[float, str]],
) -> np.ndarray:
    values = np.asarray([stop[0] for stop in stops], dtype=float)
    colors = np.asarray([_hex_rgb(stop[1]) for stop in stops], dtype=float)
    clipped = np.clip(data.astype(float), values[0], values[-1])
    rgba = np.zeros((data.shape[0], data.shape[1], 4), dtype=np.uint8)
    for channel in range(3):
        rgba[:, :, channel] = np.interp(clipped, values, colors[:, channel]).astype(np.uint8)
    rgba[:, :, 3] = np.where(mask > 0, 210, 0).astype(np.uint8)
    return rgba


def _png(rgba: np.ndarray) -> bytes:
    output = BytesIO()
    Image.fromarray(rgba).save(output, format="PNG", optimize=True)
    return output.getvalue()


@lru_cache(maxsize=1)
def transparent_tile() -> bytes:
    return _png(np.zeros((256, 256, 4), dtype=np.uint8))


def tile_intersects_bounds(z: int, x: int, y: int) -> bool:
    if z < 0 or x < 0 or y < 0 or x >= 2**z or y >= 2**z:
        return False
    tile_bounds = WEB_MERCATOR.bounds(x, y, z)
    west, south, east, north = BRAZIL_DATA_BOUNDS
    return not (
        tile_bounds.right <= west
        or tile_bounds.left >= east
        or tile_bounds.top <= south
        or tile_bounds.bottom >= north
    )


def _cache_lock(path: Path) -> Lock:
    return _cache_locks[hash(path) % len(_cache_locks)]


class RasterTileService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def render(self, layer_id: str, z: int, x: int, y: int) -> bytes:
        cache_path = self._cache_path(layer_id, z, x, y)
        try:
            return cache_path.read_bytes()
        except FileNotFoundError:
            pass

        with _cache_lock(cache_path):
            try:
                return cache_path.read_bytes()
            except FileNotFoundError:
                content = self._render_uncached(layer_id, z, x, y)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                temporary_path = cache_path.with_suffix(f".{getpid()}.{get_ident()}.tmp")
                temporary_path.write_bytes(content)
                temporary_path.replace(cache_path)
                return content

    def _cache_path(self, layer_id: str, z: int, x: int, y: int) -> Path:
        return (
            Path(self.settings.raster_tile_cache_dir)
            / self.settings.raster_tile_cache_version
            / layer_id
            / str(z)
            / str(x)
            / f"{y}.png"
        )

    def _render_uncached(self, layer_id: str, z: int, x: int, y: int) -> bytes:
        source = {
            "land-cover": self.settings.mapbiomas_cog_url,
            "vegetation": self.settings.mapbiomas_cog_url,
            "elevation": self.settings.elevation_tile_cog_url or self.settings.elevation_cog_url,
            "slope": self.settings.slope_tile_cog_url or self.settings.slope_cog_url,
        }.get(layer_id)
        if not source:
            raise FileNotFoundError(f"Camada {layer_id} não configurada")

        if not tile_intersects_bounds(z, x, y):
            return transparent_tile()

        try:
            with COGReader(source) as cog:
                tile = cog.tile(x, y, z, tilesize=256)
        except TileOutsideBounds:
            return transparent_tile()
        data = tile.data[0]
        mask = tile.mask

        if not np.any(mask):
            return transparent_tile()

        if layer_id == "land-cover":
            rgba = _rgba_categorical(
                data,
                mask,
                {value: color for value, (_, color) in MAPBIOMAS_CLASSES.items()},
            )
        elif layer_id == "vegetation":
            vegetation = np.isin(data.astype(int), list(VEGETATION_CLASSES)).astype(np.uint8)
            rgba = _rgba_categorical(vegetation, mask, {1: "#238b45"})
        elif layer_id == "elevation":
            rgba = _rgba_continuous(
                data,
                mask,
                [(0, "#2c7bb6"), (500, "#abd9e9"), (1000, "#fdae61"), (2000, "#a50026")],
            )
        else:
            rgba = _rgba_continuous(
                data,
                mask,
                [(0, "#31a354"), (3, "#addd8e"), (8, "#fee08b"), (20, "#f46d43"), (45, "#a50026")],
            )
        return _png(rgba)
