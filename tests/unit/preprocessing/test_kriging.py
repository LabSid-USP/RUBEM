import importlib
import sys

import numpy as np
import pytest

from rubem.cli import main
from rubem.preprocessing._io import PreprocessingError, read_raster, write_geotiff
from rubem.preprocessing.kriging_series import (
    CoordinatesType,
    NegativePolicy,
    Stations,
    StationsFormat,
    VariogramModel,
    _great_circle_dist_func,
    apply_negative_policy,
    coordinates_type_for,
    krige_file,
    krige_series,
    krige_step,
    read_stations,
    read_stations_long,
    read_stations_matrix,
)
from tests.helpers.compare import ensure_gdal_drivers
from tests.helpers.synthetic import series_name, write_synthetic_dataset

LOCAL_CRS = 'LOCAL_CS["Engineering grid",UNIT["metre",1]]'
TRANSFORM = (0.0, 500.0, 0.0, 1500.0, 0.0, -500.0)


def matrix_file(path, rows):
    path.write_text(
        "\n".join(";".join(str(v) for v in row) for row in rows) + "\n", encoding="utf8"
    )
    return path


class TestReaders:
    @pytest.mark.unit
    def test_matrix_layout(self, tmp_path):
        file = matrix_file(
            tmp_path / "s.csv", [[100, 200, 1.0, 2.0], [300, 400, 3.0, 4.0], [500, 600, 5.0, 6.0]]
        )

        stations = read_stations_matrix(file)

        assert stations.x.tolist() == [100, 300, 500] and stations.y.tolist() == [200, 400, 600]
        assert stations.values.tolist() == [[1.0, 3.0, 5.0], [2.0, 4.0, 6.0]]
        assert stations.ids == ("1", "2", "3") and stations.steps == 2

    @pytest.mark.unit
    def test_matrix_errors(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_stations_matrix(tmp_path / "absent.csv")
        with pytest.raises(PreprocessingError, match="at least one value"):
            read_stations_matrix(matrix_file(tmp_path / "a.csv", [[1, 2]]))
        with pytest.raises(PreprocessingError, match="non-numeric"):
            read_stations_matrix(matrix_file(tmp_path / "b.csv", [[1, 2, "x"]]))
        with pytest.raises(PreprocessingError, match="different numbers of columns"):
            read_stations_matrix(matrix_file(tmp_path / "c.csv", [[1, 2, 3], [1, 2, 3, 4]]))

    @pytest.mark.unit
    @pytest.mark.parametrize("cell", ["nan", "inf", "-inf"])
    def test_matrix_non_finite_cells_are_refused(self, tmp_path, cell):
        file = matrix_file(tmp_path / "d.csv", [[1, 2, cell]])

        with pytest.raises(PreprocessingError, match="non-finite"):
            read_stations_matrix(file)

    @pytest.mark.unit
    def test_long_layout(self, tmp_path):
        file = tmp_path / "long.csv"
        file.write_text(
            "step;id;x;y;value\n1;b;300;400;3\n1;a;100;200;1\n2;a;100;200;2\n2;b;300;400;4\n",
            encoding="utf8",
        )

        stations = read_stations_long(file)

        assert stations.ids == ("a", "b")
        assert stations.values.tolist() == [[1.0, 3.0], [2.0, 4.0]]
        assert read_stations(file, StationsFormat.LONG).ids == ("a", "b")

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "text, message",
        [
            ("", "empty"),
            ("time;id;x;y;value\n", "expected the header"),
            ("step;id;x;y;value\n1;a;1;2\n", "needs 5 columns"),
            ("step;id;x;y;value\n1;a;1;2;x\n", "non-numeric"),
            ("step;id;x;y;value\n1;a;nan;2;3\n", "non-finite"),
            ("step;id;x;y;value\n1;a;1;2;inf\n", "non-finite"),
            ("step;id;x;y;value\n0;a;1;2;3\n", "steps start at 1"),
            ("step;id;x;y;value\n1;a;1;2;3\n1;a;9;9;3\n", "different coordinates"),
            ("step;id;x;y;value\n1;a;1;2;3\n1;a;1;2;4\n", "appears twice"),
            ("step;id;x;y;value\n1;a;1;2;3\n3;a;1;2;3\n", "without gaps"),
            ("step;id;x;y;value\n1;a;1;2;3\n1;b;2;2;3\n2;a;1;2;3\n", "lacks the station"),
        ],
    )
    def test_long_errors(self, tmp_path, text, message):
        file = tmp_path / "long.csv"
        file.write_text(text, encoding="utf8")

        with pytest.raises(PreprocessingError, match=message):
            read_stations_long(file)


