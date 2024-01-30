import logging

from rubem.configuration.data_ranges_settings import DataRangesSettings


class ModelConstants:
    """
    Class representing model constants used in RUBEM.

    :param fraction_photo_active_radiation_max: Maximum fraction of photosynthetically active radiation (FPAR) [-].
    :type fraction_photo_active_radiation_max: float

    :param fraction_photo_active_radiation_min: Minimum fraction of photosynthetically active radiation (FPAR) [-].
    :type fraction_photo_active_radiation_min: float

    :param leaf_area_interception_max: Maximum leaf area index (LAI) [-].
    :type leaf_area_interception_max: float

    :param impervious_area_interception: Impervious area interception [mm].
    :type impervious_area_interception: float

    :raises ValueError: If any of the input parameter values are out of range.
    """

    def __init__(
        self,
        fraction_photo_active_radiation_max: float,
        fraction_photo_active_radiation_min: float,
        leaf_area_interception_max: float,
        impervious_area_interception: float,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.__ranges = DataRangesSettings()

        self.__validate(
            "Max. Frac. Photosynthetically Active Radiation (fpar_max)",
            fraction_photo_active_radiation_max,
            self.__ranges.variables["fraction_photo_active_radiation"],
        )
        self.__validate(
            "Min. Frac. Photosynthetically Active Radiation (fpar_min)",
            fraction_photo_active_radiation_min,
            self.__ranges.variables["fraction_photo_active_radiation"],
        )

        if fraction_photo_active_radiation_max < fraction_photo_active_radiation_min:
            self.logger.error(
                "Max. FPAR=%f must be greater than the Min. FPAR=%f.",
                fraction_photo_active_radiation_max,
                fraction_photo_active_radiation_min,
            )
            raise ValueError(
                f"Max. FPAR={fraction_photo_active_radiation_max} must be greater than the Min. FPAR={fraction_photo_active_radiation_min}."
            )

        self.__validate(
            "Max. Leaf Area Index (lai_max)",
            leaf_area_interception_max,
            self.__ranges.variables["leaf_area_interception_max"],
        )
        self.__validate(
            "Impervious Area Interception (i_imp)",
            impervious_area_interception,
            self.__ranges.variables["impervious_area_interception"],
        )

        self.fraction_photo_active_radiation_max = fraction_photo_active_radiation_max
        self.fraction_photo_active_radiation_min = fraction_photo_active_radiation_min
        self.leaf_area_interception_max = leaf_area_interception_max
        self.impervious_area_interception = impervious_area_interception

    def __validate(self, parameter_name, parameter_value, valid_range):
        min_value = valid_range["min"]
        max_value = valid_range["max"]
        if not min_value <= parameter_value <= max_value:
            raise ValueError(
                f"Parameter value out of range: {parameter_name}={parameter_value} [{min_value}, {max_value}]."
            )

    def __str__(self):
        return (
            f"Max. Frac. Photosynthetically Active Radiation (FPAR): {self.fraction_photo_active_radiation_max} [-]\n"
            f"Min. Frac. Photosynthetically Active Radiation (FPAR): {self.fraction_photo_active_radiation_min} [-]\n"
            f"Max. Leaf Area Index (LAI): {self.leaf_area_interception_max} [-]\n"
            f"Impervious Area Interception: {self.impervious_area_interception} [mm]"
        )
