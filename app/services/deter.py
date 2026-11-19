"""INPE DETER Amazônia: local queries, atomic bounded refresh, no live user downloads."""

import hashlib
import json
import logging
import math
import shutil
import time
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from io import BytesIO
from urllib.request import urlopen

from PIL import Image, ImageDraw
from shapely import make_valid, to_wkb
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, shape

from app.database import connection

SOURCE = "https://terrabrasilis.dpi.inpe.br/"
DOWNLOAD = "https://terrabrasilis.dpi.inpe.br/file-delivery/download/deter-amz/shape"
MAX_RECORDS = 100_000
MAX_DOWNLOAD = 512 * 1024 * 1024
logger = logging.getLogger(__name__)


def normalize_feature(feature):
    """Public feature IDs repeat across historical partitions: hash geometry and attributes."""
    props = feature["properties"]
    geometry = make_valid(shape(feature["geometry"]))
    polygons = []

    def collect(g):
        if isinstance(g, Polygon):
            if not g.is_empty:
                polygons.append(g)
        elif isinstance(g, MultiPolygon | GeometryCollection):
            for part in g.geoms:
                collect(part)

    collect(geometry)
    geometry = MultiPolygon(polygons)
    if geometry.is_empty or not geometry.is_valid:
        return None
    observed = datetime.fromisoformat(props["view_date"].replace("Z", "+00:00")).date()
    identity = hashlib.sha256(json.dumps(feature, sort_keys=True).encode()).hexdigest()
    return (
        identity,
        str(feature["id"]),
        str(props["classname"]),
        observed,
        props.get("municipality"),
        props.get("uf"),
        to_wkb(geometry, hex=True),
    )


