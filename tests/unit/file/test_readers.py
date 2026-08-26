import numpy as np
import pytest

from rubem.file._readers import FieldScale, geotiff_series_member, is_geotiff, read_field, set_clone
from rubem.preprocessing._io import write_geotiff
from tests.helpers.compare import ensure_gdal_drivers
from tests.helpers.synthetic import write_synthetic_dataset

TRANSFORM = (0.0, 500.0, 0.0, 1500.0, 0.0, -500.0)


class TestSetClone:
    @pytest.mark.unit
    def test_a_geotiff_clone_sets_the_pcraster_grid(self, tmp_path):
        import pcraster as pcr

        ensure_gdal_drivers()
        clone = write_geotiff(tmp_path / "clone.tif", np.ones((2, 4), np.uint8), TRANSFORM)

        set_clone(clone)

        assert (pcr.clone().nrRows(), pcr.clone().nrCols()) == (2, 4)
        assert (pcr.clone().west(), pcr.clone().north(), pcr.clone().cellSize()) == (
            0.0,
            1500.0,
            500.0,
        )

    @pytest.mark.unit
    def test_rotated_or_non_square_geotiff_clones_are_refused(self, tmp_path):
        ensure_gdal_drivers()
        rotated = write_geotiff(
            tmp_path / "r.tif", np.ones((2, 2), np.uint8), (0, 1, 0.1, 2, 0, -1)
        )
        with pytest.raises(ValueError, match="north-up"):
            set_clone(rotated)
        rectangular = write_geotiff(
            tmp_path / "q.tif", np.ones((2, 2), np.uint8), (0, 1, 0, 2, 0, -2)
        )
        with pytest.raises(ValueError, match="non-square"):
            set_clone(rectangular)

    @pytest.mark.unit
    def test_a_map_clone_is_read_by_pcraster(self, tmp_path):
        import pcraster as pcr

        config = write_synthetic_dataset(str(tmp_path))

        set_clone(config["RASTERS"]["clone"])

        assert pcr.clone().nrRows() == 3

    @pytest.mark.unit
    def test_a_mirrored_geotiff_clone_is_refused(self, tmp_path):
        """PCRaster grids are north-up with an increasing column index; a
        clone whose cell size is negative in x or positive in y is flipped."""
        ensure_gdal_drivers()
        mirrored_x = write_geotiff(
            tmp_path / "mx.tif", np.ones((2, 2), np.uint8), (0, -1, 0, 2, 0, -1)
        )
        with pytest.raises(ValueError, match="north-up"):
            set_clone(mirrored_x)
        mirrored_y = write_geotiff(
            tmp_path / "my.tif", np.ones((2, 2), np.uint8), (0, 1, 0, 2, 0, 1)
        )
        with pytest.raises(ValueError, match="north-up"):
            set_clone(mirrored_y)

    @pytest.mark.unit
    def test_the_clone_crs_is_recorded_for_read_time_checks(self, tmp_path):
        import rubem.file._readers as readers

        ensure_gdal_drivers()
        clone = write_geotiff(
            tmp_path / "clone.tif",
            np.ones((2, 2), np.uint8),
            TRANSFORM,
            projection='LOCAL_CS["Grid A",UNIT["metre",1]]',
        )

        set_clone(clone)

        assert "Grid A" in readers._clone_projection


