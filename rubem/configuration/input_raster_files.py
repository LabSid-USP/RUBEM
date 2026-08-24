import logging
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator

from .._paths import as_path
from ..configuration._problems import Problem
from ..configuration._ranges import raster_ranges
from ..configuration.raster_map import RasterMap
from ..validation.raster_content import check_extremes, check_sample_ids
from ..validation.raster_data_rules import RasterDataRules
from ..validation.raster_map_validator import RasterMapValidator

logger = logging.getLogger(__name__)

REQUIRED_RASTERS = ("dem", "clone", "ndvi_max", "ndvi_min", "soil")
OPTIONAL_RASTERS = ("sample_locations", "ldd", "georeference")


class InputRasterFiles(BaseModel):
    """
    Represents a collection of input raster files used in RUBEM analysis.

    :param dem: Path to the DEM file (``*.map`` format).
    :param clone: Path to the mask of catchment (clone) file.
    :param ndvi_max: Path to the NDVI maximum file.
    :param ndvi_min: Path to the NDVI minimum file.
    :param soil: Path to the soil file.
    :param sample_locations: Path to the stations locations (samples) file. Specifies a nominal map with unique IDs for which sampling point(s) the time series(s) are required. Defaults to ``None``.
    :param ldd: Path to the Local Drain Direction (LDD) raster file. Defaults to ``None``.
    :param georeference: Path to a raster whose coordinate reference system is written to the output GeoTIFF series. Must share the DEM geometry. Defaults to ``None``.
    :param validate_input: If ``True``, validates the content of the input raster files. Defaults to ``True``.

    :raises FileNotFoundError: If any of the input raster files does not exist.
    :raises ValueError: If any of the input raster files is empty or has an invalid extension.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dem: str
    clone: str
    ndvi_max: str
    ndvi_min: str
    soil: str
    sample_locations: str | None = None
    ldd: str | None = None
    georeference: str | None = None
    validate_input: bool = Field(default=True, exclude=True, repr=False)

    _problems: list[Problem] = PrivateAttr(default_factory=list)

    @field_validator(*REQUIRED_RASTERS, mode="before")
    @classmethod
    def _normalise(cls, value):
        return str(as_path(value))

    @field_validator(*OPTIONAL_RASTERS, mode="before")
    @classmethod
    def _normalise_optional(cls, value):
        # An empty setting means "not specified", as in the legacy configuration files.
        if value is None or value == "" or value == b"":
            return None
        return str(as_path(value))

    @property
    def problems(self) -> list[Problem]:
        """Non-blocking data problems found while validating the rasters."""
        return self._problems

    @model_validator(mode="after")
    def _validate_files(self) -> Self:
        if not self.validate_input:
            logger.warning("Input raster files validation is disabled.")
            return self

        ranges = raster_ranges()
        files = [
            (
                self.dem,
                ranges["dem"],
                RasterDataRules.FORBID_NO_DATA
                | RasterDataRules.FORBID_ALL_ZEROES
                | RasterDataRules.FORBID_ALL_ONES,
            ),
            (self.clone, ranges["clone"], RasterDataRules.FORBID_ALL_ZEROES),
            (self.ndvi_max, ranges["ndvi"], RasterDataRules.FORBID_NO_DATA),
            (self.ndvi_min, ranges["ndvi"], RasterDataRules.FORBID_NO_DATA),
            (
                self.soil,
                ranges["soil"],
                RasterDataRules.FORBID_NO_DATA | RasterDataRules.FORBID_ALL_ZEROES,
            ),
        ]
        if self.sample_locations:
            files.append(
                (
                    self.sample_locations,
                    ranges["sample_locations"],
                    RasterDataRules.FORBID_ALL_ZEROES | RasterDataRules.FORBID_ALL_ONES,
                )
            )
        if self.ldd:
            files.append(
                (
                    self.ldd,
                    ranges["ldd"],
                    RasterDataRules.FORBID_NO_DATA | RasterDataRules.FORBID_ALL_ONES,
                )
            )

        problems = []
        bands = {}
        for file, valid_range, rules in files:
            with RasterMap(file, valid_range, rules) as raster:
                logger.debug(str(raster).replace("\n", ", "))
                valid, errors = RasterMapValidator().validate(raster)
                if file in (self.ndvi_min, self.ndvi_max, self.sample_locations):
                    band = raster.bands[0]
                    bands[file] = (band.data_array.copy(), band.no_data_value)
            if not valid:
                problems.append(
                    Problem(
                        description="Raster file data validation failed.",
                        reason=f"Data rules violation(s): {[str(error) for error in errors]}.",
                        implication="This may lead to unexpected results.",
                        file=file,
                    )
                )
        minimum, minimum_no_data = bands[self.ndvi_min]
        maximum, maximum_no_data = bands[self.ndvi_max]
        problem = check_extremes(minimum, minimum_no_data, maximum, maximum_no_data, self.ndvi_max)
        if problem is not None:
            problems.append(problem)
        if self.sample_locations:
            values, no_data = bands[self.sample_locations]
            problem = check_sample_ids(values, no_data, self.sample_locations)
            if problem is not None:
                problems.append(problem)

        self._problems = problems
        return self

    def __str__(self) -> str:
        return (
            f"DEM (PCRaster Map): {self.dem}\n"
            f"Mask of Catchment (Clone): {self.clone}\n"
            f"Local Drain Direction (LDD): {self.ldd if self.ldd else 'Not specified.'}\n"
            f"Georeference: {self.georeference if self.georeference else 'Not specified.'}\n"
            f"NDVI Max.: {self.ndvi_max}\n"
            f"NDVI Min.: {self.ndvi_min}\n"
            f"Soil: {self.soil}\n"
            f"Stations Locations (Samples): {self.sample_locations if self.sample_locations else 'Not specified.'}"
        )
