from app.config import Settings
from app.schemas import LayerDefinition, LayerSource, LegendItem

MAPBIOMAS_CLASSES: dict[int, tuple[str, str]] = {
    3: ("Formação florestal", "#1f8d49"),
    4: ("Formação savânica", "#7dc975"),
    5: ("Mangue", "#04381d"),
    9: ("Silvicultura", "#7a5900"),
    11: ("Campo alagado e área pantanosa", "#519799"),
    12: ("Formação campestre", "#d6bc74"),
    15: ("Pastagem", "#edde8e"),
    18: ("Agricultura", "#e974ed"),
    21: ("Mosaico de usos", "#ffefc3"),
    24: ("Área urbanizada", "#d4271e"),
    25: ("Outras áreas não vegetadas", "#db4d4f"),
    29: ("Afloramento rochoso", "#ad5100"),
    30: ("Mineração", "#9c0027"),
    33: ("Rio, lago e oceano", "#2532e4"),
    49: ("Restinga arbórea", "#02d659"),
    50: ("Restinga herbácea ou arbustiva", "#ffaa5f"),
}

VEGETATION_CLASSES = {3, 4, 5, 6, 9, 11, 12, 32, 49, 50, 77, 84}
BUILT_UP_CLASSES = {24}


def _mapbiomas_legend() -> list[LegendItem]:
    return [
        LegendItem(value=value, label=label, color=color)
        for value, (label, color) in MAPBIOMAS_CLASSES.items()
    ]