class TestReadField:
    @pytest.mark.unit
    def test_scales_and_missing_values(self, tmp_path):
        import pcraster as pcr

        ensure_gdal_drivers()
        clone = write_geotiff(tmp_path / "clone.tif", np.ones((2, 2), np.uint8), TRANSFORM)
        set_clone(clone)
        scalar = write_geotiff(
            tmp_path / "s.tif",
            np.array([[1.5, -9999.0], [2.5, 3.5]], np.float32),
            TRANSFORM,
            nodata=-9999.0,
        )
        nominal = write_geotiff(
            tmp_path / "n.tif", np.array([[1, 2], [-9999, 4]], np.int32), TRANSFORM, nodata=-9999
        )

        values = pcr.pcr2numpy(read_field(scalar, FieldScale.SCALAR), -1.0)
        classes = pcr.pcr2numpy(read_field(nominal, FieldScale.NOMINAL), -1)
        flags = pcr.pcr2numpy(read_field(nominal, FieldScale.BOOLEAN), 9)

        assert values.tolist() == [[1.5, -1.0], [2.5, 3.5]]
        assert classes.tolist() == [[1, 2], [-1, 4]]
        assert flags.tolist() == [[1, 1], [9, 1]]
        assert is_geotiff(scalar) and not is_geotiff(tmp_path / "x.map")

    @pytest.mark.unit
    def test_geometry_mismatch_is_refused(self, tmp_path):
        ensure_gdal_drivers()
        set_clone(write_geotiff(tmp_path / "clone.tif", np.ones((2, 2), np.uint8), TRANSFORM))
        bigger = write_geotiff(tmp_path / "b.tif", np.ones((3, 3), np.float32), TRANSFORM)
        shifted = write_geotiff(
            tmp_path / "s.tif", np.ones((2, 2), np.float32), (1.0,) + TRANSFORM[1:]
        )

        with pytest.raises(ValueError, match="the clone has 2x2"):
            read_field(bigger, FieldScale.SCALAR)
        with pytest.raises(ValueError, match="does not share the clone geometry"):
            read_field(shifted, FieldScale.SCALAR)

    @pytest.mark.unit
    def test_a_mirrored_y_member_is_refused(self, tmp_path):
        """The geometry predicate must compare the y cell size too, not just
        west/cell/north: a member whose y resolution is positive (mirrored,
        south-up) instead of negative must not be placed on the clone grid
        upside down."""
        ensure_gdal_drivers()
        set_clone(write_geotiff(tmp_path / "clone.tif", np.ones((2, 2), np.uint8), TRANSFORM))
        mirrored = write_geotiff(
            tmp_path / "m.tif", np.ones((2, 2), np.float32), TRANSFORM[:5] + (500.0,)
        )

        with pytest.raises(ValueError, match="does not share the clone geometry"):
            read_field(mirrored, FieldScale.SCALAR)

    @pytest.mark.unit
    def test_a_non_square_member_is_refused(self, tmp_path):
        """A member whose y cell size differs in magnitude from the clone's
        (non-square, or a different resolution) must not be silently
        rescaled onto the clone grid."""
        ensure_gdal_drivers()
        set_clone(write_geotiff(tmp_path / "clone.tif", np.ones((2, 2), np.uint8), TRANSFORM))
        non_square = write_geotiff(
            tmp_path / "n.tif", np.ones((2, 2), np.float32), TRANSFORM[:5] + (-400.0,)
        )

        with pytest.raises(ValueError, match="does not share the clone geometry"):
            read_field(non_square, FieldScale.SCALAR)

    @pytest.mark.unit
    def test_a_crs_mismatch_is_refused_at_read_time(self, tmp_path):
        ensure_gdal_drivers()
        set_clone(
            write_geotiff(
                tmp_path / "clone.tif",
                np.ones((2, 2), np.uint8),
                TRANSFORM,
                projection='LOCAL_CS["Grid A",UNIT["metre",1]]',
            )
        )
        other_crs = write_geotiff(
            tmp_path / "s.tif",
            np.ones((2, 2), np.float32),
            TRANSFORM,
            projection='LOCAL_CS["Grid B",UNIT["foot",0.3048]]',
        )

        with pytest.raises(ValueError, match="coordinate reference system"):
            read_field(other_crs, FieldScale.SCALAR)

    @pytest.mark.unit
    def test_a_matching_crs_is_accepted_at_read_time(self, tmp_path):
        ensure_gdal_drivers()
        set_clone(
            write_geotiff(
                tmp_path / "clone.tif",
                np.ones((2, 2), np.uint8),
                TRANSFORM,
                projection='LOCAL_CS["Grid A",UNIT["metre",1]]',
            )
        )
        same_crs = write_geotiff(
            tmp_path / "s.tif",
            np.ones((2, 2), np.float32),
            TRANSFORM,
            projection='LOCAL_CS["Grid A",UNIT["metre",1]]',
        )

        read_field(same_crs, FieldScale.SCALAR)  # Does not raise.


class TestReadFieldCategoricalValues:
    @pytest.mark.unit
    def test_a_false_cell_and_a_minus_9999_class_survive(self, tmp_path):
        """Neither 0 (a valid Boolean False) nor -9999 (a valid class when the
        raster declares no no-data value) may double as the missing marker."""
        import pcraster as pcr

        ensure_gdal_drivers()
        clone = write_geotiff(tmp_path / "clone.tif", np.ones((2, 2), np.uint8), TRANSFORM)
        set_clone(clone)
        nominal = write_geotiff(
            tmp_path / "n.tif", np.array([[0, -9999], [7, 1]], np.int32), TRANSFORM
        )

        classes = pcr.pcr2numpy(read_field(nominal, FieldScale.NOMINAL), -1)
        flags = pcr.pcr2numpy(read_field(nominal, FieldScale.BOOLEAN), 9)

        assert classes.tolist() == [[0, -9999], [7, 1]]
        assert flags.tolist() == [[0, 1], [1, 1]]

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "value, message",
        [
            (1.5, "non-integer values"),
            (3e9, "32-bit integer range"),
            (-2147483648.0, "32-bit integer range"),
        ],
    )
    def test_values_the_int32_cast_would_alter_are_refused(self, tmp_path, value, message):
        """Rounding 1.5 onto class 2 or wrapping 3e9 onto another class would be
        silent corruption; the scalar scale keeps the same values untouched."""
        import pcraster as pcr

        ensure_gdal_drivers()
        clone = write_geotiff(tmp_path / "clone.tif", np.ones((2, 2), np.uint8), TRANSFORM)
        set_clone(clone)
        raster = write_geotiff(
            tmp_path / "n.tif",
            np.array([[1.0, value], [3.0, 4.0]], np.float64),
            TRANSFORM,
            nodata=-9999.0,
        )

        for scale in (FieldScale.NOMINAL, FieldScale.BOOLEAN, FieldScale.LDD):
            with pytest.raises(ValueError, match=message):
                read_field(raster, scale)
        values = pcr.pcr2numpy(read_field(raster, FieldScale.SCALAR), -1.0)
        assert values[0, 1] == pytest.approx(value)


