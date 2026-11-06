from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.mask import mask
from shapely.geometry import Point, mapping
from shapely.ops import transform

from app.config import Settings
from app.layers import BUILT_UP_CLASSES, MAPBIOMAS_CLASSES, VEGETATION_CLASSES


@dataclass(frozen=True)
class LandCoverContext:
    land_cover: str | None
    vegetation_percent: float | None
    built_up_percent: float | None


class RasterProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @contextmanager
    def _open(self, uri: str) -> Iterator[rasterio.io.DatasetReader]:
        with rasterio.Env(
            GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
            CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff",
        ):
            with rasterio.open(uri) as dataset:
                yield dataset

    @staticmethod
    def _buffer_geometry(latitude: float, longitude: float, radius_m: float, crs: CRS):
        local_crs = CRS.from_proj4(
            f"+proj=aeqd +lat_0={latitude} +lon_0={longitude} +datum=WGS84 +units=m"
        )
        to_local = Transformer.from_crs("EPSG:4326", local_crs, always_xy=True).transform
        from_local = Transformer.from_crs(local_crs, crs, always_xy=True).transform
        point = transform(to_local, Point(longitude, latitude))
        return transform(from_local, point.buffer(radius_m))

    def values_in_radius(
        self,
        uri: str,
        latitude: float,
        longitude: float,
        radius_m: float,
    ) -> np.ndarray:
        with self._open(uri) as dataset:
            geometry = self._buffer_geometry(
                latitude,
                longitude,
                radius_m,
                CRS.from_user_input(dataset.crs),
            )
            data, _ = mask(dataset, [mapping(geometry)], crop=True, filled=False, indexes=1)
            values = data.compressed()
            if dataset.nodata is not None:
                values = values[values != dataset.nodata]
            return values

    def value_at(self, uri: str, latitude: float, longitude: float) -> float | None:
        with self._open(uri) as dataset:
            transformer = Transformer.from_crs("EPSG:4326", dataset.crs, always_xy=True)
            x, y = transformer.transform(longitude, latitude)
            value = next(dataset.sample([(x, y)]))[0]
            if dataset.nodata is not None and value == dataset.nodata:
                return None
            if not np.isfinite(value):
                return None
            return float(value)

    def land_cover(self, latitude: float, longitude: float) -> LandCoverContext:
        if not self.settings.mapbiomas_cog_url:
            return LandCoverContext(None, None, None)
        values = self.values_in_radius(
            self.settings.mapbiomas_cog_url,
            latitude,
            longitude,
            self.settings.land_cover_radius_m,
        ).astype(int)
        if values.size == 0:
            return LandCoverContext(None, None, None)

        counts = Counter(values.tolist())
        predominant = counts.most_common(1)[0][0]
        land_cover = MAPBIOMAS_CLASSES.get(predominant, (f"Classe {predominant}", ""))[0]
        total = float(values.size)
        vegetation = sum(counts[class_id] for class_id in VEGETATION_CLASSES) / total * 100
        built_up = sum(counts[class_id] for class_id in BUILT_UP_CLASSES) / total * 100
        return LandCoverContext(land_cover, round(vegetation, 2), round(built_up, 2))

    def altitude(self, latitude: float, longitude: float) -> float | None:
        if not self.settings.elevation_cog_url:
            return None
        value = self.value_at(self.settings.elevation_cog_url, latitude, longitude)
        return round(value, 2) if value is not None else None

    def slope(self, latitude: float, longitude: float) -> float | None:
        if not self.settings.slope_cog_url:
            return None
        values = self.values_in_radius(
            self.settings.slope_cog_url,
            latitude,
            longitude,
            self.settings.slope_radius_m,
        )
        return round(float(np.mean(values)), 2) if values.size else None
