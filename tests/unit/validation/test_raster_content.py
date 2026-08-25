import numpy as np
import pytest

from rubem.validation.raster_content import (
    check_below_one,
    check_extremes,
    check_positive,
    check_sample_ids,
)


class TestCheckPositive:
    @pytest.mark.unit
    def test_accepts_positive_cells_and_ignores_missing_ones(self):
        values = np.array([[0.5, -9999.0], [1.0, 2.0]])

        assert check_positive(values, -9999.0, "kp.001", "Kp") is None

    @pytest.mark.unit
    def test_rejects_zero_or_negative_cells(self):
        problem = check_positive(np.array([[0.0, 1.0]]), None, "kp.001", "Kp")

        assert problem is not None and problem.blocking
        assert "Kp raster has cells that are not positive" in problem.description
        assert problem.file == "kp.001"


class TestCheckBelowOne:
    @pytest.mark.unit
    def test_accepts_values_below_one(self):
        assert check_below_one(np.array([[0.1, 0.999]]), None, "ndvi", "NDVI") is None

    @pytest.mark.unit
    def test_rejects_one_or_more(self):
        problem = check_below_one(np.array([[0.1, 1.0]]), None, "ndvi", "NDVI")

        assert problem is not None and problem.blocking
        assert "equal to or above 1" in problem.description


class TestCheckExtremes:
    @pytest.mark.unit
    def test_accepts_max_above_min_on_shared_valid_cells(self):
        minimum = np.array([[0.1, -9999.0], [0.2, 0.3]])
        maximum = np.array([[0.5, 0.0], [-9999.0, 0.9]])

        assert check_extremes(minimum, -9999.0, maximum, -9999.0, "ndvi_max") is None

    @pytest.mark.unit
    def test_rejects_equal_or_inverted_cells(self):
        problem = check_extremes(np.array([[0.5, 0.5]]), None, np.array([[0.5, 0.9]]), None, "f")

        assert problem is not None and problem.blocking
        assert "Cells with ndvi_max <= ndvi_min: 1" in problem.reason

    @pytest.mark.unit
    def test_rejects_different_shapes(self):
        problem = check_extremes(np.zeros((2, 2)), None, np.zeros((3, 3)), None, "f")

        assert problem is not None and "different shapes" in problem.description


class TestCheckSampleIds:
    @pytest.mark.unit
    def test_accepts_contiguous_ids_with_zero_and_missing_background(self):
        values = np.array([[1, 0, -9999], [2, 3, 0]])

        assert check_sample_ids(values, -9999, "samples") is None

    @pytest.mark.unit
    def test_rejects_gaps(self):
        problem = check_sample_ids(np.array([[1, 3]]), None, "samples")

        assert problem is not None and "contiguous from 1" in problem.description
        assert "[1, 3]" in problem.reason

    @pytest.mark.unit
    def test_rejects_non_integer_or_negative_ids(self):
        assert "positive integers" in check_sample_ids(np.array([[1.5, 2]]), None, "s").description
        assert "positive integers" in check_sample_ids(np.array([[-1, 1]]), None, "s").description

    @pytest.mark.unit
    def test_rejects_a_raster_without_samples(self):
        problem = check_sample_ids(np.array([[0, -9999]]), -9999, "samples")

        assert problem is not None and "has no sample" in problem.description
