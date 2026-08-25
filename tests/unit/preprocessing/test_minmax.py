import importlib
import sys

import numpy as np
import pytest

from rubem.cli import main
from rubem.preprocessing._io import PreprocessingError, read_raster, write_geotiff
from rubem.preprocessing.minmax_series import minmax, series_extremes
from tests.helpers.compare import ensure_gdal_drivers

TRANSFORM = (0.0, 500.0, 0.0, 1500.0, 0.0, -500.0)
LOCAL_CRS = 'LOCAL_CS["Engineering grid",UNIT["metre",1]]'


def series(directory, nodata=-9999.0):
    """Three 2x2 rasters; cell (0,0) is missing in the first two, cell (1,1) everywhere."""
    ensure_gdal_drivers()
    directory.mkdir(parents=True, exist_ok=True)
    layers = [
        np.array([[nodata, 5.0], [1.0, nodata]], dtype=np.float32),
        np.array([[nodata, 2.0], [7.0, nodata]], dtype=np.float32),
        np.array([[3.0, 9.0], [4.0, nodata]], dtype=np.float32),
    ]
    return [
        write_geotiff(directory / f"ndvi{i}.tif", layer, TRANSFORM, nodata=nodata)
        for i, layer in enumerate(layers, 1)
    ]


class TestSeriesExtremes:
    @pytest.mark.unit
    def test_missing_cells_are_ignored(self, tmp_path):
        files = series(tmp_path / "in")

        minimum, maximum, valid, reference = series_extremes([tmp_path / "in"])

        assert valid.tolist() == [[True, True], [True, False]]
        assert minimum[0, 0] == 3.0 and maximum[0, 0] == 3.0
        assert minimum[0, 1] == 2.0 and maximum[0, 1] == 9.0
        assert minimum[1, 0] == 1.0 and maximum[1, 0] == 7.0
        assert reference.source == str(files[0])

    @pytest.mark.unit
    def test_geometry_must_match(self, tmp_path):
        series(tmp_path / "in")
        ensure_gdal_drivers()
        write_geotiff(tmp_path / "in" / "ndvi4.tif", np.ones((3, 3), np.float32), TRANSFORM)

        with pytest.raises(PreprocessingError, match="does not share the geometry"):
            series_extremes([tmp_path / "in"])

    @pytest.mark.unit
    def test_inputs_must_exist_and_contain_rasters(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            series_extremes([tmp_path / "absent"])
        (tmp_path / "empty").mkdir()
        with pytest.raises(PreprocessingError, match="No raster in the series"):
            series_extremes([tmp_path / "empty"])


class TestMinMax:
    @pytest.mark.unit
    def test_writes_float32_geotiffs_with_no_data_where_nothing_was_valid(self, tmp_path):
        series(tmp_path / "in")

        written_min, written_max = minmax(
            [tmp_path / "in"], tmp_path / "min.tif", tmp_path / "max.tif"
        )

        minimum = read_raster(written_min)
        maximum = read_raster(written_max)
        assert minimum.array.dtype == np.float32 and minimum.nodata == -9999.0
        assert minimum.array.tolist() == [[3.0, 2.0], [1.0, -9999.0]]
        assert maximum.array.tolist() == [[3.0, 9.0], [7.0, -9999.0]]
        assert minimum.geotransform == pytest.approx(TRANSFORM)

    @pytest.mark.unit
    def test_the_georeference_lends_its_crs_and_checks_the_geometry(self, tmp_path):
        series(tmp_path / "in")
        ensure_gdal_drivers()
        georeference = write_geotiff(
            tmp_path / "georef.tif", np.ones((2, 2), np.float32), TRANSFORM, LOCAL_CRS
        )

        written_min, _ = minmax(
            [tmp_path / "in"], tmp_path / "min.tif", tmp_path / "max.tif", georeference, nodata=-1.0
        )

        data = read_raster(written_min)
        assert (
            "Engineering grid" in data.projection
            and data.nodata == -1.0
            and data.array[1, 1] == -1.0
        )
        other = write_geotiff(tmp_path / "other.tif", np.ones((3, 3), np.float32), TRANSFORM)
        with pytest.raises(PreprocessingError, match="does not share the geometry"):
            minmax([tmp_path / "in"], tmp_path / "min2.tif", tmp_path / "max2.tif", other)

    @pytest.mark.unit
    def test_identical_minimum_and_maximum_paths_are_refused(self, tmp_path):
        series(tmp_path / "in")

        with pytest.raises(PreprocessingError, match="would both be written"):
            minmax([tmp_path / "in"], tmp_path / "extreme.tif", tmp_path / "extreme.tif")

        # Different spellings of the same file resolve to one path too.
        (tmp_path / "sub").mkdir()
        with pytest.raises(PreprocessingError, match="would both be written"):
            minmax(
                [tmp_path / "in"],
                tmp_path / "sub" / ".." / "extreme.tif",
                tmp_path / "extreme.tif",
            )
        assert not (tmp_path / "extreme.tif").exists()


class TestCommand:
    @pytest.mark.unit
    def test_minmax_command_prints_the_outputs(self, tmp_path, capsys, restore_logging):
        series(tmp_path / "in")

        main(
            [
                "preprocess",
                "minmax",
                str(tmp_path / "in"),
                "--min",
                str(tmp_path / "min.tif"),
                "--max",
                str(tmp_path / "max.tif"),
            ]
        )

        assert capsys.readouterr().out.splitlines() == [
            str(tmp_path / "min.tif"),
            str(tmp_path / "max.tif"),
        ]

    @pytest.mark.unit
    def test_errors_exit_with_one(self, tmp_path, capsys, restore_logging):
        (tmp_path / "empty").mkdir()

        with pytest.raises(SystemExit) as error:
            main(
                [
                    "preprocess",
                    "minmax",
                    str(tmp_path / "empty"),
                    "--min",
                    "a.tif",
                    "--max",
                    "b.tif",
                ]
            )

        assert error.value.code == 1 and "No raster in the series" in capsys.readouterr().err


class TestDeprecatedModule:
    @pytest.mark.unit
    def test_importing_the_legacy_module_warns(self):
        sys.modules.pop("rubem.preprocessing.minmax", None)

        with pytest.warns(DeprecationWarning, match="minmax_series"):
            importlib.import_module("rubem.preprocessing.minmax")
