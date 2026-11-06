from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import Settings


class EsriTileService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def fetch(self, z: int, x: int, y: int) -> tuple[bytes, str, str | None]:
        if z < 0 or z > 19 or x < 0 or y < 0:
            raise ValueError("Coordenadas do tile inválidas")
        token = self.settings.esri_basemap_token
        if not token:
            raise RuntimeError("ESRI_BASEMAP_TOKEN não configurado")
        base_url = self.settings.esri_basemap_url.format(z=z, x=x, y=y)
        separator = "&" if "?" in base_url else "?"
        request = Request(
            f"{base_url}{separator}{urlencode({'token': token})}",
            headers={"User-Agent": "unisinos-usp-geo-api/0.1"},
        )
        with urlopen(request, timeout=self.settings.esri_timeout_seconds) as response:
            content_type = response.headers.get_content_type()
            if not content_type.startswith("image/"):
                raise RuntimeError("O provedor não retornou uma imagem")
            return response.read(), content_type, response.headers.get("Cache-Control")