class TestReadFieldLDDRegression:
    @pytest.mark.unit
    def test_a_nominal_scale_map_with_ldd_codes_is_converted_to_ldd(self, tmp_path):
        """A .map file whose own header declares Nominal, but whose cells hold
        valid LDD direction codes, must still be usable as an LDD field:
        ``pcr.accuflux`` refuses anything that is not actually LDD-typed."""
        import pcraster as pcr

        set_clone(write_geotiff(tmp_path / "clone.tif", np.ones((2, 2), np.uint8), TRANSFORM))
        codes = np.array([[5, 5], [5, 5]], dtype=np.int32)  # 5 = pit, every cell its own outlet
        ldd_path = str(tmp_path / "ldd.map")
        pcr.report(pcr.numpy2pcr(pcr.Nominal, codes, -9999), ldd_path)

        field = read_field(ldd_path, FieldScale.LDD)

        flux = pcr.accuflux(field, pcr.scalar(1))
        assert pcr.pcr2numpy(flux, -1.0).tolist() == [[1.0, 1.0], [1.0, 1.0]]

    @pytest.mark.unit
    def test_a_scalar_map_scale_is_left_unconverted(self, tmp_path):
        """Non-LDD scales are read as-is, matching the removed code, which
        applied no conversion for them either."""
        import pcraster as pcr

        config = write_synthetic_dataset(str(tmp_path))
        set_clone(config["RASTERS"]["clone"])

        field = read_field(config["RASTERS"]["dem"], FieldScale.SCALAR)

        assert pcr.pcr2numpy(field, -1.0).shape == (3, 3)


class TestGeotiffSeriesMember:
    @pytest.mark.unit
    def test_finds_the_exact_case_member(self, tmp_path):
        from tests.helpers.synthetic import geotiff_series_name

        name = geotiff_series_name("prec", 1)
        (tmp_path / name).write_bytes(b"")

        found = geotiff_series_member(tmp_path, "prec", 1)

        assert found == tmp_path / name

    @pytest.mark.unit
    def test_finds_a_member_regardless_of_case(self, tmp_path):
        """On a case-sensitive file system the fallback scan returns the
        member with its on-disk case; on a case-insensitive one (Windows) the
        exact-case candidate already resolves to it. Either way it is found."""
        from tests.helpers.synthetic import geotiff_series_name

        name = geotiff_series_name("prec", 1).upper()
        (tmp_path / name).write_bytes(b"")

        found = geotiff_series_member(tmp_path, "prec", 1)

        assert found is not None
        assert found.is_file()
        assert found.name.lower() == name.lower()

    @pytest.mark.unit
    def test_returns_none_when_no_member_exists(self, tmp_path):
        assert geotiff_series_member(tmp_path, "prec", 1) is None
        assert geotiff_series_member(tmp_path / "missing", "prec", 1) is None

    @pytest.mark.unit
    def test_raises_when_two_case_variants_match_the_same_step(self, tmp_path):
        """On a case-sensitive file system, a differently-cased name is a
        distinct file: two of them for the same step must not be resolved
        silently (which one is used would depend on directory iteration
        order). NTFS (Windows) cannot hold both, so the probe below skips
        there instead of asserting a false negative."""
        from tests.helpers.synthetic import geotiff_series_name

        name = geotiff_series_name("prec", 1)
        (tmp_path / name).write_bytes(b"")
        (tmp_path / name.upper()).write_bytes(b"")
        if len(list(tmp_path.iterdir())) < 2:
            pytest.skip("the file system is case-insensitive; both names collapse into one file")

        with pytest.raises(ValueError, match="matches more than one file"):
            geotiff_series_member(tmp_path, "prec", 1)
