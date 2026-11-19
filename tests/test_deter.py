from datetime import UTC, datetime

from fastapi.testclient import TestClient
from shapely import from_wkb

from app.config import get_settings
from app.main import app
from app.services.deter import normalize_feature


def feature(coords, id="same_id"):
    return {
        "id": id,
        "properties": {"view_date": "2026-11-01", "classname": "DESMATAMENTO_CR"},
        "geometry": {"type": "Polygon", "coordinates": [coords]},
    }


def test_repeated_source_ids_do_not_drop_different_notices():
    a = normalize_feature(feature([[0, 0], [1, 0], [1, 1], [0, 0]]))
    b = normalize_feature(feature([[0, 0], [2, 0], [2, 1], [0, 0]]))
    assert a[0] != b[0]
    assert a[1] == b[1]


def test_repair_and_empty_geometry():
    row = normalize_feature(feature([[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]))
    assert from_wkb(bytes.fromhex(row[-1])).is_valid
    assert normalize_feature(feature([[0, 0], [0, 0], [0, 0], [0, 0]])) is None


def test_deter_auth_validation_and_coverage(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "test-token")
    get_settings.cache_clear()
    client = TestClient(app)
    assert client.get("/deter/nearby?latitude=0&longitude=0").status_code == 401
    headers = {"Authorization": "Bearer test-token"}
    assert client.get("/deter/nearby?latitude=nan&longitude=0", headers=headers).status_code == 422
    assert (
        client.get("/deter/nearby?latitude=0&longitude=0&radius_m=999", headers=headers).status_code
        == 422
    )
    monkeypatch.setattr(
        "app.api.deter.nearby",
        lambda *args: dict(
            source="https://terrabrasilis.dpi.inpe.br/",
            coverage="DETER Amazônia",
            covered=False,
            fetched_at=datetime.now(UTC),
            period_start="2025-11-19",
            period_end="2026-11-19",
            records=1500,
            rejected=1,
            radius_m=1000,
            classes=[],
            total=0,
            stale=False,
        ),
    )
    result = client.get("/deter/nearby?latitude=-30&longitude=-51", headers=headers)
    assert result.status_code == 200
    assert result.json()["covered"] is False
    get_settings.cache_clear()


def test_deter_unavailable_is_not_zero(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "test-token")
    get_settings.cache_clear()

    def unavailable(*args):
        raise RuntimeError("database offline")

    monkeypatch.setattr("app.api.deter.nearby", unavailable)
    assert (
        TestClient(app)
        .get("/deter/nearby?latitude=0&longitude=0", headers={"Authorization": "Bearer test-token"})
        .status_code
        == 503
    )
    get_settings.cache_clear()


def test_failed_or_oversized_archive_keeps_last_snapshot(monkeypatch, tmp_path):
    import json
    import zipfile
    from contextlib import contextmanager
    from pathlib import Path

    import pytest

    from app.services import deter

    commands = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, query, args=None):
            commands.append(query)

        def fetchone(self):
            if "advisory" in commands[-1]:
                return {"locked": True}
            if "import_state" in commands[-1]:
                return None
            return {"n": 0}

    class Conn:
        def cursor(self):
            return Cursor()

    @contextmanager
    def fake_connection():
        try:
            yield Conn()
        except Exception:
            commands.append("ROLLBACK")
            raise

    archive = tmp_path / "data.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("public.shp", "fixture")
    monkeypatch.setattr(deter, "connection", fake_connection)
    import subprocess

    def empty_conversion(args, **kwargs):
        Path(args[3]).write_text("")

    monkeypatch.setattr(subprocess, "run", empty_conversion)
    with pytest.raises(RuntimeError, match="completeness"):
        deter.sync_snapshot(force=True, archive_path=archive)
    assert "ROLLBACK" in commands
    assert not any("DELETE FROM deter_alerts" in q for q in commands)

    def oversized_conversion(args, **kwargs):
        value = {
            "properties": {"FID": "1", "CLASSNAME": "X", "VIEW_DATE": "2026-11-01"},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        }
        Path(args[3]).write_text(json.dumps(value) + "\n")

    monkeypatch.setattr(subprocess, "run", oversized_conversion)
    monkeypatch.setattr(deter, "MAX_RECORDS", 0)
    with pytest.raises(RuntimeError, match="record budget"):
        deter.sync_snapshot(force=True, archive_path=archive)
    assert not any("DELETE FROM deter_alerts" in q for q in commands)
