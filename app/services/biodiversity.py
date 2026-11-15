"""Public iNaturalist observations: bounded queries, persistent cache and shared quota."""

import hashlib
import json
import math
import sqlite3
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from app.config import Settings

LICENSES = {"cc0", "cc-by", "cc-by-sa"}


class BiodiversityUnavailable(Exception):
    pass


def distance_m(lat: float, lng: float, other_lat: float, other_lng: float) -> float:
    p1, p2 = math.radians(lat), math.radians(other_lat)
    a = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(other_lng - lng) / 2) ** 2
    )
    return 6371000 * 2 * math.asin(min(1, math.sqrt(a)))


class BiodiversityService:
    def __init__(self, settings: Settings):
        self.settings = settings

    @contextmanager
    def _database(self):
        path = Path(self.settings.biodiversity_cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=5)
        db.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, body TEXT, expires REAL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS quota (id INTEGER PRIMARY KEY, day TEXT, "
            "count INTEGER, next_at REAL)"
        )
        db.execute("INSERT OR IGNORE INTO quota VALUES (1, '', 0, 0)")
        db.commit()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _fetch(self, params: dict) -> tuple[dict, bool, str]:
        key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
        now = time.time()
        with self._database() as db:
            row = db.execute("SELECT body, expires FROM cache WHERE key = ?", (key,)).fetchone()
            if row and row[1] > now:
                cached = json.loads(row[0])
                return cached["data"], True, cached["fetched_at"]
            # SQLite serializes quota reservations across workers/processes using this cache file.
            db.execute("BEGIN IMMEDIATE")
            day, count, next_at = db.execute("SELECT day, count, next_at FROM quota").fetchone()
            today = datetime.now(UTC).date().isoformat()
            count = count if day == today else 0
            if now < next_at or count >= self.settings.biodiversity_daily_limit:
                raise BiodiversityUnavailable("Consulta temporariamente limitada. Tente novamente.")
            db.execute(
                "UPDATE quota SET day=?, count=?, next_at=? WHERE id=1",
                (today, count + 1, now + 1.1),
            )
            db.commit()
        request = Request(
            "https://api.inaturalist.org/v1/observations?" + urlencode(params),
            headers={"User-Agent": "EducacaoOnLIFE-GeoAPI/1.0", "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=15) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise ValueError("Response too large")
                data = json.loads(raw)
                if not isinstance(data.get("results"), list):
                    raise ValueError("Invalid response")
        except HTTPError as error:
            if error.code == 429:
                with self._database() as db:
                    db.execute("UPDATE quota SET next_at=? WHERE id=1", (time.time() + 60,))
            raise BiodiversityUnavailable("iNaturalist temporariamente indisponível.") from error
        except (URLError, TimeoutError, ValueError, OSError) as error:
            raise BiodiversityUnavailable("iNaturalist temporariamente indisponível.") from error
        fetched_at = datetime.now(UTC).isoformat()
        # Retain only public fields used by the UI, not upstream profiles/comments/private data.
        observations = [item for record in data["results"] if (item := self._observation(record))]
        normalized = {
            "total_results": data.get("total_results", 0),
            "sampled_records": len(data["results"]),
            "observations": observations,
        }
        with self._database() as db:
            db.execute("DELETE FROM cache WHERE expires < ?", (now,))
            db.execute(
                "INSERT OR REPLACE INTO cache VALUES (?, ?, ?)",
                (
                    key,
                    json.dumps({"data": normalized, "fetched_at": fetched_at}),
                    now + self.settings.biodiversity_cache_seconds,
                ),
            )
        return normalized, False, fetched_at

    @staticmethod
    def _observation(record: dict) -> dict | None:
        taxon = record.get("taxon") or {}
        # Exclude unidentified/general taxa: the section promises species, not higher ranks.
        if taxon.get("rank") not in {"species", "subspecies", "variety", "form", "hybrid"}:
            return None
        photo = next(
            (
                p.get("photo", {})
                for p in record.get("observation_photos", [])
                if p.get("photo", {}).get("license_code") in LICENSES
                and not p.get("photo", {}).get("hidden")
            ),
            None,
        )
        if not photo:
            return None
        photo_url = photo.get("url", "")
        parsed = urlparse(photo_url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "inaturalist-open-data.s3.amazonaws.com",
            "static.inaturalist.org",
        }:
            return None
        coords = (record.get("geojson") or {}).get("coordinates")
        if not isinstance(coords, list) or len(coords) != 2:
            return None
        lng, lat = coords
        if not isinstance(lat, int | float) or not isinstance(lng, int | float):
            return None
        if not math.isfinite(lat) or not math.isfinite(lng) or not (-90 <= lat <= 90):
            return None
        if not -180 <= lng <= 180 or not record.get("id") or not taxon.get("id"):
            return None
        return {
            "id": record["id"],
            "taxon_id": taxon["id"],
            "scientific_name": taxon.get("name", ""),
            "common_name": taxon.get("preferred_common_name"),
            "observed_on": record.get("observed_on"),
            "latitude": lat,
            "longitude": lng,
            "approximate_location": bool(
                record.get("obscured") or record.get("geoprivacy") or record.get("taxon_geoprivacy")
            ),
            "accuracy_m": record.get("positional_accuracy"),
            "url": f"https://www.inaturalist.org/observations/{int(record['id'])}",
            "photo_url": photo_url.replace("/square.", "/medium."),
            "photo_attribution": photo.get("attribution", "iNaturalist"),
            "photo_license": photo["license_code"],
        }

    def query(
        self,
        *,
        latitude=None,
        longitude=None,
        radius_m=1000,
        north=None,
        south=None,
        east=None,
        west=None,
    ) -> dict:
        params = {
            "taxon_id": 1,
            "photos": "true",
            "verifiable": "true",
            "photo_license": ",".join(sorted(LICENSES)),
            "locale": "pt-BR",
            "order_by": "observed_on",
            "order": "desc",
            "per_page": 200,
        }
        nearby = latitude is not None
        if nearby:
            params.update(lat=latitude, lng=longitude, radius=radius_m / 1000)
        else:
            params.update(nelat=north, nelng=east, swlat=south, swlng=west)
        data, cached, fetched_at = self._fetch(params)
        observations = []
        seen = set()
        for item in data["observations"]:
            item = dict(item)
            if nearby:
                if item["taxon_id"] in seen:
                    continue
                seen.add(item["taxon_id"])
                item["distance_m"] = round(
                    distance_m(latitude, longitude, item["latitude"], item["longitude"])
                )
            observations.append(item)
            if len(observations) >= (12 if nearby else 100):
                break
        return {
            "source": "iNaturalist",
            "fetched_at": fetched_at,
            "cached": cached,
            "radius_m": radius_m if nearby else None,
            "limit": 12 if nearby else 100,
            "sampled_records": data["sampled_records"],
            "total_matching_observations": data["total_results"],
            "limited": data["total_results"] > data["sampled_records"]
            or len(data["observations"]) > len(observations),
            "observations": observations,
        }
