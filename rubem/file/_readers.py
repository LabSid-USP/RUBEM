"""Reading input rasters as PCRaster fields, from PCRaster maps or GeoTIFF files.

PCRaster maps are read by PCRaster itself. GeoTIFF files (``.tif``/``.tiff``)
are read through GDAL into an array and turned into a field of the requested
value scale on the current clone; their geometry must equal the clone's, and
their no-data cells become missing values. The clone itself may be a GeoTIFF:
its geometry is applied through the numeric ``setclone`` overload, which needs
square cells and no rotation.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path

import numpy as np

from .._paths import PathInput, as_path

logger = logging.getLogger(__name__)

GEOTIFF_SUFFIXES = (".tif", ".tiff")


class FieldScale(StrEnum):
    """Value scale a GeoTIFF input is converted to."""

    SCALAR = "scalar"
    NOMINAL = "nominal"
    BOOLEAN = "boolean"
    LDD = "ldd"


def is_geotiff(path: PathInput) -> bool:
    return as_path(path).suffix.lower() in GEOTIFF_SUFFIXES


def set_clone(path: PathInput) -> None:
    """Make ``path`` the PCRaster clone (a map, or a GeoTIFF through its geometry).

    :raises ValueError: If a GeoTIFF clone has rotated or non-square cells.
    """
    import pcraster as pcr

    file = as_path(path)
    if not is_geotiff(file):
        pcr.setclone(str(file))
        return
    from ..configuration.output_raster_base import read_raster_geometry

    cols, rows, (west, cell, rotation_x, north, rotation_y, cell_y), _ = read_raster_geometry(file)
    if rotation_x != 0 or rotation_y != 0:
        raise ValueError(
            f"The clone {file} is rotated or sheared; PCRaster grids are north-up only."
        )
    if abs(abs(cell_y) - abs(cell)) > 1e-9 * max(1.0, abs(cell)):
        raise ValueError(f"The clone {file} has non-square cells ({cell} x {cell_y}).")
    pcr.setclone(rows, cols, abs(cell), west, north)


def read_field(path: PathInput, scale: FieldScale):
    """Read a raster as a PCRaster field on the current clone.

    :raises RuntimeError: If PCRaster cannot read a map.
    :raises ValueError: If a GeoTIFF does not match the clone geometry.
    """
    import pcraster as pcr
    import pcraster.framework as pcrfw

    file = as_path(path)
    if not is_geotiff(file):
        return pcrfw.readmap(str(file))
    from ..preprocessing._io import read_raster

    data = read_raster(file)
    clone_rows, clone_cols = pcr.clone().nrRows(), pcr.clone().nrCols()
    if (data.rows, data.cols) != (clone_rows, clone_cols):
        raise ValueError(
            f"{file} has {data.cols}x{data.rows} cells, the clone has {clone_cols}x{clone_rows}."
        )
    clone_west, clone_north, clone_cell = (
        pcr.clone().west(),
        pcr.clone().north(),
        pcr.clone().cellSize(),
    )
    west, cell, _, north, _, _ = data.geotransform
    tolerance = 1e-9 * max(1.0, abs(clone_cell))
    if (
        data.is_rotated
        or abs(west - clone_west) > tolerance
        or abs(north - clone_north) > tolerance
        or abs(cell - clone_cell) > tolerance
    ):
        raise ValueError(
            f"{file} does not share the clone geometry (west {west}, north {north}, cell {cell}; "
            f"clone west {clone_west}, north {clone_north}, cell {clone_cell})."
        )
    mask = data.mask()
    if scale is FieldScale.SCALAR:
        array = np.where(mask, data.array, -9999.0).astype(np.float64)
        return pcr.numpy2pcr(pcr.Scalar, array, -9999.0)
    values = np.where(mask, np.rint(np.asarray(data.array, dtype=np.float64)), -9999).astype(
        np.int32
    )
    if scale is FieldScale.NOMINAL:
        return pcr.numpy2pcr(pcr.Nominal, values, -9999)
    if scale is FieldScale.BOOLEAN:
        return pcr.numpy2pcr(pcr.Boolean, np.where(mask, values != 0, 0).astype(np.uint8), 0)
    return pcr.ldd(pcr.numpy2pcr(pcr.Nominal, values, -9999))


def raster_format(path: PathInput) -> str:
    """``"geotiff"`` or ``"map"``."""
    return "geotiff" if is_geotiff(path) else "map"


def geotiff_series_member(directory: PathInput, prefix: str, step: int) -> Path | None:
    """The GeoTIFF member of a series for ``step``, if one exists (``.tif`` or ``.tiff``)."""
    from ._naming import output_raster_filename

    base = as_path(directory)
    for suffix in GEOTIFF_SUFFIXES:
        candidate = base / output_raster_filename(prefix, step, suffix[1:])
        if candidate.is_file():
            return candidate
    return None
