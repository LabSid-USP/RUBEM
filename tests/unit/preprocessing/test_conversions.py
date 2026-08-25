import importlib
import os
import sys

import numpy as np
import pytest

from rubem.cli import main
from rubem.preprocessing._io import (
    AllNoDataPolicy,
    PreprocessingError,
    ValueScale,
    read_raster,
    write_geotiff,
    write_pcraster_map,
)
from rubem.preprocessing.conversions import mapseries2tif, tif2map, tif2mapseries
from tests.helpers.compare import ensure_gdal_drivers
from tests.helpers.synthetic import series_name, write_synthetic_dataset

TRANSFORM = (0.0, 500.0, 0.0, 1500.0, 0.0, -500.0)
LOCAL_CRS = 'LOCAL_CS["Engineering grid",UNIT["metre",1]]'


def geotiffs(directory, count=3, nodata=-9999.0, transform=TRANSFORM, names=None):
    """Write ``count`` 3x3 GeoTIFFs whose values equal their index, one missing cell each."""
    ensure_gdal_drivers()
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for index in range(1, count + 1):
        array = np.full((3, 3), float(index), dtype=np.float32)
        array[0, 0] = nodata
        name = names[index - 1] if names else f"etp{index}.tif"
        written.append(write_geotiff(directory / name, array, transform, nodata=nodata))
    return written


class TestTif2Map:
    @pytest.mark.unit
    def test_converts_files_and_directories_next_to_the_inputs(self, tmp_path):
        files = geotiffs(tmp_path / "in")
        single = geotiffs(tmp_path / "single", count=1)

        written = tif2map([single[0], tmp_path / "in"])

        assert [p.name for p in written] == ["etp1.map", "etp1.map", "etp2.map", "etp3.map"]
        assert written[0].parent == tmp_path / "single" and files[0].exists()
        data = read_raster(tmp_path / "in" / "etp2.map")
        assert data.geotransform == pytest.approx(TRANSFORM)
        assert data.mask().sum() == 8 and data.array[data.mask()].tolist() == [2.0] * 8

    @pytest.mark.unit
    def test_value_scales_and_output_directory(self, tmp_path):
        ensure_gdal_drivers()
        ids = write_geotiff(
            tmp_path / "ids.tif", np.array([[1, 2], [3, 4]], dtype=np.int32), TRANSFORM
        )

        written = tif2map([ids], tmp_path / "out", value_scale=ValueScale.NOMINAL)

        assert written == [tmp_path / "out" / "ids.map"]
        assert read_raster(written[0]).array.tolist() == [[1, 2], [3, 4]]

    @pytest.mark.unit
    def test_collisions_and_missing_inputs_are_refused(self, tmp_path):
        geotiffs(tmp_path / "a", count=1)
        geotiffs(tmp_path / "b", count=1)

        with pytest.raises(PreprocessingError, match="would both be written"):
            tif2map([tmp_path / "a", tmp_path / "b"], tmp_path / "out")
        with pytest.raises(FileNotFoundError):
            tif2map([tmp_path / "absent.tif"])
        (tmp_path / "empty").mkdir()
        with pytest.raises(PreprocessingError, match="No GeoTIFF file"):
            tif2map([tmp_path / "empty"])

    @pytest.mark.unit
    def test_all_nodata_policy(self, tmp_path, caplog):
        ensure_gdal_drivers()
        empty = write_geotiff(
            tmp_path / "empty.tif", np.full((2, 2), -9999.0, np.float32), TRANSFORM, nodata=-9999.0
        )

        with pytest.raises(PreprocessingError, match="every cell"):
            tif2map([empty])
        assert tif2map([empty], all_nodata=AllNoDataPolicy.SKIP) == []
        with caplog.at_level("WARNING"):
            assert tif2map([empty], all_nodata=AllNoDataPolicy.WARN) == [tmp_path / "empty.map"]
        assert "every cell" in caplog.text


