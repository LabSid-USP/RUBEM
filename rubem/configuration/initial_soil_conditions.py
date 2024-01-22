import logging
import sys


class InitialSoilConditions:
    """
    Represents a set of initial soil conditions.

    :param initial_soil_moisture_content: Initial Soil Moisture Content.
    :type initial_soil_moisture_content: float
    :param initial_baseflow: Initial Baseflow.
    :type initial_baseflow: float
    :param baseflow_limit: Baseflow Threshold.
    :type baseflow_limit: float
    :param initial_saturated_zone_storage: Initial Saturated Zone Storage.
    :type initial_saturated_zone_storage: float
    """

    def __init__(
        self,
        initial_soil_moisture_content: float,
        initial_baseflow: float,
        baseflow_limit: float,
        initial_saturated_zone_storage: float,
    ) -> None:
        self.logger = logging.getLogger(__name__)

        self.__validate(
            "Initial Soil Moisture Content (T_ini)",
            initial_soil_moisture_content,
            0.0,
            sys.float_info.max,
        )
        self.__validate("Initial Baseflow (bfw_ini)", initial_baseflow, 0.0, sys.float_info.max)
        self.__validate("Baseflow Threshold (bfw_lim)", baseflow_limit, 0.0, sys.float_info.max)
        self.__validate(
            "Initial Saturated Zone Storage (S_sat_ini)",
            initial_saturated_zone_storage,
            0.0,
            sys.float_info.max,
        )

        self.initial_soil_moisture_content = initial_soil_moisture_content
        self.initial_baseflow = initial_baseflow
        self.baseflow_limit = baseflow_limit
        self.initial_saturated_zone_storage = initial_saturated_zone_storage

    def __validate(self, parameter_name, parameter_value, min_value, max_value):
        if not min_value <= parameter_value <= max_value:
            raise ValueError(
                f"Parameter value out of range: {parameter_name}={parameter_value} [{min_value}, {max_value}]."
            )

    def __str__(self):
        return (
            f"Initial Soil Moisture Content: {self.initial_soil_moisture_content} [θ (cm³/cm³)]\n"
            f"Initial Baseflow: {self.initial_baseflow} [mm]\n"
            f"Baseflow Threshold: {self.baseflow_limit} [mm]\n"
            f"Initial Saturated Zone Storage: {self.initial_saturated_zone_storage} [mm]"
        )