def build_layer_catalog(settings: Settings) -> list[LayerDefinition]:
    from time import monotonic

    from app.services.deter import catalog_state

    try:
        snapshot = catalog_state(int(monotonic() / 30))
    except Exception:
        snapshot = None
    return [
        LayerDefinition(
            id="deter-amazonia",
            name="Avisos DETER — Amazônia",
            description="Avisos dos últimos 365 dias; não representam a taxa PRODES. "
            "Cobertura: Amazônia. Amplie o mapa para visualizar.",
            data_type="raster",
            tile_format="png",
            tile_url="/tiles/deter-amazonia/{z}/{x}/{y}.png",
            attribution="INPE / TerraBrasilis — DETER Amazônia",
            default_opacity=0.75,
            min_zoom=10,
            max_zoom=18,
            available=snapshot is not None,
            legend=[
                LegendItem(
                    value="notice",
                    label="Avisos de alteração da cobertura vegetal",
                    color="#e34a33",
                )
            ],
            source=LayerSource(
                name="INPE — DETER Amazônia",
                version=str(snapshot["fetched_at"]) if snapshot else "Não importado",
                url="https://terrabrasilis.dpi.inpe.br/",
            ),
        ),
        LayerDefinition(
            id="satellite",
            name="Imagem de satélite",
            description="Imagem orbital mundial para inspeção visual do território.",
            data_type="raster",
            tile_format="jpg",
            tile_url="/tiles/satellite/{z}/{x}/{y}.jpg",
            map_role="basemap",
            attribution=("Imagem © Esri, Maxar, Earthstar Geographics e GIS User Community"),
            default_opacity=1,
            min_zoom=0,
            max_zoom=19,
            available=bool(settings.esri_basemap_enabled and settings.esri_basemap_token),
            legend=[],
            source=LayerSource(
                name="Esri World Imagery",
                version="Atualização contínua",
                url="https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9",
            ),
        ),
        LayerDefinition(
            id="land-cover",
            name="Cobertura e uso do solo",
            description="Classes predominantes de cobertura e uso da terra em 10 metros.",
            data_type="raster",
            tile_format="png",
            tile_url="/tiles/land-cover/{z}/{x}/{y}.png",
            default_opacity=0.65,
            min_zoom=7,
            max_zoom=18,
            available=bool(settings.mapbiomas_cog_url),
            legend=_mapbiomas_legend(),
            source=LayerSource(
                name="MapBiomas Brasil 10 m",
                version="Coleção 4 — 2025",
                url="https://brasil.mapbiomas.org/",
            ),
        ),
        LayerDefinition(
            id="vegetation",
            name="Vegetação",
            description="Máscara derivada das classes vegetadas do MapBiomas.",
            data_type="raster",
            tile_format="png",
            tile_url="/tiles/vegetation/{z}/{x}/{y}.png",
            default_opacity=0.65,
            min_zoom=7,
            max_zoom=18,
            available=bool(settings.mapbiomas_cog_url),
            legend=[LegendItem(value=1, label="Vegetação", color="#238b45")],
            source=LayerSource(
                name="MapBiomas Brasil 10 m",
                version="Coleção 4 — 2025",
                url="https://brasil.mapbiomas.org/",
            ),
        ),
        LayerDefinition(
            id="elevation",
            name="Altitude",
            description="Modelo digital de elevação em metros.",
            data_type="raster",
            tile_format="png",
            tile_url="/tiles/elevation/{z}/{x}/{y}.png",
            default_opacity=0.55,
            min_zoom=7,
            max_zoom=16,
            available=bool(settings.elevation_tile_cog_url or settings.elevation_cog_url),
            legend=[
                LegendItem(value=0, label="0 m", color="#2c7bb6"),
                LegendItem(value=500, label="500 m", color="#abd9e9"),
                LegendItem(value=1000, label="1.000 m", color="#fdae61"),
                LegendItem(value=2000, label="2.000 m ou mais", color="#a50026"),
            ],
            source=LayerSource(
                name="TOPODATA/INPE",
                version="MDE nacional derivado SRTM",
                url="https://www.dsr.inpe.br/topodata/",
            ),
        ),
        LayerDefinition(
            id="slope",
            name="Declividade",
            description="Declividade do terreno em porcentagem.",
            data_type="raster",
            tile_format="png",
            tile_url="/tiles/slope/{z}/{x}/{y}.png",
            default_opacity=0.6,
            min_zoom=7,
            max_zoom=16,
            available=bool(settings.slope_tile_cog_url or settings.slope_cog_url),
            legend=[
                LegendItem(value=0, label="0–3%", color="#31a354"),
                LegendItem(value=3, label="3–8%", color="#addd8e"),
                LegendItem(value=8, label="8–20%", color="#fee08b"),
                LegendItem(value=20, label="20–45%", color="#f46d43"),
                LegendItem(value=45, label="Acima de 45%", color="#a50026"),
            ],
            source=LayerSource(
                name="TOPODATA/INPE",
                version="Derivada geomorfométrica nacional",
                url="https://www.dsr.inpe.br/topodata/",
            ),
        ),
        LayerDefinition(
            id="biomes",
            name="Biomas",
            description="Limites dos biomas e sistema costeiro-marinho.",
            data_type="vector",
            tile_format="png",
            tile_url="/tiles/biomes/{z}/{x}/{y}.png",
            default_opacity=0.35,
            min_zoom=3,
            max_zoom=12,
            available=settings.biomes_enabled,
            legend=[
                LegendItem(value="Amazônia", label="Amazônia", color="#1b7837"),
                LegendItem(value="Caatinga", label="Caatinga", color="#d8b365"),
                LegendItem(value="Cerrado", label="Cerrado", color="#80cdc1"),
                LegendItem(value="Mata Atlântica", label="Mata Atlântica", color="#35978f"),
                LegendItem(value="Pampa", label="Pampa", color="#dfc27d"),
                LegendItem(value="Pantanal", label="Pantanal", color="#5ab4ac"),
            ],
            source=LayerSource(
                name="IBGE",
                version="Biomas 1:250.000",
                url="https://www.ibge.gov.br/geociencias/informacoes-ambientais/vegetacao/15842-biomas.html",
            ),
        ),
        LayerDefinition(
            id="hydrography",
            name="Hidrografia",
            description="Trechos da Base Hidrográfica Ottocodificada Multiescalas.",
            data_type="vector",
            tile_format="png",
            tile_url="/tiles/hydrography/{z}/{x}/{y}.png",
            default_opacity=0.8,
            min_zoom=4,
            max_zoom=18,
            available=settings.hydrography_enabled,
            legend=[LegendItem(value="drainage", label="Drenagem", color="#2b8cbe")],
            source=LayerSource(
                name="ANA",
                version="BHO Multiescalas 6",
                url="https://www.gov.br/ana/",
            ),
        ),
        LayerDefinition(
            id="population-density",
            name="Densidade populacional",
            description="Habitantes por km² no setor censitário.",
            data_type="vector",
            tile_format="png",
            tile_url="/tiles/population-density/{z}/{x}/{y}.png",
            default_opacity=0.55,
            min_zoom=6,
            max_zoom=16,
            available=settings.population_enabled,
            legend=[
                LegendItem(value=100, label="Até 100", color="#fff7ec"),
                LegendItem(value=1000, label="100–1.000", color="#fdbb84"),
                LegendItem(value=5000, label="1.000–5.000", color="#e34a33"),
                LegendItem(value=5001, label="Acima de 5.000", color="#7f0000"),
            ],
            source=LayerSource(
                name="IBGE — Censo Demográfico",
                version="2022 — Agregados por setores censitários",
                url="https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html",
            ),
        ),
    ]


def get_layer(settings: Settings, layer_id: str) -> LayerDefinition | None:
    return next((layer for layer in build_layer_catalog(settings) if layer.id == layer_id), None)
