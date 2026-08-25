import numpy as np
import pytest

from rubem.configuration.output_format import OutputFileFormat
from rubem.configuration.output_raster_base import OutputRasterBase
from rubem.file._file_generators import report
from tests.helpers.compare import ensure_gdal_drivers
from tests.helpers.synthetic import (
    CELL_SIZE,
    COLS,
    MISSING,
    NORTH,
    ROWS,
    WEST,
    write_synthetic_dataset,
)


def _build_field():
    import pcraster as pcr

    pcr.setclone(ROWS, COLS, CELL_SIZE, WEST, NORTH)
    array = np.arange(ROWS * COLS, dtype=np.float32).reshape(ROWS, COLS)
    array[0, 0] = MISSING
    return pcr.numpy2pcr(pcr.Scalar, array, MISSING), array


class TestReport:
    @pytest.mark.unit
    def test_writes_geotiff_with_timestep_suffix(self, tmp_path):
        config = write_synthetic_dataset(tmp_path)
        base_raster_info = OutputRasterBase(config["RASTERS"]["dem"])
        variable, array = _build_field()

        report(variable, "itp", tmp_path, base_raster_info, timestep=1)

        out_file = tmp_path / "itp0000001.tif"
        assert out_file.exists()
        self._assert_raster_matches(out_file, array, base_raster_info)

    @pytest.mark.unit
    def test_writes_geotiff_without_timestep(self, tmp_path):
        config = write_synthetic_dataset(tmp_path)
        base_raster_info = OutputRasterBase(config["RASTERS"]["dem"])
        variable, array = _build_field()

        report(variable, "itp", tmp_path, base_raster_info)

        out_file = tmp_path / "itp.tif"
        assert out_file.exists()
        assert not (tmp_path / "itp0000000.tif").exists()
        self._assert_raster_matches(out_file, array, base_raster_info)

    @pytest.mark.unit
    def test_accepts_pathlib_outpath(self, tmp_path):
        config = write_synthetic_dataset(tmp_path)
        base_raster_info = OutputRasterBase(config["RASTERS"]["dem"])
        variable, _ = _build_field()

        report(variable, "itp", tmp_path, base_raster_info)

        assert (tmp_path / "itp.tif").exists()

    @pytest.mark.unit
    def test_unsupported_format_raises_and_writes_nothing(self, tmp_path):
        config = write_synthetic_dataset(tmp_path)
        base_raster_info = OutputRasterBase(config["RASTERS"]["dem"])
        variable, _ = _build_field()
        outpath = tmp_path / "out2"
        outpath.mkdir()

        with pytest.raises(ValueError):
            report(
                variable,
                "itp",
                outpath,
                base_raster_info,
                file_format=OutputFileFormat.PCRASTER,
            )

        assert not any(outpath.iterdir())

    @staticmethod
    def _assert_raster_matches(out_file, array, base_raster_info):
        ensure_gdal_drivers()
        from osgeo import gdal

        dataset = gdal.OpenEx(str(out_file), gdal.GA_ReadOnly)
        try:
            band = dataset.GetRasterBand(1)
            assert gdal.GetDataTypeName(band.DataType) == "Float32"
            assert band.GetNoDataValue() == pytest.approx(-9999)
            assert dataset.GetMetadata("IMAGE_STRUCTURE")["COMPRESSION"] == "LZW"
            assert dataset.GetGeoTransform() == pytest.approx(base_raster_info.transformation)

            read_array = band.ReadAsArray()
            expected = array.copy()
            expected[0, 0] = -9999
            np.testing.assert_allclose(read_array, expected)
        finally:
            dataset = None
