import logging
import os
from typing import Optional, Union

from osgeo import gdal
from pcraster._pcraster import Field
from pcraster.framework import pcr2numpy

from ..configuration.output_format import OutputFileFormat
from ..configuration.output_raster_base import OutputRasterBase
from ._naming import output_raster_filename

logger = logging.getLogger(__name__)


def report(
    variable: Field,
    name: str,
    outpath: Union[str, bytes, os.PathLike],
    base_raster_info: OutputRasterBase,
    timestep: Optional[int] = None,
    file_format: OutputFileFormat = OutputFileFormat.GEOTIFF,
    no_data_value: float = -9999,
):
    """Storing map data to disk using GDAL

    :param variable: Variable containing the PCRaster map data
    :type variable: Field

    :param timestep: Current timestep. If set the filename will contain the timestep (dynamic mode). Default is ``None``.
    :type timestep: int, optional

    :param outpath: Path to store the output
    :type outpath: Union[str, bytes, os.PathLike]

    :param name: Name used as filename. Use a filename with less than eight characters and without extension. File extension will be added automatically.
    :type name: str

    :param file_format: Output file format. Default is ``OutputFileFormat.GEOTIFF``.
    :type file_format: OutputFileFormat, optional

    :param base_raster_info: Base raster information
    :type base_raster_info: OutputRasterBase

    :param no_data_value: No data value. Default is ``-9999``.
    :type no_data_value: float, optional

    :raises ValueError: If ``file_format`` is not ``OutputFileFormat.GEOTIFF``.
        PCRaster maps are written by the framework's own ``report``.
    """
    if file_format != OutputFileFormat.GEOTIFF:
        raise ValueError(f"Unsupported output file format: {file_format}")

    __report(
        variable=variable,
        timestep=timestep,
        outpath=outpath,
        name=name,
        driver_short_name="GTiff",
        extension="tif",
        base_raster_info=base_raster_info,
        no_data_value=no_data_value,
    )


def __report(
    variable: Field,
    outpath: Union[str, bytes, os.PathLike],
    name: str,
    driver_short_name: str,
    extension: str,
    base_raster_info: OutputRasterBase,
    timestep: Optional[int] = None,
    no_data_value: float = -9999,
):
    if timestep:
        filename = output_raster_filename(name, timestep, extension)
    else:
        filename = f"{name}.{extension}"
    out_tif = os.path.abspath(os.path.join(os.fsdecode(outpath), filename))

    gdal.UseExceptions()
    gdal.AllRegister()

    with gdal.GetDriverByName(driver_short_name).Create(
        out_tif,
        base_raster_info.cols,
        base_raster_info.rows,
        bands=1,
        eType=gdal.GDT_Float32,
        options=["COMPRESS=LZW"],
    ) as dataset:
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(no_data_value)
        band.WriteArray(pcr2numpy(variable, no_data_value))
        dataset.SetGeoTransform(base_raster_info.transformation)
