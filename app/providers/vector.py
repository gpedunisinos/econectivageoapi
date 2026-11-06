from dataclasses import dataclass
from typing import Any

from psycopg import sql

from app.config import Settings
from app.database import connection


@dataclass(frozen=True)
class VectorContext:
    biome: str | None = None
    water_distance_m: float | None = None
    population_density_km2: float | None = None


class VectorProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def biome_at(self, latitude: float, longitude: float) -> str | None:
        query = sql.SQL(
            """
            SELECT name
            FROM {table}
            WHERE ST_Covers(geom, ST_SetSRID(ST_Point(%s, %s), 4326))
            LIMIT 1
            """
        ).format(table=sql.Identifier(self.settings.biome_table))
        row = self._fetchone(query, (longitude, latitude))
        return row["name"] if row else None

    def water_distance(self, latitude: float, longitude: float) -> float | None:
        query = sql.SQL(
            """
            SELECT ST_Distance(
                geom::geography,
                ST_SetSRID(ST_Point(%s, %s), 4326)::geography
            ) AS distance_m
            FROM {table}
            WHERE ST_DWithin(
                geom::geography,
                ST_SetSRID(ST_Point(%s, %s), 4326)::geography,
                50000
            )
            ORDER BY geom <-> ST_SetSRID(ST_Point(%s, %s), 4326)
            LIMIT 1
            """
        ).format(table=sql.Identifier(self.settings.hydrography_table))
        row = self._fetchone(
            query,
            (longitude, latitude, longitude, latitude, longitude, latitude),
        )
        return float(row["distance_m"]) if row and row["distance_m"] is not None else None

    def population_density(self, latitude: float, longitude: float) -> float | None:
        query = sql.SQL(
            """
            SELECT density_km2
            FROM {table}
            WHERE ST_Covers(geom, ST_SetSRID(ST_Point(%s, %s), 4326))
            LIMIT 1
            """
        ).format(table=sql.Identifier(self.settings.population_table))
        row = self._fetchone(query, (longitude, latitude))
        return float(row["density_km2"]) if row and row["density_km2"] is not None else None

    def collect(self, latitude: float, longitude: float) -> VectorContext:
        return VectorContext(
            biome=self.biome_at(latitude, longitude),
            water_distance_m=self.water_distance(latitude, longitude),
            population_density_km2=self.population_density(latitude, longitude),
        )

    @staticmethod
    def _fetchone(query: sql.Composed, params: tuple[Any, ...]) -> dict[str, Any] | None:
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()
