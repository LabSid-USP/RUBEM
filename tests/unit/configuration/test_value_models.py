import math
import sys
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from rubem.configuration.calibration_parameters import CalibrationParameters
from rubem.configuration.initial_soil_conditions import InitialSoilConditions
from rubem.configuration.model_constants import ModelConstants
from rubem.configuration.raster_grid_area import RasterGrid
from rubem.configuration.simulation_period import SimulationPeriod

CALIBRATION = dict(
    alpha=4.5, beta=0.5, w_1=0.4, w_2=0.3, w_3=0.3, rcd=5.0, f=0.5, alpha_gw=0.5, x=0.5
)
INITIAL = dict(
    initial_soil_moisture_content=0.5,
    initial_baseflow=10.0,
    baseflow_limit=5.0,
    initial_saturated_zone_storage=100.0,
)
CONSTANTS = dict(
    fraction_photo_active_radiation_max=0.95,
    fraction_photo_active_radiation_min=0.001,
    leaf_area_interception_max=12.0,
    impervious_area_interception=2.5,
)


class TestSimulationPeriod:
    @pytest.mark.unit
    def test_legacy_attribute_names_are_kept(self):
        period = SimulationPeriod(start=date(2000, 1, 1), end=date(2000, 12, 1))

        assert period.start_date == date(2000, 1, 1)
        assert period.end_date == date(2000, 12, 1)
        assert (period.first_step, period.last_step, period.total_steps) == (1, 12, 12)

    @pytest.mark.unit
    def test_attribute_names_are_accepted_as_keywords_too(self):
        period = SimulationPeriod(start_date=date(2000, 1, 1), end_date=date(2000, 3, 1))

        assert period.total_steps == 3

    @pytest.mark.unit
    def test_datetimes_are_accepted(self):
        period = SimulationPeriod(start=datetime(2000, 1, 1), end=datetime(2001, 1, 1))

        assert period.last_step == 13

    @pytest.mark.unit
    def test_alignment_shifts_the_step_numbers(self):
        period = SimulationPeriod(
            start=date(2000, 3, 1), end=date(2000, 5, 1), alignment=date(2000, 1, 1)
        )

        assert (period.first_step, period.last_step, period.total_steps) == (3, 5, 3)

    @pytest.mark.unit
    def test_validation_errors_are_value_errors(self):
        with pytest.raises(ValueError, match="must be before end date"):
            SimulationPeriod(start=date(2000, 2, 1), end=date(2000, 1, 1))
        with pytest.raises(ValidationError, match="must be before start date"):
            SimulationPeriod(
                start=date(2000, 1, 1), end=date(2000, 2, 1), alignment=date(2000, 3, 1)
            )

    @pytest.mark.unit
    def test_is_frozen_and_rejects_unknown_fields(self):
        period = SimulationPeriod(start=date(2000, 1, 1), end=date(2000, 2, 1))

        with pytest.raises(ValidationError):
            period.start_date = date(1999, 1, 1)
        with pytest.raises(ValidationError, match="extra"):
            SimulationPeriod(start=date(2000, 1, 1), end=date(2000, 2, 1), step=1)

    @pytest.mark.unit
    def test_str_keeps_the_legacy_format(self):
        assert str(SimulationPeriod(start=date(2000, 1, 1), end=date(2000, 2, 1))) == (
            "2000-01-01 to 2000-02-01"
        )

    @pytest.mark.unit
    def test_dump_includes_the_computed_steps(self):
        dumped = SimulationPeriod(start=date(2000, 1, 1), end=date(2000, 2, 1)).model_dump()

        assert dumped["first_step"] == 1 and dumped["last_step"] == 2 and dumped["total_steps"] == 2


class TestRasterGrid:
    @pytest.mark.unit
    def test_positional_and_keyword_construction(self):
        assert RasterGrid(500).area == 250000
        assert RasterGrid(size=500).area == 250000

    @pytest.mark.unit
    @pytest.mark.parametrize("size", [0, -1, math.inf, math.nan, sys.float_info.max, 1e200])
    def test_non_finite_or_non_positive_sizes_are_rejected(self, size):
        """``1e200`` is finite but its square is not."""
        with pytest.raises(ValueError, match="Invalid grid area"):
            RasterGrid(size)

    @pytest.mark.unit
    def test_str_reports_the_area(self):
        assert str(RasterGrid(2)) == "4.0 [m²]"


class TestCalibrationParameters:
    @pytest.mark.unit
    def test_valid_parameters_are_stored(self):
        parameters = CalibrationParameters(**CALIBRATION)

        assert parameters.alpha == 4.5 and parameters.w_3 == 0.3
        assert "Interception Parameter (alpha): 4.5 [-]" in str(parameters)

    @pytest.mark.unit
    def test_weights_must_add_up_to_one(self):
        with pytest.raises(ValueError, match="must be equal to 1.0"):
            CalibrationParameters(**{**CALIBRATION, "w_3": 0.4})

    @pytest.mark.unit
    @pytest.mark.parametrize("name, value", [("alpha", 0.001), ("rcd", 11), ("x", -0.1)])
    def test_out_of_range_values_name_the_parameter(self, name, value):
        with pytest.raises(ValueError, match=f"out of range: .*\\({name}\\)"):
            CalibrationParameters(**{**CALIBRATION, name: value})

    @pytest.mark.unit
    def test_is_frozen(self):
        parameters = CalibrationParameters(**CALIBRATION)

        with pytest.raises(ValidationError):
            parameters.alpha = 1.0


class TestInitialSoilConditions:
    @pytest.mark.unit
    def test_valid_conditions_are_stored(self):
        conditions = InitialSoilConditions(**INITIAL)

        assert conditions.baseflow_limit == 5.0
        assert "Baseflow Threshold: 5.0 [mm]" in str(conditions)

    @pytest.mark.unit
    def test_infinite_upper_bounds_accept_large_values(self):
        conditions = InitialSoilConditions(**{**INITIAL, "initial_baseflow": 1e12})

        assert conditions.initial_baseflow == 1e12

    @pytest.mark.unit
    def test_out_of_range_values_are_rejected(self):
        with pytest.raises(ValueError, match="Initial Soil Moisture Content"):
            InitialSoilConditions(**{**INITIAL, "initial_soil_moisture_content": 1.5})


class TestModelConstants:
    @pytest.mark.unit
    def test_valid_constants_are_stored(self):
        constants = ModelConstants(**CONSTANTS)

        assert constants.leaf_area_interception_max == 12.0
        assert "Max. Leaf Area Index (LAI): 12.0 [-]" in str(constants)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "fpar_min, fpar_max",
        [(0.5, 0.5), (0.6, 0.5), (0.0, 0.95), (0.001, 1.0)],
    )
    def test_fpar_bounds_must_be_strictly_ordered_inside_the_unit_interval(
        self, fpar_min, fpar_max
    ):
        with pytest.raises(ValueError, match="FPAR"):
            ModelConstants(
                **{
                    **CONSTANTS,
                    "fraction_photo_active_radiation_min": fpar_min,
                    "fraction_photo_active_radiation_max": fpar_max,
                }
            )

    @pytest.mark.unit
    def test_lai_max_must_be_positive(self):
        with pytest.raises(ValueError, match="lai_max"):
            ModelConstants(**{**CONSTANTS, "leaf_area_interception_max": 0.0})

    @pytest.mark.unit
    def test_out_of_range_interception_is_rejected(self):
        with pytest.raises(ValueError, match="i_imp"):
            ModelConstants(**{**CONSTANTS, "impervious_area_interception": 3.5})
