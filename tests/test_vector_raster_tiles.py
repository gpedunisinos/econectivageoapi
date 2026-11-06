from app.services.vector_raster_tiles import VectorRasterTileService


def test_tile_bounds_are_ordered() -> None:
    min_x, min_y, max_x, max_y = VectorRasterTileService._tile_bounds(4, 5, 9)
    assert min_x < max_x
    assert min_y < max_y