class TestPolicies:
    @pytest.mark.unit
    def test_coordinates_type_follows_the_crs(self):
        assert coordinates_type_for("") is CoordinatesType.GEOGRAPHIC
        assert coordinates_type_for(LOCAL_CRS) is CoordinatesType.EUCLIDEAN

    @pytest.mark.unit
    def test_negative_policy(self, caplog):
        grid = np.array([[-1.0, 2.0]])

        assert apply_negative_policy(grid, NegativePolicy.KEEP, "s").tolist() == [[-1.0, 2.0]]
        with caplog.at_level("WARNING"):
            assert apply_negative_policy(grid, NegativePolicy.CLAMP, "s").tolist() == [[0.0, 2.0]]
        assert "clamped" in caplog.text
        with pytest.raises(PreprocessingError, match="negative"):
            apply_negative_policy(grid, NegativePolicy.ERROR, "s")
        assert apply_negative_policy(np.array([[1.0]]), NegativePolicy.ERROR, "s").tolist() == [
            [1.0]
        ]

    @pytest.mark.unit
    def test_a_constant_step_needs_no_variogram(self):
        stations = Stations(
            np.array([0.0, 1.0, 2.0]),
            np.array([0.0, 1.0, 0.0]),
            np.array([[5.0, 5.0, 5.0]]),
            ("a", "b", "c"),
        )

        grid = krige_step(
            stations, 0, np.array([0.5, 1.5]), np.array([0.5]), CoordinatesType.EUCLIDEAN
        )

        assert grid.tolist() == [[5.0, 5.0]]


@pytest.fixture(name="kriging_deps")
def kriging_deps_fixture():
    pytest.importorskip("pykrige")
    pytest.importorskip("skgstat")


