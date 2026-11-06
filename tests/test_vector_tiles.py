from contextlib import contextmanager

from app.config import Settings
from app.providers.vector_tiles import VectorTileProvider


class FakeCursor:
    def __init__(self) -> None:
        self.query = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, query, params) -> None:
        self.query = query
        self.params = params

    def fetchone(self):
        return {"tile": b"tile"}


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self._cursor


def test_vector_tile_filters_in_source_crs_to_use_spatial_index(monkeypatch) -> None:
    cursor = FakeCursor()

    @contextmanager
    def fake_connection():
        yield FakeConnection(cursor)

    monkeypatch.setattr("app.providers.vector_tiles.connection", fake_connection)
    provider = VectorTileProvider(Settings(_env_file=None, api_token="test-token"))

    assert provider.render("hydrography", 12, 1465, 2405) == b"tile"
    assert "source.geom && bounds.source_geom" in cursor.query.as_string()
    assert cursor.params == (12, 1465, 2405, 12, 1465, 2405, "hydrography")
