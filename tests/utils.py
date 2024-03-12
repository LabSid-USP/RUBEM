import os
from typing import Union

from osgeo import gdal
import numpy as np


def compare_rasters(
    raster1_path: Union[dict, str, bytes, os.PathLike],
    raster2_path: Union[dict, str, bytes, os.PathLike],
    tolerance: float = 1e-9,
) -> bool:
    """Compare two rasters for equality.

    :param raster1_path: The path to the first raster.
    :type raster1_path: Union[dict, str, bytes, os.PathLike]

    :param raster2_path: The path to the second raster.
    :type raster2_path: Union[dict, str, bytes, os.PathLike]

    :param tolerance: The tolerance for comparing the rasters, defaults to 1e-9.
    :type tolerance: float

    :return: True if the rasters are equal, False otherwise.
    :rtype: bool
    """

    if not raster1_path:
        raise ValueError("The first raster path is required.")

    if not raster2_path:
        raise ValueError("The second raster path is required.")

    if not os.path.exists(str(raster1_path)):
        raise FileNotFoundError(f"The first raster {raster1_path} does not exist.")

    if not os.path.exists(str(raster2_path)):
        raise FileNotFoundError(f"The second raster {raster2_path} does not exist.")

    raster1 = gdal.OpenEx(raster1_path, gdal.GA_ReadOnly)
    raster2 = gdal.OpenEx(raster2_path, gdal.GA_ReadOnly)

    if not raster1 or not raster2:
        return False

    bands1 = [raster1.GetRasterBand(i) for i in range(1, raster1.RasterCount + 1)]
    bands2 = [raster2.GetRasterBand(i) for i in range(1, raster2.RasterCount + 1)]

    if not bands1 or not bands2:
        return False

    if len(bands1) != len(bands2):
        return False

    for band1, band2 in zip(bands1, bands2):
        array1 = band1.ReadAsArray()
        array2 = band2.ReadAsArray()

        if array1.shape != array2.shape:
            return False

        if not np.isclose(array1, array2, atol=tolerance).all():
            return False

    raster1 = None
    raster2 = None
    bands1 = None
    bands2 = None

    return True


def compare_csv(
    csv1_path: Union[dict, str, bytes, os.PathLike],
    csv2_path: Union[dict, str, bytes, os.PathLike],
    delimiter: str = ";",
    tolerance: float = 1e-9,
) -> bool:
    """Compare two CSV files for equality.

    :param csv1_path: The path to the first CSV file.
    :type csv1_path: Union[dict, str, bytes, os.PathLike]

    :param csv2_path: The path to the second CSV file.
    :type csv2_path: Union[dict, str, bytes, os.PathLike]

    :param delimiter: The delimiter used in the CSV files, defaults to ";".
    :type delimiter: str

    :param tolerance: The tolerance for comparing the CSV files, defaults to 1e-9.
    :type tolerance: float

    :return: True if the CSV files are equal, False otherwise.
    :rtype: bool
    """

    if not csv1_path:
        raise ValueError("The first CSV path is required.")

    if not csv2_path:
        raise ValueError("The second CSV path is required.")

    if not os.path.exists(str(csv1_path)):
        raise FileNotFoundError(f"The first CSV file {csv1_path} does not exist.")

    if not os.path.exists(str(csv2_path)):
        raise FileNotFoundError(f"The second CSV file {csv2_path} does not exist.")

    data1 = np.genfromtxt(str(csv1_path), delimiter=delimiter, skip_header=1)
    data2 = np.genfromtxt(str(csv2_path), delimiter=delimiter, skip_header=1)

    if np.isclose(data1, data2, atol=tolerance).all():
        return True

    return False
