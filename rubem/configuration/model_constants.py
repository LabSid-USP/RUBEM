import logging
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from ._ranges import check_range

logger = logging.getLogger(__name__)


class ModelConstants(BaseModel):
    """Constants of the model.

    :param fraction_photo_active_radiation_max: Maximum fraction of photosynthetically active radiation [-].
    :param fraction_photo_active_radiation_min: Minimum fraction of photosynthetically active radiation [-].
    :param leaf_area_interception_max: Maximum leaf area index [-].
    :param impervious_area_interception: Impervious area interception [mm].

    :raises ValueError: If a value is outside the configured range, the FPAR bounds are not
        ``0 < min < max < 1``, or the maximum leaf area index is not positive.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fraction_photo_active_radiation_max: float
    fraction_photo_active_radiation_min: float
    leaf_area_interception_max: float
    impervious_area_interception: float

    @model_validator(mode="after")
    def _check_ranges(self) -> Self:
        fpar_max = self.fraction_photo_active_radiation_max
        fpar_min = self.fraction_photo_active_radiation_min
        check_range(
            "Max. Frac. Photosynthetically Active Radiation (fpar_max)",
            fpar_max,
            "fraction_photo_active_radiation",
        )
        check_range(
            "Min. Frac. Photosynthetically Active Radiation (fpar_min)",
            fpar_min,
            "fraction_photo_active_radiation",
        )
        if not 0 < fpar_min < fpar_max < 1:
            logger.error(
                "FPAR bounds must satisfy 0 < min < max < 1, got min=%f and max=%f.",
                fpar_min,
                fpar_max,
            )
            raise ValueError(
                f"Max. FPAR={fpar_max} must be greater than the Min. FPAR={fpar_min}, "
                "and both must lie strictly between 0 and 1."
            )
        check_range(
            "Max. Leaf Area Index (lai_max)",
            self.leaf_area_interception_max,
            "leaf_area_interception_max",
        )
        if self.leaf_area_interception_max <= 0:
            raise ValueError(
                f"Max. Leaf Area Index (lai_max)={self.leaf_area_interception_max} must be positive."
            )
        check_range(
            "Impervious Area Interception (i_imp)",
            self.impervious_area_interception,
            "impervious_area_interception",
        )
        return self

    def __str__(self) -> str:
        return (
            f"Max. Frac. Photosynthetically Active Radiation (FPAR): {self.fraction_photo_active_radiation_max} [-]\n"
            f"Min. Frac. Photosynthetically Active Radiation (FPAR): {self.fraction_photo_active_radiation_min} [-]\n"
            f"Max. Leaf Area Index (LAI): {self.leaf_area_interception_max} [-]\n"
            f"Impervious Area Interception: {self.impervious_area_interception} [mm]"
        )
