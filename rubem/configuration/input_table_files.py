import logging
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .._paths import as_path

logger = logging.getLogger(__name__)

TABLE_FIELDS = (
    "rainy_days",
    "a_i",
    "a_o",
    "a_s",
    "a_v",
    "manning",
    "bulk_density",
    "k_sat",
    "t_fcap",
    "t_sat",
    "t_wp",
    "rootzone_depth",
    "kc_min",
    "kc_max",
)


class InputTableFiles(BaseModel):
    """
    Represents the lookup table files used by the model.

    :param rainy_days: Path to the rainy days lookup table file.
    :param a_i: Path to the impervious area fraction lookup table file.
    :param a_o: Path to the open water area fraction lookup table file.
    :param a_s: Path to the bare soil area fraction lookup table file.
    :param a_v: Path to the vegetated area fraction lookup table file.
    :param manning: Path to the Manning's roughness coefficient lookup table file.
    :param bulk_density: Path to the bulk density lookup table file.
    :param k_sat: Path to the saturated hydraulic conductivity lookup table file.
    :param t_fcap: Path to the field capacity lookup table file.
    :param t_sat: Path to the saturated content lookup table file.
    :param t_wp: Path to the wilting point lookup table file.
    :param rootzone_depth: Path to the rootzone depth lookup table file.
    :param kc_min: Path to the minimum crop coefficient lookup table file.
    :param kc_max: Path to the maximum crop coefficient lookup table file.
    :param validate_input: If ``True``, checks that every file exists and is not empty. Defaults to ``True``.

    :raises FileNotFoundError: If any of the input lookup table files does not exist.
    :raises ValueError: If any of the input lookup table files is empty.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rainy_days: str
    a_i: str
    a_o: str
    a_s: str
    a_v: str
    manning: str
    bulk_density: str
    k_sat: str
    t_fcap: str
    t_sat: str
    t_wp: str
    rootzone_depth: str
    kc_min: str
    kc_max: str
    validate_input: bool = Field(default=True, exclude=True, repr=False)

    @field_validator(*TABLE_FIELDS, mode="before")
    @classmethod
    def _normalise(cls, value):
        return str(as_path(value))

    @model_validator(mode="after")
    def _validate_files(self) -> Self:
        if not self.validate_input:
            logger.warning("Input lookup table files validation is disabled.")
            return self
        for name in TABLE_FIELDS:
            file = Path(getattr(self, name))
            if not file.is_file():
                raise FileNotFoundError(f"Invalid input lookuptable file: {file}")
            if file.stat().st_size <= 0:
                raise ValueError(f"Empty input lookuptable file: {file}")
        return self

    def __str__(self) -> str:
        return (
            f"Rainy Days: {self.rainy_days}\n"
            f"Impervious Area Fraction (A_i): {self.a_i}\n"
            f"Open Water Area Fraction (A_o): {self.a_o}\n"
            f"Bare Soil Area Fraction (A_s): {self.a_s}\n"
            f"Vegetated Area Fraction (A_v): {self.a_v}\n"
            f"Manning's Roughness Coefficient: {self.manning}\n"
            f"Bulk Density: {self.bulk_density}\n"
            f"Saturated Hydraulic Conductivity (K_sat): {self.k_sat}\n"
            f"Field Capacity (T_fcap): {self.t_fcap}\n"
            f"Saturated Content (T_sat): {self.t_sat}\n"
            f"Wilting Point (T_wp): {self.t_wp}\n"
            f"Rootzone Depth: {self.rootzone_depth}\n"
            f"Min. Crop Coefficient (K_c_min): {self.kc_min}\n"
            f"Max. Crop Coefficient (K_c_max): {self.kc_max}"
        )