def sync_snapshot(force=False, archive_path=None):
    """Stream the official ZIP, keep only 365 days, atomically replace after full validation.

    An operator may supply a previously downloaded official ZIP for initial import.
    Temporary files live on the existing filesystem and are always removed.
    """
    import subprocess
    import tempfile
    import zipfile
    from pathlib import Path

    with connection() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_xact_lock(791119) AS locked")
        if not cursor.fetchone()["locked"]:
            return {"status": "busy"}
        cursor.execute("SELECT * FROM deter_import_state")
        snapshot = cursor.fetchone()
        if not force and (
            not snapshot or datetime.now(UTC) - snapshot["fetched_at"] < timedelta(days=1)
        ):
            return {"status": "not_due"}
        if shutil.disk_usage("/tmp").free < 2 * 1024**3:
            raise RuntimeError("DETER disk safety margin reached")
        end = datetime.now(UTC).date()
        start = end - timedelta(days=365)
        began = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="onlife-deter-") as temp:
            archive = Path(archive_path) if archive_path else Path(temp) / "source.zip"
            if archive_path is None:
                with urlopen(DOWNLOAD, timeout=60) as response, archive.open("wb") as output:
                    downloaded = 0
                    while chunk := response.read(1024 * 1024):
                        downloaded += len(chunk)
                        if downloaded > MAX_DOWNLOAD or time.monotonic() - began > 900:
                            raise RuntimeError("DETER download budget exceeded")
                        output.write(chunk)
            downloaded = archive.stat().st_size
            if downloaded > MAX_DOWNLOAD:
                raise RuntimeError("DETER ZIP over size budget")
            with zipfile.ZipFile(archive) as source:
                names = source.namelist()
                if source.testzip() is not None:
                    raise RuntimeError("DETER ZIP checksum invalid")
                shp = [n for n in names if n.lower().endswith(".shp")]
                if len(shp) != 1 or sum(f.file_size for f in source.infolist()) > 2 * 1024**3:
                    raise RuntimeError("Unexpected DETER archive")
            selected = Path(temp) / "selected.geojsonl"
            subprocess.run(
                [
                    "ogr2ogr",
                    "-f",
                    "GeoJSONSeq",
                    str(selected),
                    "/vsizip/" + str(archive.resolve()) + "/" + shp[0],
                    "-where",
                    f"VIEW_DATE >= '{start}' AND VIEW_DATE <= '{end}'",
                    "-select",
                    "FID,CLASSNAME,VIEW_DATE,MUNICIPALI,UF",
                    "-t_srs",
                    "EPSG:4326",
                    "-limit",
                    str(MAX_RECORDS + 1),
                ],
                check=True,
                timeout=180,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if selected.stat().st_size > 256 * 1024 * 1024:
                raise RuntimeError("DETER selected data over budget")
            cursor.execute(
                "CREATE TEMP TABLE deter_staging (LIKE deter_alerts INCLUDING ALL) ON COMMIT DROP"
            )
            received = rejected = 0
            with selected.open() as features:
                for line in features:
                    if not line.strip():
                        continue
                    received += 1
                    if received > MAX_RECORDS:
                        raise RuntimeError("DETER record budget exceeded")
                    original = json.loads(line.lstrip("\x1e"))
                    props = {k.lower(): v for k, v in original["properties"].items()}
                    feature = dict(
                        id=props["fid"],
                        geometry=original["geometry"],
                        properties=dict(
                            view_date=props["view_date"],
                            classname=props["classname"],
                            municipality=props.get("municipali"),
                            uf=props.get("uf"),
                        ),
                    )
                    row = normalize_feature(feature)
                    if row is None:
                        rejected += 1
                        continue
                    cursor.execute(
                        """INSERT INTO deter_staging VALUES
                        (%s,%s,%s,%s,%s,%s,ST_SetSRID(ST_GeomFromWKB(decode(%s,'hex')),4326))
                        ON CONFLICT(id) DO NOTHING""",
                        row,
                    )
            cursor.execute("SELECT count(*) AS n FROM deter_staging")
            count = cursor.fetchone()["n"]
            if received == 0 or count + rejected != received:
                raise RuntimeError("DETER completeness check failed; previous snapshot retained")
            cursor.execute("DELETE FROM deter_alerts")
            cursor.execute("INSERT INTO deter_alerts SELECT * FROM deter_staging")
            cursor.execute(
                """INSERT INTO deter_import_state VALUES(true,now(),%s,%s,%s,%s)
                ON CONFLICT(singleton) DO UPDATE SET fetched_at=excluded.fetched_at,
                period_start=excluded.period_start,period_end=excluded.period_end,
                records=excluded.records,rejected=excluded.rejected""",
                (start, end, count, rejected),
            )
            cursor.execute("ANALYZE deter_alerts")
            return dict(
                records=count,
                rejected=rejected,
                download_bytes=downloaded,
                seconds=round(time.monotonic() - began, 2),
            )


def state():
    with connection(timeout=0.5) as conn, conn.cursor() as c:
        c.execute("SELECT * FROM deter_import_state")
        return c.fetchone()


def nearby(latitude, longitude, radius_m):
    with connection() as conn, conn.cursor() as c:
        c.execute("SET LOCAL statement_timeout='5s'")
        c.execute("SELECT * FROM deter_import_state")
        snapshot = c.fetchone()
        if not snapshot:
            raise RuntimeError("DETER not imported")
        # biome membership avoids presenting absence outside Amazônia as covered data.
        c.execute(
            """SELECT EXISTS(SELECT 1 FROM ibge_biomes
            WHERE lower(name) IN ('amazônia','amazonia')
            AND ST_Covers(geom,ST_SetSRID(ST_MakePoint(%s,%s),4326))) AS covered""",
            (longitude, latitude),
        )
        covered = c.fetchone()["covered"]
        delta = radius_m / 100000
        dx = delta / max(0.01, math.cos(math.radians(latitude)))
        c.execute(
            """SELECT class_name, count(*) AS count FROM deter_alerts
            WHERE geom && ST_MakeEnvelope(%s,%s,%s,%s,4326)
            AND ST_DWithin(geom::geography,ST_SetSRID(ST_MakePoint(%s,%s),4326)::geography,%s)
            GROUP BY class_name ORDER BY count(*) DESC,class_name""",
            (
                longitude - dx,
                latitude - delta,
                longitude + dx,
                latitude + delta,
                longitude,
                latitude,
                radius_m,
            ),
        )
        classes = c.fetchall()
    return {
        **snapshot,
        "source": SOURCE,
        "coverage": "DETER Amazônia",
        "covered": covered,
        "radius_m": radius_m,
        "classes": classes,
        "total": sum(row["count"] for row in classes),
        "stale": datetime.now(UTC) - snapshot["fetched_at"] > timedelta(days=3),
    }


def render_tile(z, x, y):
    """Render only the viewport; simplify in SQL and cap response geometry complexity."""
    from app.config import get_settings
    from app.services.vector_raster_tiles import VectorRasterTileService

    with connection() as conn, conn.cursor() as c:
        c.execute("SET LOCAL statement_timeout='5s'")
        c.execute(
            """WITH bounds AS (SELECT ST_TileEnvelope(%s,%s,%s) AS geom)
            SELECT ST_AsBinary(ST_Intersection(ST_SimplifyPreserveTopology(
                ST_Transform(a.geom,3857),%s),b.geom)) AS geom
            FROM deter_alerts a,bounds b
            WHERE a.geom && ST_Transform(b.geom,4326) LIMIT 2001""",
            (z, x, y, 40075016.686 / (2**z) / 512),
        )
        rows = c.fetchall()
    if len(rows) > 2000:
        raise RuntimeError("Aproxime o mapa para visualizar os avisos DETER")
    image = Image.new("RGBA", (256, 256))
    draw = ImageDraw.Draw(image, "RGBA")
    from shapely import from_wkb

    service = VectorRasterTileService(get_settings())
    bounds = service._tile_bounds(z, x, y)
    # Reuse polygon drawing mechanics with a dedicated orange highlight.
    for row in rows:
        service._draw(
            draw, from_wkb(bytes(row["geom"])), "population-density", {"density_km2": 2000}, *bounds
        )
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


@lru_cache(maxsize=256)
def cached_tile(version, z, x, y):
    return render_tile(z, x, y)


@lru_cache(maxsize=1)
def catalog_state(bucket):
    try:
        return state()
    except Exception:
        return None
