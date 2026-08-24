import math
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from ._ranges import check_range


class CalibrationParameters(BaseModel):
    """Calibration parameters of the model.

    Every parameter must lie within the range configured in the application
    settings, and the land use, soil and slope factor weights must add up to 1.

    :param alpha: Interception parameter [-].
    :param beta: Rainfall intensity coefficient [-].
    :param w_1: Land use factor weight [-].
    :param w_2: Soil factor weight [-].
    :param w_3: Slope factor weight [-].
    :param rcd: Regional consecutive dryness level [mm].
    :param f: Flow direction factor [-].
    :param alpha_gw: Baseflow recession coefficient [-].
    :param x: Flow recession coefficient [-].

    :raises ValueError: If any parameter is out of range or the weights do not add up to 1.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    alpha: float
    beta: float
    w_1: float
    w_2: float
    w_3: float
    rcd: float
    f: float
    alpha_gw: float
    x: float

    @model_validator(mode="after")
    def _check_ranges(self) -> Self:
        check_range("Interception Parameter (alpha)", self.alpha, "alpha")
        check_range("Rainfall Intensity Coefficient (beta)", self.beta, "beta")
        check_range("Land Use Factor Weight (w_1)", self.w_1, "w_1")
        check_range("Soil Factor Weight (w_2)", self.w_2, "w_2")
        check_range("Slope Factor Weight (w_3)", self.w_3, "w_3")
        check_range("Regional Consecutive Dryness Level (rcd)", self.rcd, "rcd")
        check_range("Flow Direction Factor (f)", self.f, "f")
        check_range("Baseflow Recession Coefficient (alpha_gw)", self.alpha_gw, "alpha_gw")
        check_range("Flow Recession Coefficient (x)", self.x, "x")
        if not math.isclose(self.w_1 + self.w_2 + self.w_3, 1.0):
            raise ValueError(
                "The sum of landuse (w_1), soil (w_2) and slope (w_3) factor weights "
                "must be equal to 1.0."
            )
        return self

    def __str__(self) -> str:
        return (
            f"Interception Parameter (alpha): {self.alpha} [-]\n"
            f"Rainfall Intensity Coefficient (beta): {self.beta} [-]\n"
            f"Land Use Factor Weight (w_1): {self.w_1} [-]\n"
            f"Soil Factor Weight (w_2): {self.w_2} [-]\n"
            f"Slope Factor Weight (w_3): {self.w_3} [-]\n"
            f"Regional Consecutive Dryness Level (rcd): {self.rcd} [mm]\n"
            f"Flow Direction Factor (f): {self.f} [-]\n"
            f"Baseflow Recession Coefficient (alpha_gw): {self.alpha_gw} [-]\n"
            f"Flow Recession Coefficient (x): {self.x} [-]"
        )
