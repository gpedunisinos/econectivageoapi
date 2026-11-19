from app.services.vector_raster_tiles import VectorRasterTileService


def test_tile_bounds_are_ordered() -> None:
    min_x, min_y, max_x, max_y = VectorRasterTileService._tile_bounds(4, 5, 9)
    assert min_x < max_x
    assert min_y < max_y


def test_empty_clipped_geometries_do_not_break_tile() -> None:
    from PIL import Image, ImageDraw
    from shapely.geometry import GeometryCollection, LineString, Polygon

    from app.config import Settings

    image = Image.new("RGBA", (256, 256))
    service = VectorRasterTileService(Settings())
    for geometry in (Polygon(), LineString(), GeometryCollection([Polygon()])):
        service._draw(ImageDraw.Draw(image), geometry, "population-density", {}, 0, 0, 1, 1)
    assert image.getbbox() is None


def test_empty_part_keeps_visible_polygon() -> None:
    from PIL import Image, ImageDraw
    from shapely.geometry import GeometryCollection, Polygon

    from app.config import Settings

    image = Image.new("RGBA", (256, 256))
    geometry = GeometryCollection([Polygon(), Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])])
    VectorRasterTileService(Settings())._draw(
        ImageDraw.Draw(image), geometry, "population-density", {}, 0, 0, 1, 1
    )
    assert image.getbbox() is not None
