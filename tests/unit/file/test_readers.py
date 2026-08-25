import numpy as np
import pytest

from rubem.file._readers import FieldScale, is_geotiff, read_field, set_clone
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
