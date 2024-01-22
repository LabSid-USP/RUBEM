import logging
import os
from typing import Union
from osgeo import gdal


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
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.dem = dem
        self.demtif = demtif
        self.clone = clone
        self.ndvi_max = ndvi_max
        self.ndvi_min = ndvi_min
        self.soil = soil
        self.sample_locations = sample_locations

        self.__validate_files()

    def __validate_files(self) -> None:
        files = [
            self.dem,
            self.demtif,
            self.clone,
            self.ndvi_max,
            self.ndvi_min,
            self.soil,
            self.sample_locations,
        ]

        for file in files:
            self.logger.debug("Validating input raster file: %s", file)
            if not os.path.isfile(file):
                raise FileNotFoundError(f"Invalid input raster file: {file}")

            if os.path.getsize(file) <= 0:
                raise ValueError(f"Empty input raster file: {file}")

            if not str(file).endswith((".map", ".tif")):
                raise ValueError(f"Invalid input raster file extension: {file}")

            raster = gdal.Open(file)
            if raster is None:
                raise IOError(f"Unable to open raster file: {file}")

            self.logger.debug("Dimensions: %s", self.__check_dimensions(raster))
            self.logger.debug("Projection: %s", self.__check_projection(raster))

            for band in range(raster.RasterCount):
                band += 1
                self.logger.debug("Band: %s", band)
                raster_band = raster.GetRasterBand(band)
                if raster_band is None:
                    raise IOError(f"Unable to open band {band} of raster file: {file}")

                self.logger.debug("Data Type: %s", self.__check_data_type(raster_band))
                self.logger.debug("NoData Value: %s", self.__check_nodata_value(raster_band))
                self.logger.debug("Statistics: %s", self.__compute_statistics(raster_band))
                raster_band = None

            raster = None

    def __check_dimensions(self, raster):
        cols = raster.RasterXSize
        rows = raster.RasterYSize
        return cols, rows

    def __check_data_type(self, band):
        return gdal.GetDataTypeName(band.DataType)

    def __check_nodata_value(self, band):
        return band.GetNoDataValue()

    def __compute_statistics(self, band):
        return band.GetStatistics(True, True)

    def __check_projection(self, raster):
        projection = raster.GetProjection()
        return projection

    def __check_value_consistency(self, band, min_value, max_value):
        array = band.ReadAsArray()
        return ((array >= min_value) & (array <= max_value)).all()

    def __str__(self) -> str:
        return (
            f"DEM (PCRaster Map): {self.dem}\n"
            f"DEM (GeoTIFF Map): {self.demtif}\n"
            f"Mask of Catchment (Clone): {self.clone}\n"
            f"NDVI Max.: {self.ndvi_max}\n"
            f"NDVI Min.: {self.ndvi_min}\n"
            f"Soil: {self.soil}\n"
            f"Stations Locations (Samples): {self.sample_locations}"
        )
