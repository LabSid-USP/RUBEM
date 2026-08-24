import numpy as np
import pytest
from osgeo import gdal

from tests.helpers.compare import DEFAULT_RTOL, compare_rasters, ensure_gdal_drivers

gdal.UseExceptions()

PIXEL_SIZE = 0.00462962962962963
ORIGIN_X = -49.68709933594866
ORIGIN_Y = -25.225870835125725
GEOTRANSFORM = (ORIGIN_X, PIXEL_SIZE, 0.0, ORIGIN_Y, 0.0, -PIXEL_SIZE)
VALUES = np.arange(9, dtype=np.float32).reshape(3, 3)


def write_raster(path, geotransform=GEOTRANSFORM, values=VALUES):
    """Write a small single-band GeoTIFF and return its path as a string."""
    ensure_gdal_drivers()
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(str(path), values.shape[1], values.shape[0], 1, gdal.GDT_Float32)
    try:
        dataset.SetGeoTransform(geotransform)
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(-9999.0)
        band.WriteArray(values)
    finally:
        dataset = None
    return str(path)


def shifted(dx=0.0, dy=0.0):
    return (ORIGIN_X + dx, PIXEL_SIZE, 0.0, ORIGIN_Y + dy, 0.0, -PIXEL_SIZE)


class TestCompareRasters:
    @pytest.mark.unit
    def test_identical_rasters_are_equal(self, tmp_path):
        first = write_raster(tmp_path / "first.tif")
        second = write_raster(tmp_path / "second.tif")
        result = compare_rasters(first, second)
        assert result.equal, result.report()

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "offsets, component",
        [({"dx": 4.0e-4}, "component 0"), ({"dy": 4.0e-4}, "component 3")],
    )
    def test_origin_shift_is_reported(self, tmp_path, offsets, component):
        """A shift the data ``rtol`` would have accepted must fail.

        With ``rtol`` applied to the geotransform, an origin near -49.687
        degrees accepted a shift of ``rtol * 49.687`` (~5e-4 degrees, tens of
        metres), so a misregistered raster compared equal.
        """
        shift = next(iter(offsets.values()))
        assert shift < DEFAULT_RTOL * abs(ORIGIN_X)
        first = write_raster(tmp_path / "first.tif")
        second = write_raster(tmp_path / "second.tif", geotransform=shifted(**offsets))
        result = compare_rasters(first, second)
        assert not result.equal
        assert component in result.report()

    @pytest.mark.unit
    def test_pixel_size_difference_is_reported(self, tmp_path):
        stretched = (ORIGIN_X, PIXEL_SIZE * 1.001, 0.0, ORIGIN_Y, 0.0, -PIXEL_SIZE)
        first = write_raster(tmp_path / "first.tif")
        second = write_raster(tmp_path / "second.tif", geotransform=stretched)
        result = compare_rasters(first, second)
        assert not result.equal
        assert "component 1" in result.report()

    @pytest.mark.unit
    def test_subpixel_noise_is_tolerated(self, tmp_path):
        """Float64 noise on the coordinates must not fail the comparison."""
        first = write_raster(tmp_path / "first.tif")
        second = write_raster(tmp_path / "second.tif", geotransform=shifted(dy=1e-12))
        result = compare_rasters(first, second)
        assert result.equal, result.report()

    @pytest.mark.unit
    def test_zero_fraction_requires_identical_geotransforms(self, tmp_path):
        first = write_raster(tmp_path / "first.tif")
        second = write_raster(tmp_path / "second.tif", geotransform=shifted(dy=1e-12))
        result = compare_rasters(first, second, geotransform_fraction=0.0)
        assert not result.equal
        assert "component 3" in result.report()

    @pytest.mark.unit
    def test_values_are_compared_with_the_data_tolerances(self, tmp_path):
        first = write_raster(tmp_path / "first.tif")
        noisy = write_raster(tmp_path / "noisy.tif", values=VALUES * np.float32(1.000001))
        assert compare_rasters(first, noisy).equal
        coarse = write_raster(tmp_path / "coarse.tif", values=VALUES * np.float32(1.001))
        result = compare_rasters(first, coarse)
        assert not result.equal
        assert "beyond rtol" in result.report()
