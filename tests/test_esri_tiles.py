from email.message import Message

from app.config import Settings
from app.services.esri_tiles import EsriTileService


class FakeResponse:
    def __init__(self) -> None:
        self.headers = Message()
        self.headers["Content-Type"] = "image/jpeg"
        self.headers["Cache-Control"] = "public, max-age=300"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return b"jpeg"


def test_fetches_esri_tile_with_server_side_token(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.services.esri_tiles.urlopen", fake_urlopen)
    settings = Settings(
        _env_file=None,
        api_token="test-token",
        esri_basemap_token="private-token",
    )
    content, content_type, cache = EsriTileService(settings).fetch(8, 91, 150)
    assert content == b"jpeg"
    assert content_type == "image/jpeg"
    assert cache == "public, max-age=300"
    assert "private-token" in captured["url"]
