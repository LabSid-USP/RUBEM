"""The decision vector of the calibration: bounds, conversions and admissibility."""

import numpy as np
import pytest

from rubem.calibration.parameters import (
    CALIBRATION_PARAMETERS,
    DERIVED_PARAMETER,
    FREE_PARAMETERS,
    bounds,
    is_admissible,
    parameters_to_vector,
    vector_to_parameters,
    weights_constraint,
)
from rubem.configuration.app_settings import AppSettings
from rubem.configuration.calibration_parameters import CalibrationParameters
from rubem.configuration.model_configuration import ModelConfiguration
from tests.helpers.synthetic import write_synthetic_dataset

# The ranges of rubem/appsettings.json, written out so that a change of the
# settings file, or of the order of the decision vector, has to be made here
# too instead of passing unnoticed through a comparison with the same source.
SETTINGS_BOUNDS = {
    "alpha": (0.01, 10.0),
    "beta": (0.01, 1.0),
    "w_1": (0.0, 1.0),
    "w_2": (0.0, 1.0),
    "w_3": (0.0, 1.0),
    "rcd": (1.0, 10.0),
    "f": (0.01, 1.0),
    "alpha_gw": (0.01, 1.0),
    "x": (0.0, 1.0),
}


def admissible_vector():
    """A decision vector well inside every bound, with weights that add up below 1."""
    return np.array([4.5, 0.5, 0.333, 0.333, 5.0, 0.5, 0.5, 0.5], dtype=np.float64)


class TestBounds:
    @pytest.mark.unit
    def test_the_bounds_are_the_ranges_of_the_application_settings(self):
        ranges = AppSettings.default().value_ranges.variables

        assert bounds() == [(ranges[name].min, ranges[name].max) for name in FREE_PARAMETERS]

    @pytest.mark.unit
    def test_the_bounds_are_the_ones_written_in_the_settings_file(self):
        assert bounds() == [SETTINGS_BOUNDS[name] for name in FREE_PARAMETERS]
        assert [name for name in SETTINGS_BOUNDS if name != DERIVED_PARAMETER] == list(
            FREE_PARAMETERS
        )

    @pytest.mark.unit
    def test_the_free_parameters_do_not_include_the_derived_weight(self):
        assert DERIVED_PARAMETER not in FREE_PARAMETERS
        assert set(CALIBRATION_PARAMETERS) == set(FREE_PARAMETERS) | {DERIVED_PARAMETER}
        assert len(bounds()) == len(FREE_PARAMETERS) == 8


