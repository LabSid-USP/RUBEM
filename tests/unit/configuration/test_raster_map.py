import os

import pytest

from rubem.configuration.raster_map import RasterBand, RasterDataRules, RasterMap
from tests.helpers.compare import ensure_gdal_drivers
from tests.helpers.config import BASE_DATA_DIR
from tests.helpers.synthetic import COLS, ROWS, write_synthetic_dataset

FIXTURE_DEM_TIF = os.path.join(BASE_DATA_DIR, "maps", "dem", "dem.tif")


class TestRasterMap:
    @pytest.mark.unit
    def test_reads_a_pcraster_map(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        ensure_gdal_drivers()

        raster_map = RasterMap(config["RASTERS"]["dem"])

        assert raster_map.valid_range is None and raster_map.rules is None
        assert len(raster_map.bands) == 1
        band = raster_map.bands[0]
        assert isinstance(band, RasterBand)
        assert band.index == 1
        assert band.data_array.shape == (ROWS, COLS)
        assert band.min == pytest.approx(100.0) and band.max == pytest.approx(140.0)
        assert "Dimensions: (3, 3)" in str(raster_map)

    @pytest.mark.unit
    def test_reads_a_geotiff_with_range_and_rules(self):
        ensure_gdal_drivers()
        valid_range = {"min": 0.0, "max": 5000.0}
        rules = RasterDataRules.FORBID_ALL_ZEROES | RasterDataRules.FORBID_ALL_ONES

        raster_map = RasterMap(FIXTURE_DEM_TIF, valid_range, rules)

        assert raster_map.valid_range == valid_range
        assert raster_map.rules == rules
        assert len(raster_map.bands) == 1
        assert "WGS 84" in str(raster_map)

    @pytest.mark.unit
    def test_accepts_a_pathlib_path(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        ensure_gdal_drivers()

        raster_map = RasterMap(tmp_path / os.path.relpath(config["RASTERS"]["dem"], tmp_path))

        assert len(raster_map.bands) == 1

    @pytest.mark.unit
    def test_series_members_with_numeric_extensions_are_accepted(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        ensure_gdal_drivers()

        raster_map = RasterMap(os.path.join(config["DIRECTORIES"]["prec"], "prec0000.001"))

        assert len(raster_map.bands) == 1

    @pytest.mark.unit
    def test_a_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Invalid raster file"):
            RasterMap(tmp_path / "absent.tif")

    @pytest.mark.unit
    def test_an_empty_file_raises(self, tmp_path):
        empty = tmp_path / "empty.tif"
        empty.write_bytes(b"")

        with pytest.raises(ValueError, match="Empty raster file"):
            RasterMap(empty, {"min": 0.0, "max": 255.0}, RasterDataRules.FORBID_ALL_ZEROES)

    @pytest.mark.unit
    def test_an_unknown_extension_raises(self, tmp_path):
        other = tmp_path / "raster.xyz"
        other.write_bytes(b"not a raster")

        with pytest.raises(ValueError, match="Invalid raster file extension"):
            RasterMap(other)

    @pytest.mark.unit
    def test_close_releases_the_dataset_and_the_bands(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        ensure_gdal_drivers()

        with RasterMap(config["RASTERS"]["dem"]) as raster_map:
            assert raster_map.raster is not None

        assert raster_map.raster is None
        assert raster_map.bands == []
        assert str(raster_map) == "No raster file loaded"
