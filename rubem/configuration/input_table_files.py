import logging
import os
from typing import Union


class InputTableFiles:
    """
    Represents a collection of input lookup table files.

    This class is responsible for managing the input lookup table files used in the RUBEM model.
    It provides methods to validate the existence and non-zero size of the files, as well as a string representation
    of the file paths.

    :param rainy_days: Path to the rainy days lookup table file.
    :type rainy_days: Union[str, bytes, os.PathLike]

    :param a_i: Path to the impervious area fraction lookup table file.
    :type a_i: Union[str, bytes, os.PathLike]

    :param a_o: Path to the open water area fraction lookup table file.
    :type a_o: Union[str, bytes, os.PathLike]

    :param a_s: Path to the bare soil area fraction lookup table file.
    :type a_s: Union[str, bytes, os.PathLike]

    :param a_v: Path to the vegetated area fraction lookup table file.
    :type a_v: Union[str, bytes, os.PathLike]

    :param manning: Path to the Manning's roughness coefficient lookup table file.
    :type manning: Union[str, bytes, os.PathLike]

    :param bulk_density: Path to the bulk density lookup table file.
    :type bulk_density: Union[str, bytes, os.PathLike]

    :param k_sat: Path to the saturated hydraulic conductivity lookup table file.
    :type k_sat: Union[str, bytes, os.PathLike]

    :param t_fcap: Path to the field capacity lookup table file.
    :type t_fcap: Union[str, bytes, os.PathLike]

    :param t_sat: Path to the saturated content lookup table file.
    :type t_sat: Union[str, bytes, os.PathLike]

    :param t_wp: Path to the wilting point lookup table file.
    :type t_wp: Union[str, bytes, os.PathLike]

    :param rootzone_depth: Path to the rootzone depth lookup table file.
    :type rootzone_depth: Union[str, bytes, os.PathLike]

    :param kc_min: Path to the minimum crop coefficient lookup table file.
    :type kc_min: Union[str, bytes, os.PathLike]

    :param kc_max: Path to the maximum crop coefficient lookup table file.
    :type kc_max: Union[str, bytes, os.PathLike]

    :param validate_input: If True, validates the input lookup table files. Defaults to `True`.
    :type validate_input: bool, optional

    :raises FileNotFoundError: If any of the input lookup table files does not exist.
    :raises ValueError: If any of the input lookup table files is empty.
    """

    def __init__(
        self,
        rainy_days: Union[str, bytes, os.PathLike],
        a_i: Union[str, bytes, os.PathLike],
        a_o: Union[str, bytes, os.PathLike],
        a_s: Union[str, bytes, os.PathLike],
        a_v: Union[str, bytes, os.PathLike],
        manning: Union[str, bytes, os.PathLike],
        bulk_density: Union[str, bytes, os.PathLike],
        k_sat: Union[str, bytes, os.PathLike],
        t_fcap: Union[str, bytes, os.PathLike],
        t_sat: Union[str, bytes, os.PathLike],
        t_wp: Union[str, bytes, os.PathLike],
        rootzone_depth: Union[str, bytes, os.PathLike],
        kc_min: Union[str, bytes, os.PathLike],
        kc_max: Union[str, bytes, os.PathLike],
        validate_input: bool = True,
    ) -> None:
        self.logger = logging.getLogger(__name__)

        self.rainy_days = rainy_days
        self.a_i = a_i
        self.a_o = a_o
        self.a_s = a_s
        self.a_v = a_v
        self.manning = manning
        self.bulk_density = bulk_density
        self.k_sat = k_sat
        self.t_fcap = t_fcap
        self.t_sat = t_sat
        self.t_wp = t_wp
        self.rootzone_depth = rootzone_depth
        self.kc_min = kc_min
        self.kc_max = kc_max

        if validate_input:
            self.__validate_files()
        else:
            self.logger.warning("Input lookup table files validation is disabled.")

    def __validate_files(self) -> None:
        files = [
            self.rainy_days,
            self.a_i,
            self.a_o,
            self.a_s,
            self.a_v,
            self.manning,
            self.bulk_density,
            self.k_sat,
            self.t_fcap,
            self.t_sat,
            self.t_wp,
            self.rootzone_depth,
            self.kc_min,
            self.kc_max,
        ]

        for file in files:
            if not os.path.isfile(file):
                raise FileNotFoundError(f"Invalid input lookuptable file: {file}")

            if os.path.getsize(file) <= 0:
                raise ValueError(f"Empty input lookuptable file: {file}")

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
