import csv
import math
from pathlib import Path

import numpy as np
import pytest

from rubem.cli import main
from rubem.hydrological_processes._pan_coefficient import pan_coefficient
from rubem.preprocessing._io import (
    MANIFEST_NAME,
    PreprocessingError,
    read_raster,
    write_geotiff,
)
from rubem.preprocessing.pan_coefficient_series import OutputFormat, kp_series
from tests.helpers.compare import ensure_gdal_drivers

TRANSFORM = (0.0, 500.0, 0.0, 1500.0, 0.0, -500.0)
LOCAL_CRS = 'LOCAL_CS["Engineering grid",UNIT["metre",1]]'

# Supplement S29, PDF page 9: kp = 0.482 + 0.024 ln(B) - 0.000376 U2 + 0.0045 UR,
# with B the Class A pan border width [m], U2 the wind speed at 2 m [m/s] and
# UR the relative humidity [%].
CASES = [(25.0, 2.0, 70.0), (20.0, 0.5, 45.0), (30.0, 3.25, 88.5)]


def expected_kp(fetch_distance, wind_speed, relative_humidity):
    """The printed coefficients of S29, evaluated in float64 by the test itself."""
    return (
        0.482
        + 0.024 * math.log(fetch_distance)
        - 0.000376 * wind_speed
        + 0.0045 * relative_humidity
    )


def series(directory, values, nodata=-9999.0, name="v", transform=TRANSFORM, crs=""):
    """Write one GeoTIFF per array of ``values``, in natural order."""
    ensure_gdal_drivers()
    directory.mkdir(parents=True, exist_ok=True)
    return [
        write_geotiff(
            directory / f"{name}{step}.tif",
            np.asarray(layer, dtype=np.float32),
            transform,
            crs,
            nodata=nodata,
        )
        for step, layer in enumerate(values, 1)
    ]


def two_member_inputs(tmp_path, wind=None, humidity=None, nodata=-9999.0):
    """A two-member wind speed series and a two-member relative humidity series."""
    wind = wind if wind is not None else [[[1.0, 2.0]], [[3.0, 4.0]]]
    humidity = humidity if humidity is not None else [[[70.0, 60.0]], [[50.0, 40.0]]]
    series(tmp_path / "wind", wind, nodata=nodata, name="u2")
    series(tmp_path / "ur", humidity, nodata=nodata, name="ur")
    return tmp_path / "wind", tmp_path / "ur"


class TestFormula:
    @pytest.mark.unit
    @pytest.mark.parametrize(("fetch_distance", "wind_speed", "relative_humidity"), CASES)
    def test_matches_the_supplement_with_numpy(self, fetch_distance, wind_speed, relative_humidity):
        """Conformity with Supplement S29, PDF page 9, on the numpy path."""
        result = pan_coefficient(
            np.float64(fetch_distance),
            np.float64(wind_speed),
            np.float64(relative_humidity),
            log=np.log,
        )

        assert float(result) == pytest.approx(
            expected_kp(fetch_distance, wind_speed, relative_humidity)
        )

    @pytest.mark.unit
    def test_applies_elementwise_to_arrays(self):
        fetch = np.array([[25.0, 20.0]])
        wind = np.array([[2.0, 0.5]])
        humidity = np.array([[70.0, 45.0]])

        result = pan_coefficient(fetch, wind, humidity, log=np.log)

        assert result[0].tolist() == pytest.approx(
            [expected_kp(25.0, 2.0, 70.0), expected_kp(20.0, 0.5, 45.0)]
        )

    @pytest.mark.unit
    @pytest.mark.parametrize(("fetch_distance", "wind_speed", "relative_humidity"), CASES)
    def test_matches_the_supplement_with_pcraster(
        self, fetch_distance, wind_speed, relative_humidity
    ):
        """Conformity with Supplement S29, PDF page 9, on a 1x1 PCRaster clone."""
        import pcraster as pcr
        from pcraster.framework import generalfunctions

        pcr.setclone(1, 1, 1, 1, 1)

        field = pan_coefficient(
            pcr.scalar(fetch_distance),
            pcr.scalar(wind_speed),
            pcr.scalar(relative_humidity),
            log=pcr.ln,
        )

        assert generalfunctions.getCellValue(field, 0, 0) == pytest.approx(
            expected_kp(fetch_distance, wind_speed, relative_humidity), rel=1e-6
        )


