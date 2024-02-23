import logging
import os
from typing import Optional, Union

from rubem.configuration.raster_map import RasterMap
from rubem.configuration.data_ranges_settings import DataRangesSettings
from rubem.validation.raster_map_validator import RasterMapValidator
from rubem.validation.raster_data_rules import RasterDataRules


class InputRasterFiles:
    """
    Represents a collection of input raster files used in RUBEM analysis.

    :param dem: Path to the DEM file (*.map format).
    :type dem: Union[str, bytes, os.PathLike]

    :param demtif: Path to the DEM file (*.tif format).
    :type demtif: Union[str, bytes, os.PathLike]

    :param clone: Path to the mask of catchment (clone) file.
    :type clone: Union[str, bytes, os.PathLike]

    :param ndvi_max: Path to the NDVI maximum file.
    :type ndvi_max: Union[str, bytes, os.PathLike]

    :param ndvi_min: Path to the NDVI minimum file.
    :type ndvi_min: Union[str, bytes, os.PathLike]

    :param soil: Path to the soil file.
    :type soil: Union[str, bytes, os.PathLike]

    :param sample_locations: Path to the stations locations (samples) file.
    :type sample_locations: Union[str, bytes, os.PathLike]

    :param ldd: Path to the Local Drain Direction (LDD) raster file.
    :type ldd: Union[str, bytes, os.PathLike], optional

    :param validate_input: If True, validates the input raster files. Defaults to `True`.
    :type validate_input: bool, optional

    :raises FileNotFoundError: If any of the input raster files does not exist.
    :raises ValueError: If any of the input raster files is empty or has an invalid extension.
    """

    def __init__(
        self,
        dem: Union[str, bytes, os.PathLike],
        demtif: Union[str, bytes, os.PathLike],
        clone: Union[str, bytes, os.PathLike],
        ndvi_max: Union[str, bytes, os.PathLike],
        ndvi_min: Union[str, bytes, os.PathLike],
        soil: Union[str, bytes, os.PathLike],
        sample_locations: Union[str, bytes, os.PathLike],
        ldd: Optional[Union[str, bytes, os.PathLike]] = None,
        validate_input: bool = True,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.__ranges = DataRangesSettings()

        self.dem = dem
        self.demtif = demtif
        self.clone = clone
        self.ndvi_max = ndvi_max
        self.ndvi_min = ndvi_min
        self.soil = soil
        self.sample_locations = sample_locations
        self.ldd = ldd if ldd else None

        if validate_input:
            self.__validate_files()
        else:
            self.logger.warning("Input raster files validation is disabled.")

    def __validate_files(self) -> None:
        files = [
            (
                self.dem,
                self.__ranges.rasters["dem"],
                RasterDataRules.FORBID_NO_DATA
                | RasterDataRules.FORBID_ALL_ZEROES
                | RasterDataRules.FORBID_ALL_ONES,
            ),
            (
                self.demtif,
                self.__ranges.rasters["dem"],
                RasterDataRules.FORBID_NO_DATA
                | RasterDataRules.FORBID_ALL_ZEROES
                | RasterDataRules.FORBID_ALL_ONES,
            ),
            (self.clone, self.__ranges.rasters["clone"], RasterDataRules.FORBID_ALL_ZEROES),
            (self.ndvi_max, self.__ranges.rasters["ndvi"], RasterDataRules.FORBID_NO_DATA),
            (self.ndvi_min, self.__ranges.rasters["ndvi"], RasterDataRules.FORBID_NO_DATA),
            (
                self.soil,
                self.__ranges.rasters["soil"],
                RasterDataRules.FORBID_NO_DATA | RasterDataRules.FORBID_ALL_ZEROES,
            ),
            (
                self.sample_locations,
                self.__ranges.rasters["sample_locations"],
                RasterDataRules.FORBID_ALL_ZEROES | RasterDataRules.FORBID_ALL_ONES,
            ),
        ]

        if self.ldd:
            files.append(
                (
                    self.ldd,
                    self.__ranges.rasters["ldd"],
                    RasterDataRules.FORBID_NO_DATA | RasterDataRules.FORBID_ALL_ONES,
                )
            )

        for file, valid_range, rules in files:
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
                print(
                    f"Raster file '{file}' violated {[str(error) for error in errors]} data rule(s)."
                )

    def __str__(self) -> str:
        return (
            f"DEM (PCRaster Map): {self.dem}\n"
            f"DEM (GeoTIFF Map): {self.demtif}\n"
            f"Mask of Catchment (Clone): {self.clone}\n"
            f"Local Drain Direction (LDD): {self.ldd if self.ldd else 'Not specified.'}\n"
            f"NDVI Max.: {self.ndvi_max}\n"
            f"NDVI Min.: {self.ndvi_min}\n"
            f"Soil: {self.soil}\n"
            f"Stations Locations (Samples): {self.sample_locations}"
        )
