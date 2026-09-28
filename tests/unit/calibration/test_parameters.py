"""The decision vector of the calibration: bounds, conversions and admissibility."""

import numpy as np
import pytest

from rubem.calibration.modflow_parameters import ModflowCatalog
from rubem.calibration.parameters import (
    CALIBRATION_PARAMETERS,
    DERIVED_PARAMETER,
    FREE_PARAMETERS,
    bounds,
    decision_space,
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


class TestDefaultDecisionSpace:
    @pytest.mark.unit
    def test_a_space_without_arguments_is_the_whole_search(self):
        space = decision_space()

        assert space.free_names == FREE_PARAMETERS
        assert space.fixed == {}
        assert space.dimension == 8
        assert list(space.bounds) == bounds()

    @pytest.mark.unit
    def test_the_module_level_functions_are_the_default_space(self):
        space = decision_space()
        vector = admissible_vector()
        parameters = vector_to_parameters(vector)

        assert space.to_parameters(vector) == parameters
        assert space.from_parameters(parameters) == pytest.approx(parameters_to_vector(parameters))
        assert space.is_admissible(vector) is is_admissible(vector) is True
        assert np.array_equal(
            np.asarray(space.weights_constraint().A), np.asarray(weights_constraint().A)
        )


class TestFixedParameters:
    @pytest.mark.unit
    def test_a_fixed_parameter_leaves_the_vector_and_stays_in_the_parameters(self):
        space = decision_space(fixed={"x": 0.0})

        assert space.free_names == tuple(name for name in FREE_PARAMETERS if name != "x")
        assert space.dimension == 7
        assert space.fixed == {"x": 0.0}
        assert list(space.bounds) == [
            SETTINGS_BOUNDS[name] for name in FREE_PARAMETERS if name != "x"
        ]

        parameters = space.to_parameters(np.delete(admissible_vector(), FREE_PARAMETERS.index("x")))

        assert list(parameters) == list(CALIBRATION_PARAMETERS)
        assert parameters["x"] == 0.0
        assert parameters["alpha"] == 4.5
        assert parameters["w_3"] == pytest.approx(1.0 - 0.666)

    @pytest.mark.unit
    def test_the_free_vector_of_a_space_with_fixed_parameters_round_trips(self):
        space = decision_space(fixed={"x": 0.25, "alpha": 2.0})
        parameters = vector_to_parameters(admissible_vector())

        vector = space.from_parameters(parameters)

        assert len(vector) == space.dimension == 6
        # The fixed coordinates are dropped on the way in and restored, at the
        # value they were pinned to, on the way out.
        assert space.to_parameters(vector) == pytest.approx(
            {**parameters, "x": 0.25, "alpha": 2.0}, abs=1e-12
        )

    @pytest.mark.unit
    def test_the_legacy_spellings_name_the_parameter_that_is_fixed(self):
        space = decision_space(fixed={"b": 0.25, "w1": 0.5})

        assert space.fixed == {"beta": 0.25, "w_1": 0.5}
        assert "beta" not in space.free_names

    @pytest.mark.unit
    def test_a_vector_of_the_wrong_size_names_the_free_parameters(self):
        space = decision_space(fixed={"x": 0.0})

        with pytest.raises(ValueError, match="must have 7 entries"):
            space.to_parameters(admissible_vector())

    @pytest.mark.unit
    def test_the_derived_weight_cannot_be_fixed(self):
        with pytest.raises(ValueError, match="w_3"):
            decision_space(fixed={"w_3": 0.3})
        with pytest.raises(ValueError, match="derived"):
            decision_space(fixed={"w3": 0.3})

    @pytest.mark.unit
    def test_an_unknown_parameter_cannot_be_fixed(self):
        with pytest.raises(ValueError, match="not a searched calibration parameter"):
            decision_space(fixed={"gamma": 1.0})

    @pytest.mark.unit
    @pytest.mark.parametrize("value", [-0.5, 1.5, float("nan")])
    def test_a_fixed_value_outside_the_settings_range_is_refused(self, value):
        with pytest.raises(ValueError, match=r"'x' cannot be fixed"):
            decision_space(fixed={"x": value})

    @pytest.mark.unit
    def test_fixing_every_parameter_leaves_nothing_to_search(self):
        every = {name: minimum for name, (minimum, _) in SETTINGS_BOUNDS.items()}
        every.pop(DERIVED_PARAMETER)

        with pytest.raises(ValueError, match="nothing to look for"):
            decision_space(fixed=every)


class TestFixedWeights:
    @pytest.mark.unit
    def test_a_weight_left_with_one_value_is_fixed_as_well(self):
        """w_1 = 1 leaves w_2 no room: w_2 = 0 is fixed and leaves the vector.

        The dimension, the budget and the initial population then describe the
        search that runs, and no zero-width coordinate reaches the optimizer.
        """
        space = decision_space(fixed={"w_1": 1.0})

        assert "w_2" not in space.free_names
        assert space.fixed == {"w_1": 1.0, "w_2": 0.0}
        assert space.dimension == 6
        assert space.weights_constraint() is None
        parameters = space.to_parameters([4.5, 0.5, 5.0, 0.5, 0.5, 0.5])
        assert (parameters["w_1"], parameters["w_2"], parameters["w_3"]) == (1.0, 0.0, 0.0)

    @pytest.mark.unit
    def test_fixing_one_weight_narrows_the_other_instead_of_constraining_the_pair(self):
        space = decision_space(fixed={"w_1": 0.7})
        position = space.free_names.index("w_2")

        # w_3 = 1 - w_1 - w_2 may not fall below its own minimum, so w_2 is
        # searched in [0, 0.3] and the pair needs no constraint of its own.
        assert space.bounds[position] == (0.0, pytest.approx(0.3))
        assert space.weights_constraint() is None

    @pytest.mark.unit
    def test_the_narrowed_bound_keeps_the_override_when_the_override_is_tighter(self):
        space = decision_space(fixed={"w_2": 0.5}, bounds={"w_1": (0.1, 0.2)})
        position = space.free_names.index("w_1")

        assert space.bounds[position] == (0.1, 0.2)

    @pytest.mark.unit
    def test_a_fixed_weight_that_leaves_the_other_no_value_is_refused(self):
        with pytest.raises(ValueError, match="no value in its range"):
            decision_space(fixed={"w_1": 0.9}, bounds={"w_2": (0.2, 0.5)})

    @pytest.mark.unit
    def test_fixing_both_weights_checks_the_derived_one(self):
        space = decision_space(fixed={"w_1": 0.3, "w_2": 0.4})
        vector = np.array([4.5, 0.5, 5.0, 0.5, 0.5, 0.5], dtype=np.float64)

        assert space.free_names == ("alpha", "beta", "rcd", "f", "alpha_gw", "x")
        assert space.weights_constraint() is None
        assert space.to_parameters(vector)["w_3"] == pytest.approx(0.3)
        assert space.is_admissible(vector)

    @pytest.mark.unit
    def test_two_fixed_weights_that_add_up_above_one_are_refused(self):
        with pytest.raises(ValueError, match="derives w_3"):
            decision_space(fixed={"w_1": 0.6, "w_2": 0.6})

    @pytest.mark.unit
    def test_the_constraint_follows_the_positions_of_the_weights_in_the_vector(self):
        pytest.importorskip("scipy.optimize")
        space = decision_space(fixed={"alpha": 5.0})
        constraint = space.weights_constraint()

        expected = np.zeros((1, space.dimension))
        expected[0, space.free_names.index("w_1")] = 1.0
        expected[0, space.free_names.index("w_2")] = 1.0
        assert np.array_equal(np.asarray(constraint.A), expected)
        assert np.all(np.asarray(constraint.ub) == 1.0)


class TestOverriddenBounds:
    @pytest.mark.unit
    def test_an_override_narrows_the_range_of_the_settings(self):
        space = decision_space(bounds={"rcd": (2.0, 5.0)})
        position = space.free_names.index("rcd")

        assert space.bounds[position] == (2.0, 5.0)
        assert [
            bound
            for name, bound in zip(space.free_names, space.bounds, strict=True)
            if name != "rcd"
        ] == [SETTINGS_BOUNDS[name] for name in FREE_PARAMETERS if name != "rcd"]

    @pytest.mark.unit
    def test_a_candidate_outside_the_narrowed_bound_is_not_admissible(self):
        space = decision_space(bounds={"rcd": (2.0, 5.0)})
        vector = admissible_vector()

        assert space.is_admissible(vector)
        vector[FREE_PARAMETERS.index("rcd")] = 8.0
        assert not space.is_admissible(vector)
        # The same candidate is admissible in the default space: the refusal is
        # the narrowed bound of this run and not a bound of the model.
        assert is_admissible(vector)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "override",
        [(0.5, 5.0), (2.0, 12.0), (5.0, 2.0), (3.0, 3.0), (float("nan"), 5.0)],
        ids=["below", "above", "reversed", "empty", "not a number"],
    )
    def test_a_bound_that_does_not_narrow_the_settings_range_is_refused(self, override):
        with pytest.raises(ValueError, match=r"of 'rcd' is not a narrower range") as failure:
            decision_space(bounds={"rcd": override})

        # Both ranges are named, so the message says what was asked and what is
        # available.
        assert "(1.0, 10.0)" in str(failure.value)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "override", [3.0, (3.0,), (1.0, 2.0, 3.0)], ids=["a number", "one value", "three values"]
    )
    def test_a_bound_that_is_not_a_pair_is_refused(self, override):
        # A bound is a range: anything else is answered with the pair it needs
        # and not with the error of the conversion it failed.
        with pytest.raises(ValueError, match=r"bound of 'rcd' must be a \(minimum, maximum\) pair"):
            decision_space(bounds={"rcd": override})

    @pytest.mark.unit
    def test_a_bound_of_the_derived_or_of_an_unknown_parameter_is_refused(self):
        with pytest.raises(ValueError, match="derived"):
            decision_space(bounds={"w_3": (0.1, 0.5)})
        with pytest.raises(ValueError, match="not a searched calibration parameter"):
            decision_space(bounds={"gamma": (0.1, 0.5)})

    @pytest.mark.unit
    def test_a_bound_of_a_fixed_parameter_has_nowhere_to_apply(self):
        with pytest.raises(ValueError, match="nowhere to apply"):
            decision_space(fixed={"rcd": 3.0}, bounds={"rcd": (2.0, 5.0)})