class TestKrigeSeries:
    @pytest.mark.unit
    def test_interpolates_each_step_onto_the_clone_grid(self, tmp_path, kriging_deps, caplog):
        ensure_gdal_drivers()
        clone = write_geotiff(
            tmp_path / "clone.tif", np.ones((3, 3), np.float32), TRANSFORM, LOCAL_CRS
        )
        stations = Stations(
            x=np.array([250.0, 1250.0, 250.0, 1250.0, 2500.0]),
            y=np.array([1250.0, 1250.0, 250.0, 250.0, 250.0]),
            values=np.array([[10.0, 20.0, 30.0, 40.0, 50.0], [1.0, 1.0, 1.0, 1.0, 1.0]]),
            ids=("a", "b", "c", "d", "e"),
        )

        with caplog.at_level("WARNING"):
            written = krige_series(stations, clone, tmp_path / "out", "prec", seed=1)

        assert [p.name for p in written] == [series_name("prec", 1), series_name("prec", 2)]
        assert "outside the clone extent: ['e']" in caplog.text
        first = read_raster(written[0])
        assert first.array.shape == (3, 3) and first.geotransform == pytest.approx(TRANSFORM)
        assert 0.0 <= first.array.min() and first.array.max() <= 60.0
        second = read_raster(written[1])
        assert np.allclose(second.array, 1.0)
        assert (tmp_path / "out" / "manifest.csv").is_file()

    @pytest.mark.unit
    def test_an_interpolated_value_equal_to_no_data_is_refused(self, tmp_path, kriging_deps):
        ensure_gdal_drivers()
        clone = write_geotiff(tmp_path / "clone.tif", np.ones((3, 3), np.float32), TRANSFORM)
        # Station "a" sits exactly on a grid cell center with a negative
        # value; ordinary kriging is an exact interpolator, so that cell
        # comes back as -50.0 and the clamp policy turns it into exactly
        # 0.0, a genuine (if clamped) interpolated value.
        stations = Stations(
            x=np.array([250.0, 1250.0, 250.0]),
            y=np.array([1250.0, 1250.0, 250.0]),
            values=np.array([[-50.0, 100.0, 80.0]]),
            ids=("a", "b", "c"),
        )

        with pytest.raises(PreprocessingError, match="valid cell"):
            krige_series(stations, clone, tmp_path / "out", "prec", nodata=0.0)

        # The default sentinel does not collide with any interpolated cell.
        written = krige_series(stations, clone, tmp_path / "out", "prec")
        assert read_raster(written[0]).array[0, 0] == pytest.approx(0.0)

    @pytest.mark.unit
    def test_station_and_step_limits(self, tmp_path, kriging_deps):
        ensure_gdal_drivers()
        clone = write_geotiff(tmp_path / "clone.tif", np.ones((2, 2), np.float32), TRANSFORM)
        few = Stations(
            np.array([0.0, 1.0]), np.array([0.0, 1.0]), np.array([[1.0, 2.0]]), ("a", "b")
        )
        with pytest.raises(PreprocessingError, match="at least 3 stations"):
            krige_series(few, clone, tmp_path / "out", "prec")
        three = Stations(
            np.array([0.0, 1.0, 2.0]),
            np.array([0.0, 1.0, 0.0]),
            np.array([[1.0, 1.0, 1.0]]),
            ("a", "b", "c"),
        )
        with pytest.raises(PreprocessingError, match="carries 1 step"):
            krige_series(three, clone, tmp_path / "out", "prec", steps=2)
        rotated = write_geotiff(
            tmp_path / "rot.tif", np.ones((2, 2), np.float32), (0, 1, 0.1, 2, 0.1, -1)
        )
        with pytest.raises(PreprocessingError, match="rotated"):
            krige_series(three, rotated, tmp_path / "out", "prec")

    @pytest.mark.unit
    def test_south_up_clones_are_refused(self, tmp_path, kriging_deps):
        ensure_gdal_drivers()
        three = Stations(
            np.array([0.0, 1.0, 2.0]),
            np.array([0.0, 1.0, 0.0]),
            np.array([[1.0, 1.0, 1.0]]),
            ("a", "b", "c"),
        )
        south_up = write_geotiff(
            tmp_path / "south.tif", np.ones((2, 2), np.float32), (0, 1, 0, 0, 0, 1)
        )

        with pytest.raises(PreprocessingError, match="south-up"):
            krige_series(three, south_up, tmp_path / "out", "prec")

    @pytest.mark.unit
    def test_duplicate_station_coordinates_are_refused(self, tmp_path, kriging_deps):
        ensure_gdal_drivers()
        clone = write_geotiff(tmp_path / "clone.tif", np.ones((2, 2), np.float32), TRANSFORM)
        duplicated = Stations(
            np.array([250.0, 250.0, 1250.0]),
            np.array([1250.0, 1250.0, 250.0]),
            np.array([[1.0, 2.0, 3.0]]),
            ("a", "b", "c"),
        )

        with pytest.raises(PreprocessingError, match="distinct station coordinates"):
            krige_series(duplicated, clone, tmp_path / "out", "prec")

    @pytest.mark.unit
    def test_the_duplicate_coordinate_error_names_the_stations_and_coordinate(
        self, tmp_path, kriging_deps
    ):
        ensure_gdal_drivers()
        clone = write_geotiff(tmp_path / "clone.tif", np.ones((2, 2), np.float32), TRANSFORM)
        duplicated = Stations(
            np.array([250.0, 250.0, 1250.0]),
            np.array([1250.0, 1250.0, 250.0]),
            np.array([[1.0, 2.0, 3.0]]),
            ("a", "b", "c"),
        )

        with pytest.raises(PreprocessingError, match=r"a, b share coordinate \(250.0, 1250.0\)"):
            krige_series(duplicated, clone, tmp_path / "out", "prec")

    @pytest.mark.unit
    def test_four_stations_with_three_unique_coordinates_are_refused_up_front(
        self, tmp_path, kriging_deps
    ):
        # Exactly three unique coordinates satisfies the minimum-station
        # count but still leaves two stations ("a" and its duplicate "d") at
        # the same point, which makes OrdinaryKriging's matrix singular on a
        # non-constant step; this must be caught before any map is written,
        # not partway through the series.
        ensure_gdal_drivers()
        clone = write_geotiff(tmp_path / "clone.tif", np.ones((2, 2), np.float32), TRANSFORM)
        stations = Stations(
            np.array([250.0, 1250.0, 750.0, 250.0]),
            np.array([1250.0, 1250.0, 250.0, 1250.0]),
            np.array([[1.0, 2.0, 3.0, 1.0], [4.0, 3.0, 2.0, 4.0]]),
            ("a", "b", "c", "d"),
        )

        with pytest.raises(PreprocessingError, match="distinct station coordinates"):
            krige_series(stations, clone, tmp_path / "out", "prec")

        assert not (tmp_path / "out").exists()

    @pytest.mark.unit
    def test_a_matrix_file_with_three_unique_coordinates_is_refused_up_front(
        self, tmp_path, kriging_deps
    ):
        ensure_gdal_drivers()
        clone = write_geotiff(tmp_path / "clone.tif", np.ones((2, 2), np.float32), TRANSFORM)
        stations = matrix_file(
            tmp_path / "stations.csv",
            [
                [250, 1250, 1.0, 4.0],
                [1250, 1250, 2.0, 3.0],
                [750, 250, 3.0, 2.0],
                [250, 1250, 1.0, 4.0],
            ],
        )

        with pytest.raises(PreprocessingError, match="distinct station coordinates"):
            krige_file(stations, clone, tmp_path / "out", "prec")

        assert not (tmp_path / "out").exists()

    @pytest.mark.unit
    def test_a_long_format_file_with_three_unique_coordinates_is_refused_up_front(
        self, tmp_path, kriging_deps
    ):
        ensure_gdal_drivers()
        clone = write_geotiff(tmp_path / "clone.tif", np.ones((2, 2), np.float32), TRANSFORM)
        file = tmp_path / "long.csv"
        file.write_text(
            "step;id;x;y;value\n"
            "1;a;250;1250;1.0\n"
            "1;b;1250;1250;2.0\n"
            "1;c;750;250;3.0\n"
            "1;d;250;1250;4.0\n"
            "2;a;250;1250;5.0\n"
            "2;b;1250;1250;6.0\n"
            "2;c;750;250;7.0\n"
            "2;d;250;1250;8.0\n",
            encoding="utf8",
        )

        with pytest.raises(PreprocessingError, match="distinct station coordinates"):
            krige_file(file, clone, tmp_path / "out", "prec", layout=StationsFormat.LONG)

        assert not (tmp_path / "out").exists()

    @pytest.mark.unit
    def test_unsupported_variogram_models_are_refused(self, tmp_path, kriging_deps):
        ensure_gdal_drivers()
        clone = write_geotiff(tmp_path / "clone.tif", np.ones((2, 2), np.float32), TRANSFORM)
        three = Stations(
            np.array([0.0, 1.0, 2.0]),
            np.array([0.0, 1.0, 0.0]),
            np.array([[1.0, 2.0, 3.0]]),
            ("a", "b", "c"),
        )

        with pytest.raises(PreprocessingError, match="Unsupported variogram model 'linear'"):
            krige_series(three, clone, tmp_path / "out", "prec", variogram_model="linear")


