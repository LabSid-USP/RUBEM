import os
from pathlib import Path

import pytest

from rubem.configuration.output_raster_base import OutputRasterBase
from tests.helpers.compare import ensure_gdal_drivers
from tests.helpers.config import BASE_DATA_DIR
from tests.helpers.synthetic import CELL_SIZE, COLS, NORTH, ROWS, WEST, write_synthetic_dataset

FIXTURE_DEM_TIF = os.path.join(BASE_DATA_DIR, "maps", "dem", "dem.tif")


class TestOutputRasterBase:
    @pytest.mark.unit
    def test_reads_dimensions_and_transformation_from_pcraster_map(self, tmp_path):
        config = write_synthetic_dataset(tmp_path)

        base_raster = OutputRasterBase(config["RASTERS"]["dem"])

        assert base_raster.cols == COLS
        assert base_raster.rows == ROWS
        transformation = base_raster.transformation
        assert len(transformation) == 6
        assert transformation[0] == pytest.approx(WEST)
        assert transformation[3] == pytest.approx(NORTH)
        assert transformation[1] == pytest.approx(CELL_SIZE)
        assert transformation[5] == pytest.approx(-CELL_SIZE)

    @pytest.mark.unit
    def test_reads_dimensions_and_transformation_from_geotiff(self):
        ensure_gdal_drivers()
        from osgeo import gdal

        base_raster = OutputRasterBase(FIXTURE_DEM_TIF)

        dataset = gdal.OpenEx(FIXTURE_DEM_TIF, gdal.GA_ReadOnly)
        try:
            assert base_raster.cols == dataset.RasterXSize
            assert base_raster.rows == dataset.RasterYSize
            assert base_raster.transformation == dataset.GetGeoTransform()
        finally:
            dataset = None

    @pytest.mark.unit
    def test_accepts_pathlib_path(self):
        base_raster = OutputRasterBase(Path(FIXTURE_DEM_TIF))

        assert base_raster.cols > 0
        assert base_raster.rows > 0

    @pytest.mark.unit
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            OutputRasterBase(tmp_path / "absent.tif")