class TestTif2MapSeries:
    @pytest.mark.unit
    def test_natural_order_and_pcraster_names(self, tmp_path):
        names = ["etp10.tif", "etp2.tif", "etp1.tif"]
        geotiffs(tmp_path / "in", count=3, names=names)

        written = tif2mapseries(tmp_path / "in", "etp", tmp_path / "out")

        assert [p.name for p in written] == [
            series_name("etp", 1),
            series_name("etp", 2),
            series_name("etp", 3),
        ]
        # etp1.tif carries value 3 (third written), so step 1 reads it
        assert read_raster(written[0]).array[1, 1] == 3.0
        manifest = (tmp_path / "out" / "manifest.csv").read_text(encoding="utf8").splitlines()
        assert manifest[0] == "source,target" and len(manifest) == 4
        assert manifest[1].endswith(series_name("etp", 1))

    @pytest.mark.unit
    def test_first_step_and_skipped_rasters_keep_the_numbering(self, tmp_path):
        ensure_gdal_drivers()
        files = geotiffs(tmp_path / "in", count=2)
        write_geotiff(
            tmp_path / "in" / "etp3.tif",
            np.full((3, 3), -9999.0, np.float32),
            TRANSFORM,
            nodata=-9999.0,
        )
        (tmp_path / "in" / "notes.txt").write_text("ignored", encoding="utf8")

        written = tif2mapseries(
            tmp_path / "in", "etp", first_step=5, all_nodata=AllNoDataPolicy.SKIP
        )

        assert [p.name for p in written] == [series_name("etp", 5), series_name("etp", 6)]
        assert not (tmp_path / "in" / series_name("etp", 7)).exists()
        assert files[0].exists()

    @pytest.mark.unit
    def test_geometry_must_match_the_clone_or_the_first_file(self, tmp_path):
        geotiffs(tmp_path / "in", count=2)
        ensure_gdal_drivers()
        shifted = (1.0,) + TRANSFORM[1:]
        write_geotiff(tmp_path / "in" / "etp3.tif", np.ones((3, 3), np.float32), shifted)

        with pytest.raises(PreprocessingError, match="does not share the geometry"):
            tif2mapseries(tmp_path / "in", "etp", tmp_path / "out")
        assert not (tmp_path / "out" / "manifest.csv").exists()

        clone = write_geotiff(tmp_path / "clone.tif", np.ones((4, 4), np.float32), TRANSFORM)
        with pytest.raises(PreprocessingError, match="does not share the geometry"):
            tif2mapseries(tmp_path / "in", "etp", tmp_path / "out2", clone=clone)

    @pytest.mark.unit
    def test_long_prefixes_are_refused_before_writing(self, tmp_path):
        geotiffs(tmp_path / "in", count=1)

        with pytest.raises(ValueError, match="shorter than 8"):
            tif2mapseries(tmp_path / "in", "prefix08", tmp_path / "out")

    @pytest.mark.unit
    def test_a_stale_manifest_does_not_survive_a_failing_run(self, tmp_path):
        geotiffs(tmp_path / "in", count=2)
        ensure_gdal_drivers()
        shifted = (1.0,) + TRANSFORM[1:]
        write_geotiff(tmp_path / "in" / "etp3.tif", np.ones((3, 3), np.float32), shifted)
        (tmp_path / "out").mkdir()
        (tmp_path / "out" / "manifest.csv").write_text("source,target\nstale,stale\n", "utf8")

        with pytest.raises(PreprocessingError, match="does not share the geometry"):
            tif2mapseries(tmp_path / "in", "etp", tmp_path / "out")

        assert not (tmp_path / "out" / "manifest.csv").exists()

    @pytest.mark.unit
    def test_skipping_a_raster_removes_a_stale_target(self, tmp_path):
        geotiffs(tmp_path / "in", count=1)
        write_geotiff(
            tmp_path / "in" / "etp2.tif",
            np.full((3, 3), -9999.0, np.float32),
            TRANSFORM,
            nodata=-9999.0,
        )
        stale_target = tmp_path / "out" / series_name("etp", 2)
        stale_target.parent.mkdir(parents=True)
        stale_target.write_bytes(b"leftover from an earlier run")

        written = tif2mapseries(
            tmp_path / "in", "etp", tmp_path / "out", all_nodata=AllNoDataPolicy.SKIP
        )

        assert [p.name for p in written] == [series_name("etp", 1)]
        assert not stale_target.exists()