class TestGeographicDistance:
    @pytest.mark.unit
    def test_matches_pykrige_great_circle_distance(self, kriging_deps):
        from pykrige.core import great_circle_distance

        u, v = np.array([10.0, 80.0]), np.array([-30.0, -5.0])

        assert _great_circle_dist_func(u, v) == pytest.approx(
            great_circle_distance(u[0], u[1], v[0], v[1])
        )

    @pytest.mark.unit
    def test_geographic_fit_disagrees_with_a_naive_euclidean_fit_at_high_latitude(
        self, kriging_deps
    ):
        import skgstat as skg

        # A degree of longitude covers far less ground than a degree of
        # latitude this close to the pole, so a variogram fitted on raw
        # longitude/latitude numbers ("euclidean") disagrees strongly with
        # one fitted on the true angular (great-circle) distance.
        x = np.array([0.0, 20.0, 40.0, 60.0, 80.0, 10.0])
        y = np.array([80.0, 80.0, 80.0, 80.0, 80.0, 79.0])
        values = np.array([1.0, 3.0, 2.0, 5.0, 4.0, 2.5])
        coordinates = np.column_stack([x, y])

        euclidean = skg.Variogram(
            coordinates=coordinates,
            values=values,
            model="spherical",
            bin_func="uniform",
            n_lags=4,
            dist_func="euclidean",
        )
        geographic = skg.Variogram(
            coordinates=coordinates,
            values=values,
            model="spherical",
            bin_func="uniform",
            n_lags=4,
            dist_func=_great_circle_dist_func,
        )

        # The great-circle distances are the true ones for these stations;
        # the Euclidean-on-degrees distances overstate them at this latitude.
        assert geographic.distance.max() < euclidean.distance.max()
        euclidean_range, geographic_range = euclidean.parameters[0], geographic.parameters[0]
        assert geographic_range < euclidean_range

    @pytest.mark.unit
    def test_krige_step_runs_with_the_geographic_metric(self, kriging_deps):
        stations = Stations(
            x=np.array([0.0, 20.0, 40.0, 60.0, 80.0, 10.0]),
            y=np.array([80.0, 80.0, 80.0, 80.0, 80.0, 79.0]),
            values=np.array([[1.0, 3.0, 2.0, 5.0, 4.0, 2.5]]),
            ids=("a", "b", "c", "d", "e", "f"),
        )

        grid = krige_step(
            stations,
            0,
            np.array([10.0, 30.0]),
            np.array([79.5]),
            CoordinatesType.GEOGRAPHIC,
            VariogramModel.SPHERICAL,
            n_lags=4,
        )

        assert grid.shape == (1, 2) and np.all(np.isfinite(grid))


