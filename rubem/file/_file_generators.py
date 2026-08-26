import logging
import os
from pathlib import Path

from osgeo import gdal
from pcraster import defined
from pcraster._pcraster import Field
from pcraster.framework import pcr2numpy

from ..configuration.output_format import OutputFileFormat
from ..configuration.output_raster_base import OutputRasterBase
from ..preprocessing._io import PreprocessingError, check_nodata_collision
from ._naming import output_raster_filename

logger = logging.getLogger(__name__)


def report(
    variable: Field,
    name: str,
    outpath: str | bytes | os.PathLike,
    base_raster_info: OutputRasterBase,
    timestep: int | None = None,
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
    :raises RuntimeError: If a valid cell of ``variable`` equals ``no_data_value``
        (it would be read back as missing), or if GDAL cannot write the file.
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
    outpath: str | bytes | os.PathLike,
    name: str,
    driver_short_name: str,
    extension: str,
    base_raster_info: OutputRasterBase,
    timestep: int | None = None,
    no_data_value: float = -9999,
):
    if timestep:
        filename = output_raster_filename(name, timestep, extension)
    else:
        filename = f"{name}.{extension}"
    out_tif = str((Path(os.fsdecode(outpath)) / filename).absolute())

    # The sentinel is written into the missing cells and declared as the
    # band's no-data value, so a valid cell holding that exact value (a
    # runoff of 0 with no_data_value 0) would be indistinguishable from a
    # missing one on read. Same policy as the preprocessing writers.
    array = pcr2numpy(variable, no_data_value)
    valid = pcr2numpy(defined(variable), 0).astype(bool)
    try:
        check_nodata_collision(array, valid, no_data_value, f"Could not write the raster {out_tif}")
    except PreprocessingError as e:
        raise RuntimeError(str(e)) from e

    gdal.UseExceptions()
    gdal.AllRegister()

    try:
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
            band.WriteArray(array)
            dataset.SetGeoTransform(base_raster_info.transformation)
            if base_raster_info.projection:
                dataset.SetProjection(base_raster_info.projection)
    except Exception as e:
        # A partially written file would pass for a result of the run.
        out_tif_path = Path(out_tif)
        if out_tif_path.is_symlink() or out_tif_path.exists():
            try:
                out_tif_path.unlink()
            except OSError as removal_error:
                logger.error("Could not remove the partial file %s: %s", out_tif, removal_error)
        raise RuntimeError(f"Could not write the raster {out_tif}: {e}") from e
