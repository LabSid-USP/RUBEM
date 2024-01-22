import logging
import math


class CalibrationParameters:
    """
    Represents a set of calibration parameters.

    :param alpha: Interception parameter.
    :type alpha: float
    :param beta: Rainfall Intensity parameter.
    :type beta: float
    :param w_1: Land Use Factor Weight.
    :type w_1: float
    :param w_2: Soil Factor Weight.
    :type w_2: float
    :param w_3: Slope Factor Weight.
    :type w_3: float
    :param rcd: Regional Consecutive Dryness Level
    :type rcd: float
    :param f: Flow Direction Factor.
    :type f: float
    :param alpha_gw: Baseflow Recession Coefficient.
    :type alpha_gw: float
    :param x: Flow Recession Coefficient.
    :type x: float
    """

    def __init__(
        self,
        alpha: float,
        beta: float,
        w_1: float,
        w_2: float,
        w_3: float,
        rcd: float,
        f: float,
        alpha_gw: float,
        x: float,
    ) -> None:
        self.logger = logging.getLogger(__name__)

        self.__validate("Interception Parameter (alpha)", alpha, 0.01, 10.0)
        self.__validate("Rainfall Intensity Coefficient (beta)", beta, 0.01, 1.0)
        self.__validate("Land Use Factor Weight (w_1)", w_1, 0.0, 1.0)
        self.__validate("Soil Factor Weight (w_2)", w_2, 0.0, 1.0)
        self.__validate("Slope Factor Weight (w_3)", w_3, 0.0, 1.0)
        self.__validate("Regional Consecutive Dryness Level (rcd)", rcd, 1.0, 10.0)
        self.__validate("Flow Direction Factor (f)", f, 0.01, 1.0)
        self.__validate("Baseflow Recession Coefficient (alpha_gw)", alpha_gw, 0.01, 1.0)
        self.__validate("Flow Recession Coefficient (x)", x, 0.0, 1.0)

        if not math.isclose(w_1 + w_2 + w_3, 1.0):
            raise ValueError(
                "The sum of landuse (w_1), soil (w_2) and slope (w_3) factor weights must be equal to 1."
            )

        self.alpha = alpha
        self.beta = beta
        self.w_1 = w_1
        self.w_2 = w_2
        self.w_3 = w_3
        self.rcd = rcd
        self.f = f
        self.alpha_gw = alpha_gw
        self.x = x

    def __validate(self, parameter_name, parameter_value, min_value, max_value):
        if not min_value <= parameter_value <= max_value:
            raise ValueError(
                f"Parameter value out of range: {parameter_name}={parameter_value} [{min_value}\n{max_value}]."
            )

    def __str__(self):
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
