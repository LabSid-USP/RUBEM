import logging
import re
import os
from typing import Optional, Union

from osgeo import gdal
import numpy as np


class PCRasterMap:
    """
    Initialize a PCRasterMap object.

    :param file_path: The path to the raster file.
    :type file_path: Union[str, bytes, os.PathLike]

    :param valid_range: The valid range of values for the raster. Defaults to None.
    :type valid_range: Optional[dict[str, float]], optional

    :raises FileNotFoundError: If the raster file does not exist.
    :raises ValueError: If the raster file is empty or has an invalid extension.
    :raises IOError: If the raster file cannot be opened.
    """

    def __init__(
        self,
        file_path: Union[str, bytes, os.PathLike],
        valid_range: Optional[dict[str, float]] = None,
    ) -> None:
        self.logger = logging.getLogger(__name__)

        self.logger.debug("Opening raster file: %s", file_path)
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Invalid raster file: {file_path}")

        if os.path.getsize(file_path) <= 0:
            raise ValueError(f"Empty raster file: {file_path}")

        if not str(file_path).endswith((".map", ".tif")) and not bool(
            bool(re.search(r"\.[0-9]{3}$", str(os.path.splitext(file_path)[1])))
        ):
            raise ValueError(f"Invalid raster file extension: {file_path}")

        self.raster = gdal.Open(file_path)
        if self.raster is None:
            raise IOError(f"Unable to open raster file: {file_path}")

        self.logger.debug("Dimensions: %s", self.__check_dimensions(self.raster))
        self.logger.debug("Projection: %s", self.__check_projection(self.raster))
        self.logger.debug("Number of Bands: %s", self.raster.RasterCount)
        self.logger.debug("Driver: %s", self.raster.GetDriver().ShortName)
        self.logger.debug("Metadata: %s", self.raster.GetMetadata())
        self.logger.debug("GeoTransform: %s", self.raster.GetGeoTransform())
        self.logger.debug("GCPs: %s", self.raster.GetGCPs())
        self.logger.debug("Metadata Domain List: %s", self.raster.GetMetadataDomainList())

        self.raster_band = []
        for band in range(self.raster.RasterCount):
            band += 1
            self.logger.debug("Band: %s", band)
            self.raster_band.append(self.raster.GetRasterBand(band))
            if self.raster_band[band - 1] is None:
                raise IOError(f"Unable to open band {band} of raster file: {file_path}")

            self.logger.debug("Data Type: %s", self.__check_data_type(self.raster_band[band - 1]))
            self.logger.debug(
                "NoData Value: %s", self.__check_nodata_value(self.raster_band[band - 1])
            )
            self.logger.debug(
                "Statistics: %s", self.__compute_statistics(self.raster_band[band - 1])
            )

            if valid_range and not self.__check_value_consistency(
                self.raster_band[band - 1], valid_range["min"], valid_range["max"]
            ):
                raise ValueError(
                    f"Raster file {file_path} has values outside the range [{valid_range['min']}, {valid_range['max']}]"
                )

    def __check_dimensions(self, raster: gdal.Dataset) -> tuple[int, int]:
        """
        Check the dimensions of the raster.

        :param raster: The raster object.
        :type raster: gdal.Dataset

        :return: The number of columns and rows in the raster.
        :rtype: tuple[int, int]
        """
        cols = raster.RasterXSize
        rows = raster.RasterYSize
        return cols, rows

    def __check_data_type(self, band: gdal.Band) -> str:
        """
        Check the data type of the raster band.

        :param band: The raster band object.
        :type band: gdal.Band

        :return: The data type of the raster band.
        :rtype: str
        """
        return gdal.GetDataTypeName(band.DataType)

    def __check_nodata_value(self, band: gdal.Band) -> float:
        """
        Check the NoData value of the raster band.

        :param band: The raster band object.
        :type band: gdal.Band

        :return: The NoData value of the raster band.
        :rtype: float
        """
        return band.GetNoDataValue()

    def __compute_statistics(self, band: gdal.Band) -> tuple[float, float, float, float]:
        """
        Compute the statistics of the raster band.

        :param band: The raster band object.
        :type band: gdal.Band

        :return: The minimum, maximum, mean, and standard deviation of the raster band.
        :rtype: tuple[float, float, float, float]
        """
        return band.GetStatistics(True, True)

    def __check_projection(self, raster: gdal.Dataset) -> str:
        """
        Check the projection of the raster.

        :param raster: The raster object.
        :type raster: gdal.Dataset

        :return: The projection of the raster.
        :rtype: str
        """
        projection = raster.GetProjection()
        return projection

    def __check_value_consistency(
        self, band: gdal.Band, min_value: float, max_value: float
    ) -> bool:
        """
        Check if the values in the raster band are within the valid range.

        :param band: The raster band object.
        :type band: gdal.Band

        :param min_value: The minimum valid value.
        :type min_value: float

        :param max_value: The maximum valid value.
        :type max_value: float

        :return: True if all values are within the valid range, False otherwise.
        :rtype: bool
        """
        array = self.__get_array_without_no_data(band)
        return ((array >= min_value) & (array <= max_value)).all()

    def __get_array_without_no_data(self, band) -> np.ma.MaskedArray:
        """
        Get the array of the raster band without the NoData values.

        :param band: The raster band object.
        :type band: gdal.Band

        :return: The array of the raster band without the NoData values.
        :rtype: numpy.ma.MaskedArray
        """
        band.ComputeStatistics(0)
        nodata = band.GetNoDataValue()
        array = band.ReadAsArray()
        if nodata is not None:
            array = np.ma.masked_equal(array, nodata)
        return array
