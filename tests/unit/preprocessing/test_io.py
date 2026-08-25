import csv
import os

import numpy as np
import pytest

from rubem.preprocessing._io import (
    AllNoDataPolicy,
    AtomicOutput,
    PreprocessingError,
    RasterData,
    ValueScale,
    apply_all_nodata_policy,
    check_no_collisions,
    check_same_geometry,
    natural_sorted,
    read_raster,
    write_geotiff,
    write_manifest,
    write_pcraster_map,
)
from tests.helpers.compare import ensure_gdal_drivers
from tests.helpers.synthetic import write_synthetic_dataset

TRANSFORM = (0.0, 500.0, 0.0, 1500.0, 0.0, -500.0)
LOCAL_CRS = 'LOCAL_CS["Engineering grid",UNIT["metre",1]]'
# A different unit, not just a different name: osr.SpatialReference.IsSame()
# ignores the LOCAL_CS name, so this is what makes the two CRSs actually differ.
OTHER_LOCAL_CRS = 'LOCAL_CS["Engineering grid",UNIT["US survey foot",0.304800609601219]]'


def sample(nodata=-9999.0):
    array = np.arange(9, dtype=np.float32).reshape(3, 3)
    array[0, 0] = nodata
    return array


class TestReadWrite:
    @pytest.mark.unit
    def test_geotiff_round_trip_keeps_values_geometry_and_nodata(self, tmp_path):
        ensure_gdal_drivers()
        array = sample()

        written = write_geotiff(tmp_path / "grid.tif", array, TRANSFORM, nodata=-9999.0)
        data = read_raster(written)

        np.testing.assert_array_equal(data.array, array)
        assert data.nodata == -9999.0
        assert data.geotransform == pytest.approx(TRANSFORM)
        assert data.projection == ""
        assert data.source == str(written)
        assert (data.rows, data.cols, data.cell_size, data.west, data.north) == (
            3,
            3,
            500.0,
            0.0,
            1500.0,
        )
        assert not data.is_rotated
        assert data.mask().sum() == 8 and not data.all_nodata()
        assert not list(tmp_path.glob("*.tmp"))

    @pytest.mark.unit
    def test_geotiff_type_can_be_forced(self, tmp_path):
        ensure_gdal_drivers()

        written = write_geotiff(
            tmp_path / "ids.tif", np.ones((2, 2), dtype=np.int64), TRANSFORM, gdal_type="Int32"
        )

        assert read_raster(written).array.dtype == np.int32
        with pytest.raises(PreprocessingError, match="Unsupported data type"):
            write_geotiff(tmp_path / "bad.tif", np.ones((2, 2)), TRANSFORM, gdal_type="NoSuchType")

    @pytest.mark.unit
    def test_pcraster_map_round_trip(self, tmp_path):
        ensure_gdal_drivers()
        array = sample()

        written = write_pcraster_map(
            tmp_path / "grid.map", array, ValueScale.SCALAR, TRANSFORM, nodata=-9999.0
        )
        data = read_raster(written)

        assert data.geotransform == pytest.approx(TRANSFORM)
        assert data.mask().sum() == 8
        np.testing.assert_allclose(data.array[data.mask()], array[array != -9999.0])
        nominal = write_pcraster_map(
            tmp_path / "ids.map",
            np.array([[1, 2], [3, 0]]),
            ValueScale.NOMINAL,
            (0.0, 1.0, 0.0, 2.0, 0.0, -1.0),
        )
        assert read_raster(nominal).array.tolist() == [[1, 2], [3, 0]]

    @pytest.mark.unit
    def test_pcraster_map_refuses_rotation_and_non_square_cells(self, tmp_path):
        with pytest.raises(PreprocessingError, match="north-up"):
            write_pcraster_map(
                tmp_path / "r.map", np.ones((2, 2)), ValueScale.SCALAR, (0, 1, 0.1, 2, 0, -1)
            )
        with pytest.raises(PreprocessingError, match="square cells"):
            write_pcraster_map(
                tmp_path / "r.map", np.ones((2, 2)), ValueScale.SCALAR, (0, 1, 0, 2, 0, -2)
            )

    @pytest.mark.unit
    def test_pcraster_map_refuses_south_up_and_mirrored_geometries(self, tmp_path):
        with pytest.raises(PreprocessingError, match="cell_x > 0 and cell_y < 0"):
            write_pcraster_map(
                tmp_path / "south.map", np.ones((2, 2)), ValueScale.SCALAR, (0, 1, 0, 2, 0, 1)
            )
        with pytest.raises(PreprocessingError, match="cell_x > 0 and cell_y < 0"):
            write_pcraster_map(
                tmp_path / "mirrored.map", np.ones((2, 2)), ValueScale.SCALAR, (0, -1, 0, 2, 0, -1)
            )

    @pytest.mark.unit
    def test_directional_maps_keep_fractional_values(self, tmp_path):
        ensure_gdal_drivers()
        array = np.array([[1.75, 90.0], [180.0, -9999.0]])

        written = write_pcraster_map(
            tmp_path / "aspect.map", array, ValueScale.DIRECTIONAL, TRANSFORM, nodata=-9999.0
        )
        data = read_raster(written)

        assert data.mask().sum() == 3
        np.testing.assert_allclose(data.array[data.mask()], [1.75, 90.0, 180.0])

    @pytest.mark.unit
    def test_reading_errors_are_explicit(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_raster(tmp_path / "absent.tif")
        broken = tmp_path / "broken.tif"
        broken.write_bytes(b"not a raster")
        with pytest.raises(PreprocessingError, match="cannot be opened"):
            read_raster(broken)
        ensure_gdal_drivers()
        written = write_geotiff(tmp_path / "grid.tif", sample(), TRANSFORM)
        with pytest.raises(PreprocessingError, match="band 2 does not exist"):
            read_raster(written, band=2)

    @pytest.mark.unit
    def test_the_synthetic_dem_reads_as_a_raster(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        ensure_gdal_drivers()

        data = read_raster(config["RASTERS"]["dem"])

        assert (data.rows, data.cols) == (3, 3)
        assert data.array.min() == pytest.approx(100.0)


class TestContracts:
    @pytest.mark.unit
    def test_atomic_output_replaces_on_success_and_cleans_on_failure(self, tmp_path):
        target = tmp_path / "out.txt"
        with AtomicOutput(target) as temporary:
            temporary.write_text("done", encoding="utf8")
        assert target.read_text(encoding="utf8") == "done"

        with pytest.raises(RuntimeError):
            with AtomicOutput(target) as temporary:
                temporary.write_text("partial", encoding="utf8")
                raise RuntimeError("boom")
        assert target.read_text(encoding="utf8") == "done"
        assert not list(tmp_path.glob("*.tmp"))

    @pytest.mark.unit
    def test_natural_order(self):
        names = ["etp10.tif", "etp2.tif", "etp1.tif", "ETP3.tif"]

        assert [p.name for p in natural_sorted(names)] == [
            "etp1.tif",
            "etp2.tif",
            "ETP3.tif",
            "etp10.tif",
        ]

    @pytest.mark.unit
    def test_collisions_are_refused(self, tmp_path):
        check_no_collisions([("a.tif", tmp_path / "a.map"), ("b.tif", tmp_path / "b.map")])
        with pytest.raises(PreprocessingError, match="would both be written"):
            check_no_collisions([("a.tif", tmp_path / "x.map"), ("b.tif", tmp_path / "x.map")])

    @pytest.mark.unit
    def test_geometry_equality(self):
        reference = RasterData(np.ones((2, 2)), None, TRANSFORM, "", "ref")
        same = RasterData(np.zeros((2, 2)), None, TRANSFORM, "", "same")
        shifted = RasterData(np.zeros((2, 2)), None, (1.0,) + TRANSFORM[1:], "", "shifted")
        bigger = RasterData(np.zeros((3, 2)), None, TRANSFORM, "", "bigger")

        check_same_geometry(reference, same, "series")
        with pytest.raises(PreprocessingError, match="shifted"):
            check_same_geometry(reference, shifted, "series")
        with pytest.raises(PreprocessingError, match="bigger"):
            check_same_geometry(reference, bigger, "series")

    @pytest.mark.unit
    def test_geometry_equality_compares_the_crs_when_both_carry_one(self):
        reference = RasterData(np.ones((2, 2)), None, TRANSFORM, LOCAL_CRS, "ref")
        same_crs_raster = RasterData(np.zeros((2, 2)), None, TRANSFORM, LOCAL_CRS, "same-crs")
        other_crs = RasterData(np.zeros((2, 2)), None, TRANSFORM, OTHER_LOCAL_CRS, "other-crs")
        no_crs = RasterData(np.zeros((2, 2)), None, TRANSFORM, "", "no-crs")

        check_same_geometry(reference, same_crs_raster, "series")
        check_same_geometry(reference, no_crs, "series")
        check_same_geometry(no_crs, same_crs_raster, "series")
        with pytest.raises(PreprocessingError, match="coordinate reference systems"):
            check_same_geometry(reference, other_crs, "series")

    @pytest.mark.unit
    def test_all_nodata_policy(self, caplog):
        empty = RasterData(np.full((2, 2), -9999.0), -9999.0, TRANSFORM, "", "empty.tif")
        full = RasterData(np.ones((2, 2)), -9999.0, TRANSFORM, "", "full.tif")

        assert apply_all_nodata_policy(full, AllNoDataPolicy.ERROR, "series")
        with pytest.raises(PreprocessingError, match="every cell"):
            apply_all_nodata_policy(empty, AllNoDataPolicy.ERROR, "series")
        with caplog.at_level("WARNING"):
            assert apply_all_nodata_policy(empty, AllNoDataPolicy.WARN, "series")
            assert not apply_all_nodata_policy(empty, AllNoDataPolicy.SKIP, "series")
        assert caplog.text.count("every cell") == 2 and "Skipped." in caplog.text

    @pytest.mark.unit
    def test_nan_cells_count_as_missing_in_float_rasters(self):
        data = RasterData(np.array([[np.nan, 1.0]]), None, TRANSFORM, "")

        assert data.mask().tolist() == [[False, True]]

    @pytest.mark.unit
    def test_manifest_is_written_atomically(self, tmp_path):
        manifest = write_manifest(tmp_path, [("a.tif", "a.map"), ("b.tif", "b.map")])

        with manifest.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        assert rows == [["source", "target"], ["a.tif", "a.map"], ["b.tif", "b.map"]]
        assert os.listdir(tmp_path) == ["manifest.csv"]
