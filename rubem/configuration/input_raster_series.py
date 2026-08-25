import logging
from pathlib import Path
from typing import Self

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

from .._paths import as_path
from ..configuration._problems import Problem
from ..configuration.data_ranges_settings import DataRangesSettings
from ..configuration.raster_map import RasterMap
from ..file._naming import RASTER_SERIES_BASENAME_LENGTH, raster_series_pattern
from ..validation.raster_data_rules import RasterDataRules
from ..validation.raster_map_validator import RasterMapValidator

RASTER_SERIES_FILENAME_MAX_CHARS = RASTER_SERIES_BASENAME_LENGTH

logger = logging.getLogger(__name__)

SERIES = ("etp", "precipitation", "ndvi", "kp", "landuse")


class InputRasterSeries(BaseModel):
    """
    Represents a set of input data directories and their corresponding filenames prefixes for raster files from its series.

    The directories are given with the series names (``etp``, ``precipitation``,
    ``ndvi``, ``kp``, ``landuse``); the attributes of the same names hold the
    absolute directory-plus-prefix paths the model reads its series from.

    :param etp: Path to the directory containing ETP (Evapotranspiration) data.
    :param etp_filename_prefix: Prefix for the ETP (Evapotranspiration) data filenames.
    :param precipitation: Path to the directory containing precipitation data.
    :param precipitation_filename_prefix: Prefix for the precipitation data filenames.
    :param ndvi: Path to the directory containing NDVI (Normalized Difference Vegetation Index) data.
    :param ndvi_filename_prefix: Prefix for the NDVI (Normalized Difference Vegetation Index) data filenames.
    :param kp: Path to the directory containing KP (Crop Coefficient) data.
    :param kp_filename_prefix: Prefix for the KP (Crop Coefficient) data filenames.
    :param landuse: Path to the directory containing land use data.
    :param landuse_filename_prefix: Prefix for the land use data filenames.
    :param validate_input: If ``True``, validates the directories and the content of their raster files. Defaults to ``True``.

    :raises NotADirectoryError: If any of the input data directories does not exist.
    :raises ValueError: If any of the input data directories is empty, or a prefix is too long.
    :raises FileNotFoundError: If any of the input data directories does not contain files with the specified prefix.
    """

    model_config = ConfigDict(
        frozen=True, extra="forbid", validate_by_name=True, validate_by_alias=True
    )

    etp_directory: str = Field(validation_alias=AliasChoices("etp", "etp_directory"))
    etp_filename_prefix: str
    precipitation_directory: str = Field(
        validation_alias=AliasChoices("precipitation", "precipitation_directory")
    )
    precipitation_filename_prefix: str
    ndvi_directory: str = Field(validation_alias=AliasChoices("ndvi", "ndvi_directory"))
    ndvi_filename_prefix: str
    kp_directory: str = Field(validation_alias=AliasChoices("kp", "kp_directory"))
    kp_filename_prefix: str
    landuse_directory: str = Field(validation_alias=AliasChoices("landuse", "landuse_directory"))
    landuse_filename_prefix: str
    validate_input: bool = Field(default=True, exclude=True, repr=False)

    _problems: list[Problem] = PrivateAttr(default_factory=list)

    @field_validator(*(f"{name}_directory" for name in SERIES), mode="before")
    @classmethod
    def _normalise(cls, value):
        return str(as_path(value))

    @field_validator(*(f"{name}_filename_prefix" for name in SERIES))
    @classmethod
    def _check_prefix(cls, value: str) -> str:
        if RASTER_SERIES_FILENAME_MAX_CHARS - len(value) <= 0:
            raise ValueError("Prefix too long. Must be less than 8 characters.")
        return value

    @property
    def problems(self) -> list[Problem]:
        """Non-blocking data problems found while validating the series."""
        return self._problems

    def __series_path(self, name: str) -> str:
        directory = getattr(self, f"{name}_directory")
        prefix = getattr(self, f"{name}_filename_prefix")
        return str((Path(directory) / prefix).absolute())

    @property
    def etp(self) -> str:
        """Absolute path of the ETP series (directory joined with the prefix)."""
        return self.__series_path("etp")

    @property
    def precipitation(self) -> str:
        """Absolute path of the precipitation series."""
        return self.__series_path("precipitation")

    @property
    def ndvi(self) -> str:
        """Absolute path of the NDVI series."""
        return self.__series_path("ndvi")

    @property
    def kp(self) -> str:
        """Absolute path of the Kp series."""
        return self.__series_path("kp")

    @property
    def landuse(self) -> str:
        """Absolute path of the land use series."""
        return self.__series_path("landuse")

    @model_validator(mode="after")
    def _validate_directories(self) -> Self:
        if not self.validate_input:
            logger.warning("Input data directories validation is disabled.")
            return self

        ranges = DataRangesSettings().rasters
        rules = {
            "etp": RasterDataRules.FORBID_NO_DATA,
            "precipitation": RasterDataRules.FORBID_NO_DATA,
            "ndvi": RasterDataRules.FORBID_NO_DATA,
            "kp": RasterDataRules.FORBID_NO_DATA,
            "landuse": RasterDataRules.FORBID_NO_DATA | RasterDataRules.FORBID_ALL_ZEROES,
        }

        problems = []
        total_num_files = []
        for name in SERIES:
            directory = Path(getattr(self, f"{name}_directory"))
            prefix = getattr(self, f"{name}_filename_prefix")
            if not directory.is_dir():
                raise NotADirectoryError(f"Invalid input data directory: {directory}")
            if not any(directory.iterdir()):
                raise ValueError(f"Empty input data directory: {directory}")
            total_num_files.append(
                self.__validate_files_with_prefix(
                    directory, prefix, ranges[name], rules[name], problems
                )
            )

        if len(set(total_num_files)) > 1:
            logger.warning(
                "Number of files in one or more input data directories is different. "
                "This may lead to unexpected results."
            )
        self._problems = problems
        return self

    @staticmethod
    def __validate_files_with_prefix(directory, prefix, valid_range, rules, problems) -> int:
        compiled_pattern = raster_series_pattern(prefix)

        counter = 0
        for entry in directory.iterdir():
            if entry.is_file() and compiled_pattern.match(entry.name):
                InputRasterSeries.__validate_raster_file(str(entry), valid_range, rules, problems)
                counter += 1

        if counter == 0:
            logger.error("No files found with prefix '%s' in directory '%s'", prefix, directory)
            raise FileNotFoundError(
                f"No files found with prefix '{prefix}' in directory '{directory}'"
            )

        logger.info("Found %d files with prefix '%s' in directory '%s'", counter, prefix, directory)
        return counter

    @staticmethod
    def __validate_raster_file(file, valid_range, rules, problems) -> None:
        with RasterMap(file, valid_range, rules) as raster:
            logger.debug(str(raster).replace("\n", ", "))
            valid, errors = RasterMapValidator().validate(raster)
        if not valid:
            problems.append(
                Problem(
                    description="Raster file data validation failed.",
                    reason=f"Data rules violation(s): {[str(error) for error in errors]}",
                    implication="This may lead to unexpected results.",
                    file=file,
                )
            )

    def __str__(self) -> str:
        return (
            f"Potential Evapotranspiration (ETP): {self.etp_directory} ({self.etp_filename_prefix})\n"
            f"Rainfall: {self.precipitation_directory} ({self.precipitation_filename_prefix})\n"
            f"NDVI: {self.ndvi_directory} ({self.ndvi_filename_prefix})\n"
            f"Class A Pan Coefficient (Kp): {self.kp_directory} ({self.kp_filename_prefix})\n"
            f"Land Use: {self.landuse_directory} ({self.landuse_filename_prefix})"
        )
