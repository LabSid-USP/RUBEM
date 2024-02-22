import logging
import os
from typing import Union
import re

from rubem.configuration.raster_map import RasterMap
from rubem.configuration.data_ranges_settings import DataRangesSettings
from rubem.validation.raster_map_validator import RasterMapValidator
from rubem.validation.raster_data_rules import RasterDataRules

RASTER_SERIES_FILENAME_MAX_CHARS = 8
RASTER_SERIES_FILENAME_EXTENSION_NUM_DIGITS = 3


class InputRasterSeries:
    """
    Represents a set of input data directories and their corresponding filenames prefixes for raster files from its series.

    :param etp: Path to the directory containing ETP (Evapotranspiration) data.
    :type etp: Union[str, bytes, os.PathLike]

    :param etp_filename_prefix: Prefix for the ETP (Evapotranspiration) data filenames.
    :type etp_filename_prefix: str

    :param precipitation: Path to the directory containing precipitation data.
    :type precipitation: Union[str, bytes, os.PathLike]

    :param precipitation_filename_prefix: Prefix for the precipitation data filenames.
    :type precipitation_filename_prefix: str

    :param ndvi: Path to the directory containing NDVI (Normalized Difference Vegetation Index) data.
    :type ndvi: Union[str, bytes, os.PathLike]

    :param ndvi_filename_prefix: Prefix for the NDVI (Normalized Difference Vegetation Index) data filenames.
    :type ndvi_filename_prefix: str

    :param kp: Path to the directory containing KP (Crop Coefficient) data.
    :type kp: Union[str, bytes, os.PathLike]

    :param kp_filename_prefix: Prefix for the KP (Crop Coefficient) data filenames.
    :type kp_filename_prefix: str

    :param landuse: Path to the directory containing land use data.
    :type landuse: Union[str, bytes, os.PathLike]

    :param landuse_filename_prefix: Prefix for the land use data filenames.
    :type landuse_filename_prefix: str

    :param validate_input: If True, validates the input data directories and their corresponding filenames prefixes for raster files from its series. Defaults to `True`.
    :type validate_input: bool, optional

    :raises NotADirectoryError: If any of the input data directories does not exist.
    :raises ValueError: If any of the input data directories is empty or if any of the input data directories contains files with invalid extensions.
    :raises FileNotFoundError: If any of the input data directories does not contain files with the specified prefix.
    """

    def __init__(
        self,
        etp: Union[str, bytes, os.PathLike],
        etp_filename_prefix: str,
        precipitation: Union[str, bytes, os.PathLike],
        precipitation_filename_prefix: str,
        ndvi: Union[str, bytes, os.PathLike],
        ndvi_filename_prefix: str,
        kp: Union[str, bytes, os.PathLike],
        kp_filename_prefix: str,
        landuse: Union[str, bytes, os.PathLike],
        landuse_filename_prefix: str,
        validate_input: bool = True,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.__ranges = DataRangesSettings()

        self.__etp_dir_path = etp
        self.__etp_filename_prefix = etp_filename_prefix
        self.__precipitation_dir_path = precipitation
        self.__precipitation_filename_prefix = precipitation_filename_prefix
        self.__ndvi_dir_path = ndvi
        self.__ndvi_filename_prefix = ndvi_filename_prefix
        self.__kp_dir_path = kp
        self.__kp_filename_prefix = kp_filename_prefix
        self.__landuse_dir_path = landuse
        self.__landuse_filename_prefix = landuse_filename_prefix

        if validate_input:
            self.__validate_directories()
        else:
            self.logger.warning("Input data directories validation is disabled.")

        self.etp = os.path.join(str(self.__etp_dir_path), self.__etp_filename_prefix)
        self.precipitation = os.path.join(
            str(self.__precipitation_dir_path), self.__precipitation_filename_prefix
        )
        self.ndvi = os.path.join(str(self.__ndvi_dir_path), self.__ndvi_filename_prefix)
        self.kp = os.path.join(str(self.__kp_dir_path), self.__kp_filename_prefix)
        self.landuse = os.path.join(str(self.__landuse_dir_path), self.__landuse_filename_prefix)

    def __validate_directories(self) -> None:
        directories = [
            (
                self.__etp_dir_path,
                self.__etp_filename_prefix,
                self.__ranges.rasters["etp"],
                RasterDataRules.FORBID_NO_DATA,
            ),
            (
                self.__precipitation_dir_path,
                self.__precipitation_filename_prefix,
                self.__ranges.rasters["precipitation"],
                RasterDataRules.FORBID_NO_DATA,
            ),
            (
                self.__ndvi_dir_path,
                self.__ndvi_filename_prefix,
                self.__ranges.rasters["ndvi"],
                RasterDataRules.FORBID_NO_DATA,
            ),
            (
                self.__kp_dir_path,
                self.__kp_filename_prefix,
                self.__ranges.rasters["kp"],
                RasterDataRules.FORBID_NO_DATA,
            ),
            (
                self.__landuse_dir_path,
                self.__landuse_filename_prefix,
                self.__ranges.rasters["landuse"],
                RasterDataRules.FORBID_NO_DATA | RasterDataRules.FORBID_ALL_ZEROES,
            ),
        ]

        total_num_files = []
        for directory, prefix, valid_range, rules in directories:
            if not os.path.isdir(directory):
                raise NotADirectoryError(f"Invalid input data directory: {directory}")

            if not os.listdir(directory):
                raise ValueError(f"Empty input data directory: {directory}")

            self.__validate_raster_series_filenames_prefixes(prefix)
            total_num_files.append(
                self.__validate_files_with_prefix(directory, prefix, valid_range, rules)
            )

        common_total_num_files = set(total_num_files)
        if len(common_total_num_files) > 1:
            self.logger.warning(
                "Number of files in one or more input data directories is different. "
                "This may lead to unexpected results."
            )

    def __validate_files_with_prefix(self, directory, prefix, valid_range, rules) -> int:
        num_digits = RASTER_SERIES_FILENAME_MAX_CHARS - len(prefix)
        regex_pattern = rf"^{prefix}[0-9]{{{num_digits}}}\.[0-9]{{{RASTER_SERIES_FILENAME_EXTENSION_NUM_DIGITS}}}$"
        compiled_pattern = re.compile(regex_pattern, re.IGNORECASE)

        counter = 0
        with os.scandir(directory) as it:
            for entry in it:
                if entry.is_file() and compiled_pattern.match(entry.name):
                    self.__validate_raster_file(entry.path, valid_range, rules)
                    counter += 1

        if counter == 0:
            self.logger.error(
                "No files found with prefix '%s' in directory '%s'", prefix, directory
            )
            raise FileNotFoundError(
                f"No files found with prefix '{prefix}' in directory '{directory}'"
            )

        self.logger.info(
            "Found %d files with prefix '%s' in directory '%s'",
            counter,
            prefix,
            directory,
        )

        return counter

    def __validate_raster_file(self, file, valid_range, rules) -> None:
        raster = RasterMap(file, valid_range, rules)
        self.logger.debug(str(raster).replace("\n", ", "))

        validator = RasterMapValidator()
        valid, errors = validator.validate(raster)
        if not valid:
            self.logger.warning(
                "Raster file '%s' violated %s. This may lead to unexpected results.",
                file,
                errors,
            )
            print(f"Raster file '{file}' violated {[str(error) for error in errors]} data rule(s).")

    def __validate_raster_series_filenames_prefixes(self, prefix):
        num_digits = RASTER_SERIES_FILENAME_MAX_CHARS - len(prefix)
        if num_digits <= 0:
            raise ValueError("Prefix too long. Must be less than 8 characters.")

    def __str__(self) -> str:
        return (
            f"Potential Evapotranspiration (ETP): {self.__etp_dir_path} ({self.__etp_filename_prefix})\n"
            f"Rainfall: {self.__precipitation_dir_path} ({self.__precipitation_filename_prefix})\n"
            f"NDVI: {self.__ndvi_dir_path} ({self.__ndvi_filename_prefix})\n"
            f"Class A Pan Coefficient (Kp): {self.__kp_dir_path} ({self.__kp_filename_prefix})\n"
            f"Land Use: {self.__landuse_dir_path} ({self.__landuse_filename_prefix})"
        )
