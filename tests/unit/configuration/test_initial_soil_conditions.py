import sys
import pytest

from rubem.configuration.initial_soil_conditions import InitialSoilConditions


class TestInitialSoilConditions:

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "initial_soil_moisture_content, baseflow_ini, baseflow_lim, initial_saturated_zone_storage",
        [
            (-0.01, 0.0, 0.0, 0.0),
            (0.0, -0.01, 0.0, 0.0),
            (0.0, 0.0, -0.01, 0.0),
            (0.0, 0.0, 0.0, -0.01),
            (1.01, 1.0, 1.0, 1.0),
        ],
    )
    def test_initial_soil_conditions_constructor_bad_args(
        self,
        initial_soil_moisture_content,
        baseflow_ini,
        baseflow_lim,
        initial_saturated_zone_storage,
    ):
        with pytest.raises(Exception):
            _ = InitialSoilConditions(
                initial_soil_moisture_content=initial_soil_moisture_content,
                initial_baseflow=baseflow_ini,
                baseflow_limit=baseflow_lim,
                initial_saturated_zone_storage=initial_saturated_zone_storage,
            )

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "initial_soil_moisture_content, baseflow_ini, baseflow_lim, initial_saturated_zone_storage",
        [
            (0.0, 0.0, 0.0, 0.0),
            (1.0, 1.0, 1.0, 1.0),
            (1.0, sys.float_info.max, 0.0, 0.0),
            (1.0, 0.0, sys.float_info.max, 0.0),
            (1.0, 0.0, 0.0, sys.float_info.max),
        ],
    )
    def test_initial_soil_conditions_constructor_good_args(
        self,
        initial_soil_moisture_content,
        baseflow_ini,
        baseflow_lim,
        initial_saturated_zone_storage,
    ):
        _ = InitialSoilConditions(
            initial_soil_moisture_content=initial_soil_moisture_content,
            initial_baseflow=baseflow_ini,
            baseflow_limit=baseflow_lim,
            initial_saturated_zone_storage=initial_saturated_zone_storage,
        )