class TestMapSeries2Tif:
    @pytest.mark.unit
    def test_the_synthetic_precipitation_series_becomes_geotiffs(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        ensure_gdal_drivers()
        georeference = write_geotiff(
            tmp_path / "georef.tif", np.ones((3, 3), np.float32), TRANSFORM, LOCAL_CRS
        )

        written = mapseries2tif(
            config["DIRECTORIES"]["prec"], "prec", tmp_path / "tif", georeference
        )

        assert [p.name for p in written] == ["prec000001.tif", "prec000002.tif"]
        data = read_raster(written[0])
        assert "Engineering grid" in data.projection
        assert data.nodata == -9999.0
        assert data.geotransform == pytest.approx(TRANSFORM)
        assert (tmp_path / "tif" / "manifest.csv").is_file()

    @pytest.mark.unit
    def test_missing_series_and_geometry_mismatch(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        with pytest.raises(PreprocessingError, match="No member of the series"):
            mapseries2tif(config["DIRECTORIES"]["prec"], "xyz")
        with pytest.raises(NotADirectoryError):
            mapseries2tif(tmp_path / "absent", "prec")
        ensure_gdal_drivers()
        other = write_geotiff(tmp_path / "other.tif", np.ones((4, 4), np.float32), TRANSFORM)
        with pytest.raises(PreprocessingError, match="does not share the geometry"):
            mapseries2tif(config["DIRECTORIES"]["prec"], "prec", tmp_path / "tif", other)

    @pytest.mark.unit
    def test_the_no_data_value_is_remapped(self, tmp_path):
        ensure_gdal_drivers()
        (tmp_path / "series").mkdir()

        array = np.array([[1.0, -9999.0], [2.0, 3.0]])
        write_pcraster_map(
            tmp_path / "series" / series_name("v", 1),
            array,
            ValueScale.SCALAR,
            (0, 1, 0, 2, 0, -1),
            -9999.0,
        )

        written = mapseries2tif(tmp_path / "series", "v", nodata=-1.0)

        data = read_raster(written[0])
        assert data.nodata == -1.0 and data.array[0, 1] == -1.0 and data.mask().sum() == 3

    @pytest.mark.unit
    def test_the_first_member_is_the_geometry_reference_without_a_georeference(self, tmp_path):
        ensure_gdal_drivers()
        (tmp_path / "series").mkdir()
        write_pcraster_map(
            tmp_path / "series" / series_name("v", 1),
            np.array([[1.0, 2.0], [3.0, 4.0]]),
            ValueScale.SCALAR,
            TRANSFORM,
        )
        write_pcraster_map(
            tmp_path / "series" / series_name("v", 2),
            np.array([[1.0, 2.0], [3.0, 4.0]]),
            ValueScale.SCALAR,
            (1.0,) + TRANSFORM[1:],
        )

        with pytest.raises(PreprocessingError, match="does not share the geometry"):
            mapseries2tif(tmp_path / "series", "v")

    @pytest.mark.unit
    def test_no_georeference_leaves_the_projection_empty(self, tmp_path):
        ensure_gdal_drivers()
        (tmp_path / "series").mkdir()
        write_pcraster_map(
            tmp_path / "series" / series_name("v", 1),
            np.array([[1.0, 2.0], [3.0, 4.0]]),
            ValueScale.SCALAR,
            TRANSFORM,
        )

        written = mapseries2tif(tmp_path / "series", "v")

        assert read_raster(written[0]).projection == ""

    @pytest.mark.unit
    def test_a_no_data_value_the_source_type_cannot_hold_promotes_the_band(self, tmp_path):
        ensure_gdal_drivers()
        (tmp_path / "series").mkdir()
        write_pcraster_map(
            tmp_path / "series" / series_name("b", 1),
            np.array([[1.0, 0.0], [1.0, np.nan]]),
            ValueScale.BOOLEAN,
            TRANSFORM,
        )

        written = mapseries2tif(tmp_path / "series", "b")

        data = read_raster(written[0])
        assert data.array.dtype == np.int16
        assert data.nodata == -9999.0
        assert data.array[data.mask()].tolist() == [1, 0, 1]
        assert data.array[~data.mask()].tolist() == [-9999]

    @pytest.mark.unit
    def test_a_no_data_value_float32_cannot_hold_exactly_promotes_to_float64(self, tmp_path):
        ensure_gdal_drivers()
        (tmp_path / "series").mkdir()
        write_pcraster_map(
            tmp_path / "series" / series_name("v", 1),
            np.array([[1.0, 2.0], [3.0, 4.0]]),
            ValueScale.SCALAR,
            TRANSFORM,
        )

        # 1e40 overflows float32 to inf; a naive round-trip comparison of the
        # overflowed inf against the original value would wrongly call them
        # equal (NEP 50 casts the Python scalar down to the array's dtype for
        # the comparison), so this also guards against that pitfall.
        written = mapseries2tif(tmp_path / "series", "v", nodata=1e40)

        data = read_raster(written[0])
        assert data.array.dtype == np.float64
        assert data.nodata == pytest.approx(1e40)

    @pytest.mark.unit
    def test_a_fractional_no_data_value_is_refused_on_an_integer_value_scale(self, tmp_path):
        ensure_gdal_drivers()
        (tmp_path / "series").mkdir()
        write_pcraster_map(
            tmp_path / "series" / series_name("b", 1),
            np.array([[1.0, 0.0], [1.0, np.nan]]),
            ValueScale.BOOLEAN,
            TRANSFORM,
        )

        with pytest.raises(PreprocessingError, match="fractional"):
            mapseries2tif(tmp_path / "series", "b", nodata=-9999.5)

    @pytest.mark.unit
    def test_a_stale_manifest_does_not_survive_a_failing_run(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        ensure_gdal_drivers()
        other = write_geotiff(tmp_path / "other.tif", np.ones((4, 4), np.float32), TRANSFORM)
        (tmp_path / "tif").mkdir()
        (tmp_path / "tif" / "manifest.csv").write_text("source,target\nstale,stale\n", "utf8")

        with pytest.raises(PreprocessingError, match="does not share the geometry"):
            mapseries2tif(config["DIRECTORIES"]["prec"], "prec", tmp_path / "tif", other)

        assert not (tmp_path / "tif" / "manifest.csv").exists()

    @pytest.mark.unit
    def test_an_integer_source_with_a_valid_zero_refuses_no_data_zero(self, tmp_path):
        ensure_gdal_drivers()
        (tmp_path / "series").mkdir()
        write_pcraster_map(
            tmp_path / "series" / series_name("b", 1),
            np.array([[0.0, 1.0], [1.0, np.nan]]),
            ValueScale.BOOLEAN,
            TRANSFORM,
        )

        with pytest.raises(PreprocessingError, match="valid cell"):
            mapseries2tif(tmp_path / "series", "b", nodata=0)

        # The default sentinel does not collide with any valid cell.
        written = mapseries2tif(tmp_path / "series", "b")
        assert read_raster(written[0]).nodata == -9999.0

    @pytest.mark.unit
    def test_a_floating_source_with_a_valid_zero_refuses_no_data_zero(self, tmp_path):
        ensure_gdal_drivers()
        (tmp_path / "series").mkdir()
        write_pcraster_map(
            tmp_path / "series" / series_name("v", 1),
            np.array([[0.0, 1.5], [2.5, np.nan]]),
            ValueScale.SCALAR,
            TRANSFORM,
        )

        with pytest.raises(PreprocessingError, match="valid cell"):
            mapseries2tif(tmp_path / "series", "v", nodata=0.0)

        written = mapseries2tif(tmp_path / "series", "v")
        assert read_raster(written[0]).nodata == -9999.0


class TestCommands:
    @pytest.mark.unit
    def test_tif2map_prints_the_maps_written(self, tmp_path, capsys, restore_logging):
        geotiffs(tmp_path / "in", count=2)

        main(
            [
                "preprocess",
                "tif2map",
                str(tmp_path / "in"),
                "-o",
                str(tmp_path / "out"),
                "--value-scale",
                "scalar",
            ]
        )

        assert capsys.readouterr().out.splitlines() == [
            str(tmp_path / "out" / "etp1.map"),
            str(tmp_path / "out" / "etp2.map"),
        ]

    @pytest.mark.unit
    def test_tif2mapseries_and_back(self, tmp_path, capsys, restore_logging):
        geotiffs(tmp_path / "in", count=2)

        main(
            [
                "preprocess",
                "tif2mapseries",
                str(tmp_path / "in"),
                "--prefix",
                "etp",
                "-o",
                str(tmp_path / "series"),
            ]
        )
        main(
            [
                "preprocess",
                "mapseries2tif",
                str(tmp_path / "series"),
                "--prefix",
                "etp",
                "-o",
                str(tmp_path / "back"),
            ]
        )

        assert sorted(os.listdir(tmp_path / "back")) == [
            "etp0000001.tif",
            "etp0000002.tif",
            "manifest.csv",
        ]

    @pytest.mark.unit
    def test_tool_errors_exit_with_one(self, tmp_path, capsys, restore_logging):
        (tmp_path / "empty").mkdir()

        with pytest.raises(SystemExit) as error:
            main(["preprocess", "tif2map", str(tmp_path / "empty")])

        assert error.value.code == 1
        assert "No GeoTIFF file" in capsys.readouterr().err

    @pytest.mark.unit
    def test_an_unknown_value_scale_exits_with_one(self, tmp_path, capsys, restore_logging):
        geotiffs(tmp_path / "in", count=1)

        with pytest.raises(SystemExit) as error:
            main(["preprocess", "tif2map", str(tmp_path / "in"), "--value-scale", "fuzzy"])

        assert error.value.code == 1


class TestDeprecatedModules:
    @pytest.mark.unit
    @pytest.mark.parametrize("name", ["tif2map", "tif2pcrtss", "pcrtss2tif"])
    def test_importing_the_legacy_modules_warns(self, name):
        sys.modules.pop(f"rubem.preprocessing.{name}", None)

        with pytest.warns(DeprecationWarning, match="rubem.preprocessing.conversions"):
            module = importlib.import_module(f"rubem.preprocessing.{name}")

        assert module is not None