class TestConversions:
    @pytest.mark.unit
    def test_a_vector_becomes_the_nine_parameters_with_the_derived_weight(self):
        parameters = vector_to_parameters(admissible_vector())

        assert list(parameters) == list(CALIBRATION_PARAMETERS)
        assert parameters["beta"] == 0.5
        assert parameters["w_3"] == 1.0 - (0.333 + 0.333)
        assert parameters["w_1"] + parameters["w_2"] + parameters["w_3"] == pytest.approx(1.0)

    @pytest.mark.unit
    def test_a_vector_of_the_wrong_size_is_rejected(self):
        with pytest.raises(ValueError, match="must have 8 entries"):
            vector_to_parameters([1.0, 2.0, 3.0])

    @pytest.mark.unit
    def test_the_configuration_parameters_round_trip_through_the_vector(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        configuration = ModelConfiguration(config, validate_input=False)
        parameters = configuration.calibration_parameters.model_dump()

        vector = parameters_to_vector(parameters)

        assert vector_to_parameters(vector) == pytest.approx(parameters, abs=1e-12)

    @pytest.mark.unit
    def test_the_legacy_spellings_of_the_parameters_are_accepted(self):
        legacy = {
            "alpha": 4.5,
            "b": 0.5,
            "w1": 0.333,
            "w2": 0.333,
            "w3": 0.334,
            "rcd": 5.0,
            "f": 0.5,
            "alpha_gw": 0.5,
            "x": 0.5,
        }

        assert parameters_to_vector(legacy) == pytest.approx(admissible_vector())

    @pytest.mark.unit
    def test_a_missing_parameter_names_what_the_vector_needs(self):
        with pytest.raises(KeyError, match="alpha_gw"):
            parameters_to_vector({"alpha": 4.5, "beta": 0.5})


class TestAdmissibility:
    @pytest.mark.unit
    def test_a_vector_inside_the_bounds_is_admissible(self):
        assert is_admissible(admissible_vector())

    @pytest.mark.unit
    def test_a_vector_on_the_bounds_is_admissible(self):
        vector = np.array([minimum for minimum, _ in bounds()], dtype=np.float64)

        assert is_admissible(vector)

    @pytest.mark.unit
    @pytest.mark.parametrize("index", range(8))
    def test_a_value_above_its_bound_is_rejected(self, index):
        vector = admissible_vector()
        vector[index] = bounds()[index][1] + 1.0

        assert not is_admissible(vector)

    @pytest.mark.unit
    @pytest.mark.parametrize("index", range(8))
    def test_a_value_below_its_bound_is_rejected(self, index):
        vector = admissible_vector()
        vector[index] = bounds()[index][0] - 1.0

        assert not is_admissible(vector)

    @pytest.mark.unit
    def test_weights_that_add_up_above_one_are_rejected(self):
        vector = admissible_vector()
        vector[FREE_PARAMETERS.index("w_1")] = 0.6
        vector[FREE_PARAMETERS.index("w_2")] = 0.6

        # Both weights are inside their own [0, 1] bound; what makes the
        # candidate inadmissible is their sum, and the negative w_3 it derives.
        assert vector_to_parameters(vector)["w_3"] < 0.0
        assert not is_admissible(vector)

    @pytest.mark.unit
    def test_weights_that_add_up_to_exactly_one_are_admissible(self):
        vector = admissible_vector()
        vector[FREE_PARAMETERS.index("w_1")] = 0.4
        vector[FREE_PARAMETERS.index("w_2")] = 0.6

        assert vector_to_parameters(vector)["w_3"] == 0.0
        assert is_admissible(vector)

    @pytest.mark.unit
    @pytest.mark.parametrize("hundredths", range(101))
    def test_every_pair_of_weights_that_adds_up_to_one_reaches_the_model(self, hundredths):
        """What the guard admits, the configuration model must accept.

        ``1 - w_1 - w_2`` rounds twice and lands one ulp below zero for 20 of
        these 101 pairs, ``w_1 = 0.33, w_2 = 0.67`` among them, which is a
        weight :class:`CalibrationParameters` refuses; deriving the weight with
        a single subtraction gives exactly zero for all of them.
        """
        vector = admissible_vector()
        vector[FREE_PARAMETERS.index("w_1")] = hundredths / 100.0
        vector[FREE_PARAMETERS.index("w_2")] = (100 - hundredths) / 100.0
        parameters = vector_to_parameters(vector)

        assert parameters["w_3"] == 0.0
        assert is_admissible(vector)
        # No exception: the candidate the guard admits is one the model runs.
        CalibrationParameters(**parameters)

    @pytest.mark.unit
    def test_the_guard_and_the_derivation_cannot_disagree(self):
        """Every admissible candidate of a grid is one the model accepts."""
        refused = []
        for first in range(0, 101, 7):
            for second in range(0, 101, 11):
                vector = admissible_vector()
                vector[FREE_PARAMETERS.index("w_1")] = first / 100.0
                vector[FREE_PARAMETERS.index("w_2")] = second / 100.0
                if not is_admissible(vector):
                    continue
                try:
                    CalibrationParameters(**vector_to_parameters(vector))
                except ValueError:
                    refused.append((first / 100.0, second / 100.0))

        assert not refused, f"admitted but refused by the model: {refused}"

    @pytest.mark.unit
    def test_a_vector_of_the_wrong_size_or_with_a_nan_is_rejected(self):
        vector = admissible_vector()
        vector[0] = np.nan

        assert not is_admissible(vector)
        assert not is_admissible(admissible_vector()[:-1])


class TestWeightsConstraint:
    """The only part of the module that needs the optional SciPy extra."""

    @pytest.fixture(autouse=True)
    def _scipy(self):
        pytest.importorskip("scipy.optimize")

    @pytest.mark.unit
    def test_the_constraint_is_the_sum_of_the_two_searched_weights(self):
        constraint = weights_constraint()

        expected = np.zeros((1, len(FREE_PARAMETERS)))
        expected[0, FREE_PARAMETERS.index("w_1")] = 1.0
        expected[0, FREE_PARAMETERS.index("w_2")] = 1.0
        assert np.array_equal(np.asarray(constraint.A), expected)
        assert np.all(np.asarray(constraint.lb) == -np.inf)
        assert np.all(np.asarray(constraint.ub) == 1.0)

    @pytest.mark.unit
    def test_the_constraint_evaluates_to_the_sum_of_the_weights(self):
        constraint = weights_constraint()
        vector = admissible_vector()

        assert np.asarray(constraint.A) @ vector == pytest.approx([0.666])