class TestModelDelegation:
    @pytest.mark.unit
    @pytest.mark.parametrize(("fetch_distance", "wind_speed", "relative_humidity"), CASES)
    def test_the_model_method_gives_the_same_numbers(
        self, fetch_distance, wind_speed, relative_humidity
    ):
        import pcraster as pcr
        from pcraster.framework import generalfunctions

        from rubem.hydrological_processes import Evapotranspiration

        pcr.setclone(1, 1, 1, 1, 1)

        method = Evapotranspiration.get_pan_coef_et_open_water_area(
            fetch_distance, wind_speed, relative_humidity
        )
        pure = pan_coefficient(
            pcr.scalar(fetch_distance),
            pcr.scalar(wind_speed),
            pcr.scalar(relative_humidity),
            log=pcr.ln,
        )

        assert generalfunctions.getCellValue(method, 0, 0) == pytest.approx(
            generalfunctions.getCellValue(pure, 0, 0)
        )
        assert generalfunctions.getCellValue(method, 0, 0) == pytest.approx(
            expected_kp(fetch_distance, wind_speed, relative_humidity), rel=1e-6
        )

    @pytest.mark.unit
    def test_the_model_method_matches_the_hand_computed_coefficient(self):
        """S29 with B = 25 m, U2 = 2 m/s and UR = 70 %, evaluated by hand.

        0.482 + 0.024 * ln(25) - 0.000376 * 2 + 0.0045 * 70
        = 0.482 + 0.0772530198 - 0.000752 + 0.315 = 0.8735010198.
        """
        import pcraster as pcr
        from pcraster.framework import generalfunctions

        from rubem.hydrological_processes import Evapotranspiration

        pcr.setclone(1, 1, 1, 1, 1)

        field = Evapotranspiration.get_pan_coef_et_open_water_area(25, 2.0, 70.0)

        assert generalfunctions.getCellValue(field, 0, 0) == pytest.approx(
            0.8735010197968368, rel=1e-6
        )


