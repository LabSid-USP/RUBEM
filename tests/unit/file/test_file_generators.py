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


def _build_field_with_zero_and_missing():
    """One genuine zero-valued cell and one genuinely missing cell."""
    import pcraster as pcr

    pcr.setclone(ROWS, COLS, CELL_SIZE, WEST, NORTH)
    array = np.arange(ROWS * COLS, dtype=np.float32).reshape(ROWS, COLS)
    array[0, 0] = 0.0
    array[1, 1] = MISSING
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

    @pytest.mark.unit
    def test_a_legitimate_zero_cell_survives_the_round_trip(self, tmp_path):
        """A real data cell equal to 0 must not be confused with no-data.

        This is what ``finite_float32`` (``rubem.configuration.model_configuration_file``)
        guards against: a no-data value that underflows to 0.0 in Float32
        would collide with a cell like this one. With a proper no-data
        value (-9999, distinct from 0), the zero cell and a genuinely
        missing cell must both round-trip unchanged and stay distinguishable.
        """
        config = write_synthetic_dataset(tmp_path)
        base_raster_info = OutputRasterBase(config["RASTERS"]["dem"])
        variable, array = _build_field_with_zero_and_missing()

        report(variable, "itp", tmp_path, base_raster_info, timestep=1, no_data_value=-9999)

        out_file = tmp_path / "itp0000001.tif"
        ensure_gdal_drivers()
        from osgeo import gdal

        dataset = gdal.OpenEx(str(out_file), gdal.GA_ReadOnly)
        try:
            band = dataset.GetRasterBand(1)
            assert band.GetNoDataValue() == pytest.approx(-9999)
            read_array = band.ReadAsArray()
            assert read_array[0, 0] == 0.0, "a legitimate zero cell must not read as no-data"
            assert read_array[1, 1] == pytest.approx(-9999), "a missing cell must read as no-data"
            expected = array.copy()
            expected[1, 1] = -9999
            np.testing.assert_allclose(read_array, expected)
        finally:
            dataset = None

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


class TestReportFailures:
    @pytest.mark.unit
    def test_an_unwritable_destination_raises_without_leaving_a_file(self, tmp_path):
        config = write_synthetic_dataset(tmp_path)
        base_raster_info = OutputRasterBase(config["RASTERS"]["dem"])
        variable, _ = _build_field()
        blocked = tmp_path / "blocked"
        blocked.write_text("a file where the output directory should be", encoding="utf8")

        with pytest.raises(RuntimeError, match="Could not write the raster"):
            report(variable, "itp", blocked, base_raster_info, timestep=1)

        assert blocked.is_file()

    @pytest.mark.unit
    def test_a_failure_after_creation_removes_the_partial_file(self, tmp_path, monkeypatch):
        from osgeo import gdal

        config = write_synthetic_dataset(tmp_path)
        base_raster_info = OutputRasterBase(config["RASTERS"]["dem"])
        variable, _ = _build_field()

        def refuse(self, transformation):
            raise RuntimeError("the transform cannot be written")

        monkeypatch.setattr(gdal.Dataset, "SetGeoTransform", refuse)

        with pytest.raises(RuntimeError, match="the transform cannot be written"):
            report(variable, "itp", tmp_path, base_raster_info, timestep=1)

        assert not (tmp_path / "itp0000001.tif").exists()

    @pytest.mark.unit
    def test_the_projection_of_the_base_raster_is_written(self, tmp_path):
        """A local engineering CRS is used so that the test does not depend on
        the PROJ database being available."""
        from rubem.configuration.output_raster_base import read_raster_geometry

        config = write_synthetic_dataset(tmp_path)
        cols, rows, transformation, _ = read_raster_geometry(config["RASTERS"]["dem"])
        ensure_gdal_drivers()
        from osgeo import gdal

        gdal.UseExceptions()
        georeference = tmp_path / "georeference.tif"
        dataset = gdal.GetDriverByName("GTiff").Create(
            str(georeference), cols, rows, 1, gdal.GDT_Float32
        )
        dataset.SetGeoTransform(transformation)
        dataset.SetProjection('LOCAL_CS["Engineering grid",UNIT["metre",1]]')
        dataset = None
        base_raster_info = OutputRasterBase(
            config["RASTERS"]["dem"], georeference_path=georeference
        )
        variable, _ = _build_field()

        report(variable, "itp", tmp_path, base_raster_info, timestep=1)

        dataset = gdal.OpenEx(str(tmp_path / "itp0000001.tif"), gdal.GA_ReadOnly)
        try:
            assert "Engineering grid" in dataset.GetProjection()
        finally:
            dataset = None
