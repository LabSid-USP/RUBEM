from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from ._ranges import check_range


class InitialSoilConditions(BaseModel):
    """Initial soil conditions of the simulation.

    :param initial_soil_moisture_content: Initial soil moisture content, as a fraction of saturation [-].
    :param initial_baseflow: Initial baseflow [mm].
    :param baseflow_limit: Baseflow threshold [mm].
    :param initial_saturated_zone_storage: Initial saturated zone storage [mm].

    :raises ValueError: If any value is outside the range configured in the application settings.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    initial_soil_moisture_content: float
    initial_baseflow: float
    baseflow_limit: float
    initial_saturated_zone_storage: float

    @model_validator(mode="after")
    def _check_ranges(self) -> Self:
        check_range(
            "Initial Soil Moisture Content (T_ini)",
            self.initial_soil_moisture_content,
            "initial_soil_moisture_content",
        )
        check_range("Initial Baseflow (bfw_ini)", self.initial_baseflow, "baseflow")
        check_range("Baseflow Threshold (bfw_lim)", self.baseflow_limit, "baseflow")
        check_range(
            "Initial Saturated Zone Storage (S_sat_ini)",
            self.initial_saturated_zone_storage,
            "initial_saturated_zone_storage",
        )
        return self

    def __str__(self) -> str:
        return (
            f"Initial Soil Moisture Content: {self.initial_soil_moisture_content} [θ (cm³/cm³)]\n"
            f"Initial Baseflow: {self.initial_baseflow} [mm]\n"
            f"Baseflow Threshold: {self.baseflow_limit} [mm]\n"
            f"Initial Saturated Zone Storage: {self.initial_saturated_zone_storage} [mm]"
        )