class TestKpSeries:
    @pytest.mark.unit
    def test_writes_one_pcraster_member_per_pair(self, tmp_path):
        wind_dir, humidity_dir = two_member_inputs(tmp_path)

        written = kp_series([wind_dir], [humidity_dir], tmp_path / "out", "kp", fetch_distance=25.0)

        assert [path.name for path in written] == ["kp000000.001", "kp000000.002"]
        first = read_raster(written[0])
        assert first.array[0].tolist() == pytest.approx(
            [expected_kp(25.0, 1.0, 70.0), expected_kp(25.0, 2.0, 60.0)], rel=1e-6
        )
        assert read_raster(written[1]).array[0].tolist() == pytest.approx(
            [expected_kp(25.0, 3.0, 50.0), expected_kp(25.0, 4.0, 40.0)], rel=1e-6
        )
        assert first.geotransform == pytest.approx(TRANSFORM)

    @pytest.mark.unit
    def test_writes_geotiff_members_with_the_projection_of_the_series(self, tmp_path):
        series(tmp_path / "wind", [[[1.0, 2.0]]], name="u2", crs=LOCAL_CRS)
        series(tmp_path / "ur", [[[70.0, 60.0]]], name="ur", crs=LOCAL_CRS)

        written = kp_series(
            [tmp_path / "wind"],
            [tmp_path / "ur"],
            tmp_path / "out",
            "kp",
            fetch_distance=25.0,
            output_format=OutputFormat.TIF,
        )

        assert [path.name for path in written] == ["kp00000001.tif"]
        data = read_raster(written[0])
        assert data.array.dtype == np.float32 and data.nodata == -9999.0
        assert "Engineering grid" in data.projection
        assert data.array[0].tolist() == pytest.approx(
            [expected_kp(25.0, 1.0, 70.0), expected_kp(25.0, 2.0, 60.0)], rel=1e-6
        )

    @pytest.mark.unit
    def test_a_cell_missing_in_any_input_is_missing_in_the_member(self, tmp_path):
        wind_dir, humidity_dir = two_member_inputs(
            tmp_path,
            wind=[[[-9999.0, 2.0, 3.0]], [[1.0, 2.0, 3.0]]],
            humidity=[[[70.0, -9999.0, 50.0]], [[70.0, 60.0, 50.0]]],
        )

        written = kp_series(
            [wind_dir],
            [humidity_dir],
            tmp_path / "out",
            "kp",
            fetch_distance=25.0,
            output_format=OutputFormat.TIF,
        )

        first = read_raster(written[0])
        assert first.mask().tolist() == [[False, False, True]]
        assert first.array[0, 2] == pytest.approx(expected_kp(25.0, 3.0, 50.0), rel=1e-6)
        assert read_raster(written[1]).mask().all()

    @pytest.mark.unit
    def test_the_fetch_raster_drives_the_formula_cell_by_cell(self, tmp_path):
        series(tmp_path / "wind", [[[1.0, 1.0]]], name="u2")
        series(tmp_path / "ur", [[[70.0, 70.0]]], name="ur")
        fetch = write_geotiff(
            tmp_path / "fetch.tif",
            np.array([[20.0, 30.0]], dtype=np.float32),
            TRANSFORM,
            nodata=-9999.0,
        )

        written = kp_series(
            [tmp_path / "wind"],
            [tmp_path / "ur"],
            tmp_path / "out",
            "kp",
            fetch_raster=fetch,
            output_format=OutputFormat.TIF,
        )

        assert read_raster(written[0]).array[0].tolist() == pytest.approx(
            [expected_kp(20.0, 1.0, 70.0), expected_kp(30.0, 1.0, 70.0)], rel=1e-6
        )

    @pytest.mark.unit
    def test_the_manifest_lists_both_sources_of_every_member(self, tmp_path):
        wind_dir, humidity_dir = two_member_inputs(tmp_path)

        written = kp_series([wind_dir], [humidity_dir], tmp_path / "out", "kp", fetch_distance=25.0)

        with (tmp_path / "out" / MANIFEST_NAME).open(encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        assert rows[0] == ["source", "target"]
        assert [row[1] for row in rows[1:]] == [str(written[0])] * 2 + [str(written[1])] * 2
        assert [Path(row[0]).name for row in rows[1:]] == [
            "u21.tif",
            "ur1.tif",
            "u22.tif",
            "ur2.tif",
        ]

    @pytest.mark.unit
    def test_the_first_step_numbers_the_members(self, tmp_path):
        wind_dir, humidity_dir = two_member_inputs(tmp_path)

        written = kp_series(
            [wind_dir], [humidity_dir], tmp_path / "out", "kp", fetch_distance=25.0, first_step=5
        )

        assert [path.name for path in written] == ["kp000000.005", "kp000000.006"]

    @pytest.mark.unit
    def test_a_coefficient_above_the_input_range_is_written_with_a_warning(self, tmp_path, caplog):
        """The model only reports a kp above the maximum of its range, so the tool warns."""
        wind_dir, humidity_dir = two_member_inputs(
            tmp_path, wind=[[[0.0, 0.0]]], humidity=[[[100.0, 100.0]]]
        )

        with caplog.at_level("WARNING"):
            written = kp_series(
                [wind_dir],
                [humidity_dir],
                tmp_path / "out",
                "kp",
                fetch_distance=25.0,
                output_format=OutputFormat.TIF,
            )

        assert "2 cell(s) of kp00000001.tif are above 1.0" in caplog.text
        assert read_raster(written[0]).array[0].tolist() == pytest.approx(
            [expected_kp(25.0, 0.0, 100.0)] * 2, rel=1e-6
        )
        assert expected_kp(25.0, 0.0, 100.0) > 1.0

    @pytest.mark.unit
    def test_a_warning_reports_a_fetch_distance_outside_the_supplement_range(
        self, tmp_path, caplog
    ):
        wind_dir, humidity_dir = two_member_inputs(tmp_path)

        with caplog.at_level("WARNING"):
            kp_series([wind_dir], [humidity_dir], tmp_path / "out", "kp", fetch_distance=100.0)

        assert "outside the 20.0 to 30.0 m" in caplog.text


class TestKpSeriesErrors:
    @pytest.mark.unit
    def test_the_series_must_have_the_same_number_of_members(self, tmp_path):
        series(tmp_path / "wind", [[[1.0]], [[2.0]]], name="u2")
        series(tmp_path / "ur", [[[70.0]]], name="ur")

        with pytest.raises(PreprocessingError, match="same number of members"):
            kp_series(
                [tmp_path / "wind"],
                [tmp_path / "ur"],
                tmp_path / "out",
                "kp",
                fetch_distance=25.0,
            )
        assert not (tmp_path / "out").exists()

    @pytest.mark.unit
    def test_the_series_must_share_one_geometry(self, tmp_path):
        series(tmp_path / "wind", [[[1.0, 2.0]]], name="u2")
        series(tmp_path / "ur", [[[70.0], [60.0]]], name="ur")

        with pytest.raises(PreprocessingError, match="does not share the geometry"):
            kp_series(
                [tmp_path / "wind"],
                [tmp_path / "ur"],
                tmp_path / "out",
                "kp",
                fetch_distance=25.0,
            )

    @pytest.mark.unit
    def test_a_fetch_raster_of_another_geometry_is_refused(self, tmp_path):
        series(tmp_path / "wind", [[[1.0, 2.0]]], name="u2")
        series(tmp_path / "ur", [[[70.0, 60.0]]], name="ur")
        fetch = write_geotiff(tmp_path / "fetch.tif", np.full((2, 2), 25.0, np.float32), TRANSFORM)

        with pytest.raises(PreprocessingError, match="does not share the geometry"):
            kp_series(
                [tmp_path / "wind"], [tmp_path / "ur"], tmp_path / "out", "kp", fetch_raster=fetch
            )

    @pytest.mark.unit
    def test_a_member_with_a_non_positive_coefficient_writes_nothing(self, tmp_path):
        """The model blocks a kp raster with a cell that is not positive."""
        wind_dir, humidity_dir = two_member_inputs(
            tmp_path,
            wind=[[[1.0, 2.0]], [[5000.0, 6000.0]]],
            humidity=[[[70.0, 60.0]], [[0.0, 0.0]]],
        )

        with pytest.raises(PreprocessingError, match="must be positive") as error:
            kp_series([wind_dir], [humidity_dir], tmp_path / "out", "kp", fetch_distance=25.0)

        assert "u22.tif: 2 cell(s)" in str(error.value)
        assert not (tmp_path / "out").exists()

    @pytest.mark.unit
    def test_a_refused_run_keeps_the_previous_members_and_manifest(self, tmp_path):
        wind_dir, humidity_dir = two_member_inputs(tmp_path)
        kp_series([wind_dir], [humidity_dir], tmp_path / "out", "kp", fetch_distance=25.0)
        assert (tmp_path / "out" / MANIFEST_NAME).is_file()

        series(tmp_path / "bad", [[[5000.0, 6000.0]], [[5000.0, 6000.0]]], name="u2")
        with pytest.raises(PreprocessingError, match="must be positive"):
            kp_series(
                [tmp_path / "bad"],
                [humidity_dir],
                tmp_path / "out",
                "kp",
                fetch_distance=25.0,
            )

        # Nothing was written, so the previous run's manifest still describes it.
        assert (tmp_path / "out" / MANIFEST_NAME).is_file()

    @pytest.mark.unit
    def test_a_valid_cell_equal_to_the_no_data_value_is_refused(self, tmp_path):
        """A kp of exactly the sentinel would be read back as missing."""
        wind_dir, humidity_dir = two_member_inputs(tmp_path)
        kp_of_first_cell = expected_kp(25.0, 1.0, 70.0)

        with pytest.raises(PreprocessingError, match="already equal the no-data value"):
            kp_series(
                [wind_dir],
                [humidity_dir],
                tmp_path / "out",
                "kp",
                fetch_distance=25.0,
                output_format=OutputFormat.TIF,
                nodata=float(np.float32(kp_of_first_cell)),
            )
        assert not (tmp_path / "out").exists()

    @pytest.mark.unit
    @pytest.mark.parametrize("distance", [0.0, -5.0, float("nan")])
    def test_the_fetch_distance_must_be_positive(self, tmp_path, distance):
        wind_dir, humidity_dir = two_member_inputs(tmp_path)

        with pytest.raises(PreprocessingError, match="positive number of meters"):
            kp_series([wind_dir], [humidity_dir], tmp_path / "out", "kp", fetch_distance=distance)

    @pytest.mark.unit
    def test_a_fetch_raster_cell_that_is_not_positive_is_refused(self, tmp_path):
        wind_dir, humidity_dir = two_member_inputs(tmp_path)
        fetch = write_geotiff(
            tmp_path / "fetch.tif", np.array([[25.0, 0.0]], np.float32), TRANSFORM
        )

        with pytest.raises(PreprocessingError, match="positive fetch distance"):
            kp_series([wind_dir], [humidity_dir], tmp_path / "out", "kp", fetch_raster=fetch)

    @pytest.mark.unit
    def test_exactly_one_fetch_input_is_needed(self, tmp_path):
        wind_dir, humidity_dir = two_member_inputs(tmp_path)
        fetch = write_geotiff(tmp_path / "fetch.tif", np.full((1, 2), 25.0, np.float32), TRANSFORM)

        with pytest.raises(PreprocessingError, match="not as neither or both"):
            kp_series([wind_dir], [humidity_dir], tmp_path / "out", "kp")
        with pytest.raises(PreprocessingError, match="not as neither or both"):
            kp_series(
                [wind_dir],
                [humidity_dir],
                tmp_path / "out",
                "kp",
                fetch_distance=25.0,
                fetch_raster=fetch,
            )

    @pytest.mark.unit
    def test_a_member_that_would_overwrite_an_input_is_refused(self, tmp_path):
        """The series is read twice, so a member written over an input would change it."""
        series(tmp_path / "wind", [[[1.0]], [[2.0]]], name="kp0000000")
        series(tmp_path / "ur", [[[70.0]], [[60.0]]], name="ur")

        with pytest.raises(PreprocessingError, match="both an input of the series"):
            kp_series(
                [tmp_path / "wind"],
                [tmp_path / "ur"],
                tmp_path / "wind",
                "kp",
                fetch_distance=25.0,
                output_format=OutputFormat.TIF,
            )
        assert read_raster(tmp_path / "wind" / "kp00000001.tif").array[0, 0] == pytest.approx(1.0)

    @pytest.mark.unit
    def test_an_empty_series_is_reported_with_its_name(self, tmp_path):
        series(tmp_path / "wind", [[[1.0]]], name="u2")
        (tmp_path / "ur").mkdir()

        with pytest.raises(PreprocessingError, match="relative humidity series"):
            kp_series(
                [tmp_path / "wind"],
                [tmp_path / "ur"],
                tmp_path / "out",
                "kp",
                fetch_distance=25.0,
            )


class TestCommand:
    @pytest.mark.unit
    def test_kp_command_prints_the_members(self, tmp_path, capsys, restore_logging):
        wind_dir, humidity_dir = two_member_inputs(tmp_path)

        main(
            [
                "preprocess",
                "kp",
                "--wind",
                str(wind_dir),
                "--humidity",
                str(humidity_dir),
                "-o",
                str(tmp_path / "out"),
                "--prefix",
                "kp",
                "--fetch",
                "25",
                "--format",
                "tif",
            ]
        )

        printed = capsys.readouterr().out.splitlines()
        assert [Path(line).name for line in printed] == ["kp00000001.tif", "kp00000002.tif"]
        assert read_raster(printed[0]).array[0].tolist() == pytest.approx(
            [expected_kp(25.0, 1.0, 70.0), expected_kp(25.0, 2.0, 60.0)], rel=1e-6
        )

    @pytest.mark.unit
    def test_errors_exit_with_one(self, tmp_path, capsys, restore_logging):
        wind_dir, humidity_dir = two_member_inputs(tmp_path)

        with pytest.raises(SystemExit) as error:
            main(
                [
                    "preprocess",
                    "kp",
                    "--wind",
                    str(wind_dir),
                    "--humidity",
                    str(humidity_dir),
                    "-o",
                    str(tmp_path / "out"),
                    "--prefix",
                    "kp",
                    "--fetch",
                    "-1",
                ]
            )

        assert error.value.code == 1
        assert "positive number of meters" in capsys.readouterr().err
