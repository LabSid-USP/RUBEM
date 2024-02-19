import pytest
import sys

from rubem.configuration.model_configuration import RasterGrid


class TestRasterGridArea:

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "size",
        [-1.0, 0, sys.float_info.max],
    )
    def test_raster_grid_constructor_bad_args(self, size):
        with pytest.raises(Exception):
            _ = RasterGrid(size)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "size",
        [1.0, 1, sys.float_info.min],
    )
    def test_raster_grid_constructor_good_args(self, size):
        _ = RasterGrid(size)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "size, expected",
        [(1, 1), (2, 4), (8, 64)],
    )
    def test_raster_grid_area(self, size, expected):
        rg = RasterGrid(size)
        assert rg.area == expected
