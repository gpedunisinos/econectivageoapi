from psycopg import sql

from app.config import Settings
from app.database import connection


class VectorTileProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def render(self, layer_id: str, z: int, x: int, y: int) -> bytes:
        definitions = {
            "biomes": (self.settings.biome_table, ["name"]),
            "hydrography": (self.settings.hydrography_table, ["name"]),
            "population-density": (self.settings.population_table, ["sector_code", "density_km2"]),
        }
        if layer_id not in definitions:
            raise KeyError(layer_id)
        table, fields = definitions[layer_id]
        selected_fields = sql.SQL(", ").join(sql.Identifier(field) for field in fields)
        query = sql.SQL(
            """
            WITH bounds AS (
              SELECT
                ST_TileEnvelope(%s, %s, %s) AS tile_geom,
                ST_Transform(ST_TileEnvelope(%s, %s, %s), 4326) AS source_geom
            ), mvtgeom AS (
              SELECT {fields}, ST_AsMVTGeom(
                ST_Transform(source.geom, 3857), bounds.tile_geom, 4096, 64, true
              ) AS geom
              FROM {table} source, bounds
              WHERE source.geom && bounds.source_geom
                AND ST_Intersects(source.geom, bounds.source_geom)
            )
            SELECT ST_AsMVT(mvtgeom, %s, 4096, 'geom') AS tile FROM mvtgeom
            """
        ).format(fields=selected_fields, table=sql.Identifier(table))
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(query, (z, x, y, z, x, y, layer_id))
            row = cursor.fetchone()
            return bytes(row["tile"]) if row and row["tile"] else b""