SPECIFIC_YIELD = "modflow.layers.1.specific_yield"
KH = "modflow.layers.1.kh.2"
CONDUCTANCE = "modflow.river.1.conductance"


@pytest.fixture
def catalog():
    """The MODFLOW parameters of a configuration, in the order of its section."""
    return ModflowCatalog(
        values={SPECIFIC_YIELD: 0.15, "modflow.layers.1.kh.1": 0.5, KH: 0.1, CONDUCTANCE: 0.387},
        tables={1: [("1", 0.5), ("2", 0.1)]},
    )


class TestModflowParameters:
    @pytest.mark.unit
    def test_without_a_modflow_name_the_space_is_the_one_of_today(self, catalog):
        assert decision_space(modflow=catalog) == decision_space()
        assert decision_space(
            fixed={"x": 0.0}, bounds={"rcd": (2.0, 5.0)}, modflow=catalog
        ) == decision_space(fixed={"x": 0.0}, bounds={"rcd": (2.0, 5.0)})
        assert decision_space().modflow_names == ()

    @pytest.mark.unit
    def test_a_bounded_name_is_searched_after_the_eight_parameters(self, catalog):
        space = decision_space(bounds={SPECIFIC_YIELD: (0.05, 0.3)}, modflow=catalog)

        assert space.free_names == (*FREE_PARAMETERS, SPECIFIC_YIELD)
        assert space.bounds[-1] == (0.05, 0.3)
        assert space.dimension == 9
        assert space.modflow_names == (SPECIFIC_YIELD,)

    @pytest.mark.unit
    def test_the_names_follow_the_catalog_whatever_order_they_are_given_in(self, catalog):
        space = decision_space(
            bounds={CONDUCTANCE: (0.1, 0.5), KH: (0.05, 0.5), SPECIFIC_YIELD: (0.05, 0.3)},
            modflow=catalog,
        )

        assert space.free_names[8:] == (SPECIFIC_YIELD, KH, CONDUCTANCE)
        assert space.bounds[8:] == ((0.05, 0.3), (0.05, 0.5), (0.1, 0.5))

    @pytest.mark.unit
    def test_a_candidate_carries_the_nine_parameters_and_the_modflow_ones(self, catalog):
        space = decision_space(
            fixed={CONDUCTANCE: 0.2}, bounds={SPECIFIC_YIELD: (0.05, 0.3)}, modflow=catalog
        )
        vector = np.append(admissible_vector(), 0.25)

        parameters = space.to_parameters(vector)

        assert list(parameters) == [*CALIBRATION_PARAMETERS, SPECIFIC_YIELD, CONDUCTANCE]
        assert parameters[SPECIFIC_YIELD] == 0.25
        assert parameters[CONDUCTANCE] == 0.2
        assert parameters["w_3"] == pytest.approx(1.0 - 0.666)
        assert space.fixed == {CONDUCTANCE: 0.2}
        assert space.modflow_names == (SPECIFIC_YIELD, CONDUCTANCE)

    @pytest.mark.unit
    def test_the_starting_point_reads_the_modflow_values(self, catalog):
        space = decision_space(bounds={KH: (0.05, 0.5)}, modflow=catalog)
        parameters = vector_to_parameters(admissible_vector())

        vector = space.from_parameters({**parameters, **catalog.values})

        assert vector.tolist() == pytest.approx([*admissible_vector().tolist(), 0.1])

    @pytest.mark.unit
    def test_a_modflow_value_outside_its_bound_is_not_admissible(self, catalog):
        space = decision_space(bounds={KH: (0.05, 0.5)}, modflow=catalog)

        assert space.is_admissible(np.append(admissible_vector(), 0.5))
        assert not space.is_admissible(np.append(admissible_vector(), 0.6))
        assert not space.is_admissible(np.append(admissible_vector(), np.nan))

    @pytest.mark.unit
    def test_the_weights_keep_their_positions_in_the_constraint(self, catalog):
        pytest.importorskip("scipy.optimize")
        space = decision_space(bounds={KH: (0.05, 0.5)}, modflow=catalog)

        coefficients = np.asarray(space.weights_constraint().A)

        assert coefficients.tolist() == [[0, 0, 1, 1, 0, 0, 0, 0, 0]]

    @pytest.mark.unit
    def test_the_eight_parameters_may_all_be_fixed_when_a_modflow_one_is_searched(self, catalog):
        every = {name: minimum for name, (minimum, _) in SETTINGS_BOUNDS.items()}
        every.pop(DERIVED_PARAMETER)
        every["w_1"], every["w_2"] = 0.5, 0.5

        space = decision_space(fixed=every, bounds={KH: (0.05, 0.5)}, modflow=catalog)

        assert space.free_names == (KH,)
        assert space.weights_constraint() is None

    @pytest.mark.unit
    def test_a_name_the_catalog_does_not_hold_names_the_known_ones(self, catalog):
        with pytest.raises(ValueError, match="modflow.layers.2.specific_yield") as failure:
            decision_space(bounds={"modflow.layers.2.specific_yield": (0.1, 0.2)}, modflow=catalog)

        for name in catalog.names:
            assert name in str(failure.value)

    @pytest.mark.unit
    @pytest.mark.parametrize("argument", ["fixed", "bounds"])
    def test_a_modflow_name_without_modflow_is_refused(self, argument):
        value = 0.2 if argument == "fixed" else (0.1, 0.3)

        with pytest.raises(ValueError, match="does not enable MODFLOW"):
            decision_space(**{argument: {SPECIFIC_YIELD: value}})

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("name", "override"),
        [
            (KH, (0.0, 0.5)),
            (KH, (-1.0, 0.5)),
            (KH, (0.5, 0.1)),
            (KH, (0.3, 0.3)),
            (KH, (0.1, float("inf"))),
            (KH, (float("nan"), 0.5)),
            (CONDUCTANCE, (0.0, 1.0)),
            (SPECIFIC_YIELD, (0.0, 0.3)),
            (SPECIFIC_YIELD, (0.1, 1.2)),
        ],
    )
    def test_a_bound_outside_the_domain_of_the_parameter_is_refused(self, catalog, name, override):
        with pytest.raises(ValueError, match=f"bound .* of '{name}'"):
            decision_space(bounds={name: override}, modflow=catalog)

    @pytest.mark.unit
    def test_a_specific_yield_may_be_searched_up_to_one(self, catalog):
        space = decision_space(bounds={SPECIFIC_YIELD: (0.5, 1.0)}, modflow=catalog)

        assert space.bounds[-1] == (0.5, 1.0)

    @pytest.mark.unit
    @pytest.mark.parametrize("override", [0.3, (0.3,), (0.1, 0.2, 0.3)])
    def test_a_modflow_bound_that_is_not_a_pair_is_refused(self, catalog, override):
        with pytest.raises(ValueError, match=r"must be a \(minimum, maximum\) pair"):
            decision_space(bounds={KH: override}, modflow=catalog)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("name", "value"),
        [(KH, 0.0), (CONDUCTANCE, -1.0), (SPECIFIC_YIELD, 1.5), (KH, float("nan"))],
    )
    def test_a_fixed_value_outside_the_domain_is_refused(self, catalog, name, value):
        with pytest.raises(ValueError, match=f"'{name}' cannot be fixed"):
            decision_space(fixed={name: value}, modflow=catalog)

    @pytest.mark.unit
    def test_a_modflow_name_both_fixed_and_bounded_is_refused(self, catalog):
        with pytest.raises(ValueError, match="nowhere to apply"):
            decision_space(fixed={KH: 0.2}, bounds={KH: (0.1, 0.3)}, modflow=catalog)