class TestCommand:
    @pytest.mark.unit
    def test_krige_command_writes_the_series(self, tmp_path, kriging_deps, capsys, restore_logging):
        config = write_synthetic_dataset(str(tmp_path))
        stations = matrix_file(
            tmp_path / "stations.csv",
            [[250, 1250, 1.0, 2.0], [1250, 1250, 1.0, 2.0], [750, 250, 1.0, 2.0]],
        )

        main(
            [
                "preprocess",
                "krige",
                str(stations),
                "--clone",
                config["RASTERS"]["clone"],
                "-o",
                str(tmp_path / "krig"),
                "--prefix",
                "prec",
                "--steps",
                "1",
            ]
        )

        assert capsys.readouterr().out.splitlines() == [
            str(tmp_path / "krig" / series_name("prec", 1))
        ]

    @pytest.mark.unit
    def test_missing_extra_is_explained(self, tmp_path, monkeypatch, capsys, restore_logging):
        import importlib.util

        real = importlib.util.find_spec
        monkeypatch.setattr(
            importlib.util,
            "find_spec",
            lambda name: None if name in ("pykrige", "skgstat") else real(name),
        )
        config = write_synthetic_dataset(str(tmp_path))
        stations = matrix_file(tmp_path / "s.csv", [[0, 0, 1], [1, 1, 1], [2, 0, 1]])

        with pytest.raises(SystemExit) as error:
            main(
                [
                    "preprocess",
                    "krige",
                    str(stations),
                    "--clone",
                    config["RASTERS"]["clone"],
                    "-o",
                    str(tmp_path / "k"),
                    "--prefix",
                    "prec",
                ]
            )

        assert "rubem[preprocessing]" in str(error.value)


class TestDeprecatedModule:
    @pytest.mark.unit
    def test_importing_the_legacy_module_warns(self, kriging_deps):
        sys.modules.pop("rubem.preprocessing.kriging", None)

        with pytest.warns(DeprecationWarning, match="kriging_series"):
            importlib.import_module("rubem.preprocessing.kriging")
