from io import BytesIO

from PIL import Image, ImageDraw
from psycopg import sql
from shapely import wkb
from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon, Polygon

from app.config import Settings
from app.database import connection

TILE_SIZE = 256

BIOME_COLORS = {
    "amazônia": "#1b7837",
    "caatinga": "#d8b365",
    "cerrado": "#80cdc1",
    "mata atlântica": "#35978f",
    "pampa": "#dfc27d",
    "pantanal": "#5ab4ac",
}


class VectorRasterTileService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def render(self, layer_id: str, z: int, x: int, y: int) -> bytes:
        definitions = {
            "biomes": (self.settings.biome_table, ["name"]),
            "hydrography": (self.settings.hydrography_table, ["name"]),
            "population-density": (self.settings.population_table, ["density_km2"]),
        }
        if layer_id not in definitions:
            raise KeyError(layer_id)

        table, fields = definitions[layer_id]
        selected = sql.SQL(", ").join(sql.Identifier(field) for field in fields)
        query = sql.SQL(
            """
            WITH bounds AS (
              SELECT ST_TileEnvelope(%s, %s, %s) AS geom,
                     ST_Transform(ST_TileEnvelope(%s, %s, %s), 4326) AS source_geom
            )
            SELECT {fields}, ST_AsBinary(
              ST_Intersection(ST_Transform(source.geom, 3857), bounds.geom)
            ) AS geometry
            FROM {table} source, bounds
            WHERE source.geom && bounds.source_geom
              AND ST_Intersects(source.geom, bounds.source_geom)
            """
        ).format(fields=selected, table=sql.Identifier(table))
        with connection() as conn, conn.cursor() as cursor:
            cursor.execute(query, (z, x, y, z, x, y))
            rows = cursor.fetchall()

        image = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image, "RGBA")
        min_x, min_y, max_x, max_y = self._tile_bounds(z, x, y)
        for row in rows:
            if not row["geometry"]:
                continue
            geometry = wkb.loads(bytes(row["geometry"]))
            self._draw(draw, geometry, layer_id, row, min_x, min_y, max_x, max_y)

        output = BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()

    @staticmethod
    def _tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
        world = 20037508.342789244
        size = world * 2 / (2**z)
        min_x = -world + x * size
        max_y = world - y * size
        return min_x, max_y - size, min_x + size, max_y

    def _draw(self, draw, geometry, layer_id, row, min_x, min_y, max_x, max_y):
        # Bounding-box matches can clip to empty geometries at tile boundaries.
        if geometry.is_empty:
            return

        def point(coordinate):
            px = (coordinate[0] - min_x) / (max_x - min_x) * TILE_SIZE
            py = (max_y - coordinate[1]) / (max_y - min_y) * TILE_SIZE
            return (px, py)

        if isinstance(geometry, GeometryCollection | MultiPolygon | MultiLineString):
            for child in geometry.geoms:
                self._draw(draw, child, layer_id, row, min_x, min_y, max_x, max_y)
            return
        if isinstance(geometry, Polygon):
            coordinates = [point(value) for value in geometry.exterior.coords]
            if layer_id == "biomes":
                color = BIOME_COLORS.get(str(row.get("name", "")).lower(), "#969696")
            else:
                density = float(row.get("density_km2") or 0)
                color = (
                    "#fff7ec"
                    if density <= 100
                    else "#fdbb84"
                    if density <= 1000
                    else "#e34a33"
                    if density <= 5000
                    else "#7f0000"
                )
            draw.polygon(coordinates, fill=color + "88", outline=color + "DD", width=1)
            for interior in geometry.interiors:
                draw.polygon([point(value) for value in interior.coords], fill=(0, 0, 0, 0))
            return
        if isinstance(geometry, LineString):
            draw.line([point(value) for value in geometry.coords], fill="#2b8cbeE6", width=2)
