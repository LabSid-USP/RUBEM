import logging
import re
from pathlib import Path

from osgeo import gdal

from .._paths import PathInput, as_path
from ..validation.raster_data_rules import RasterDataRules


class RasterBand:
    """
    Initialize a RasterBand object.

    :param index: The index of the raster band.
    :type index: int

    :param band: The raster band object.
    :type band: gdal.Band

    :raises ValueError: If the raster band is empty or has an invalid data type.
    """

    def __init__(self, index: int, band: gdal.Band) -> None:
        self.logger = logging.getLogger(__name__)

        if band is None:
            raise ValueError("Invalid raster band")

        self.index = index
        self.band = band
        self.no_data_value = self.band.GetNoDataValue()
        try:
            self.band.ComputeStatistics(0)
            self.min, self.max, self.mean, self.std_dev = self.band.GetStatistics(True, True)
        except RuntimeError:
            # A band without a single valid pixel has no statistics; the data
            # rules report it, so the object must still be built.
            self.min = self.max = self.mean = self.std_dev = float("nan")
        self.data_type = gdal.GetDataTypeName(self.band.DataType)
        self.data_array = self.band.ReadAsArray()

    def __str__(self) -> str:
        return (
            f"Index: {self.index}, "
            f"Data Type: {self.data_type}, "
            f"NoData Value: {self.no_data_value}, "
            f"Statistics: Min: {self.min}, Max: {self.max}, Mean: {self.mean}, Std Dev: {self.std_dev}"
        )


class RasterMap:
    """
    Initialize a RasterMap object.

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
        file_path: PathInput,
        valid_range: dict[str, float] | None = None,
        rules: RasterDataRules | None = None,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        file_path = as_path(file_path)

        gdal.UseExceptions()
        gdal.AllRegister()

        self.logger.debug("Opening raster file: %s", file_path)

        self.__validate_file(file_path)
        self.__validate_file_extension(file_path)

        self.raster = gdal.OpenEx(str(file_path), gdal.GA_ReadOnly)

        self.valid_range = valid_range
        self.rules = rules

        self.bands = []
        for band_index in range(self.raster.RasterCount):
            band_index += 1
            band = RasterBand(band_index, self.raster.GetRasterBand(band_index))
            self.bands.append(band)

    def close(self) -> None:
        """Release the GDAL dataset and the band arrays."""
        self.bands = []
        self.raster = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def __validate_file(self, file_path):
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Invalid raster file: {file_path}")

        if path.stat().st_size <= 0:
            raise ValueError(f"Empty raster file: {file_path}")

    def __validate_file_extension(self, file_path):
        if not str(file_path).lower().endswith((".map", ".tif", ".tiff")) and not bool(
            bool(re.search(r"\.[0-9]{3}$", Path(file_path).suffix))
        ):
            raise ValueError(f"Invalid raster file extension: {file_path}")

    def __str__(self):
        if self.raster:
            return (
                f"Dimensions: {(self.raster.RasterXSize, self.raster.RasterYSize)}\n"
                f"Projection: {self.raster.GetProjection()}\n"
                f"Driver: {self.raster.GetDriver().ShortName}\n"
                f"Metadata: {self.raster.GetMetadata()}\n"
                f"GeoTransform: {self.raster.GetGeoTransform()}\n"
                f"GCPs: {self.raster.GetGCPs()}\n"
                f"Metadata Domain List: {self.raster.GetMetadataDomainList()}\n"
                f"Number of Bands: {self.raster.RasterCount}\n"
                f"Bands: {[str(band) for band in self.bands]}"
            )
        return "No raster file loaded"
