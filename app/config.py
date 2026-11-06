from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Unisinos USP Geo API"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_token: str = Field(default="change-me", min_length=8)
    cors_origins: str = ""

    database_url: str = "postgresql://geo:geo@postgis:5432/geo"
    database_pool_min_size: int = 1
    database_pool_max_size: int = 5

    mapbiomas_cog_url: str | None = None
    elevation_cog_url: str | None = None
    slope_cog_url: str | None = None
    elevation_tile_cog_url: str | None = None
    slope_tile_cog_url: str | None = None
    raster_cache_max_age: int = 86400
    raster_tile_cache_dir: str = "/data/tile-cache"
    raster_tile_cache_version: str = "v1"
    esri_basemap_enabled: bool = False
    esri_basemap_token: str | None = None
    esri_basemap_url: str = (
        "https://ibasemaps-api.arcgis.com/arcgis/rest/services/"
        "World_Imagery/MapServer/tile/{z}/{y}/{x}"
    )
    esri_timeout_seconds: float = 15

    land_cover_radius_m: float = 250
    slope_radius_m: float = 100

    biome_table: str = "ibge_biomes"
    hydrography_table: str = "ana_hydrography"
    population_table: str = "ibge_census_sectors"
    biomes_enabled: bool = False
    hydrography_enabled: bool = False
    population_enabled: bool = False

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
