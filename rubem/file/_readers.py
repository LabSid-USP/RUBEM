"""Reading input rasters as PCRaster fields, from PCRaster maps or GeoTIFF files.

PCRaster maps are read by PCRaster itself. GeoTIFF files (``.tif``/``.tiff``)
are read through GDAL into an array and turned into a field of the requested
value scale on the current clone; their geometry must equal the clone's, and
their no-data cells become missing values. The clone itself may be a GeoTIFF:
its geometry is applied through the numeric ``setclone`` overload, which needs
square, unrotated, north-up cells.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path

import numpy as np

from .._paths import PathInput, as_path

logger = logging.getLogger(__name__)

GEOTIFF_SUFFIXES = (".tif", ".tiff")

# Coordinate reference system of the raster last passed to :func:`set_clone`, empty
# when the clone carries none. Read-time checks in :func:`read_field` compare a
# GeoTIFF member's CRS against it, the same way the clone's geometry is compared
# through PCRaster's own global clone state.
_clone_projection = ""


class FieldScale(StrEnum):
    """Value scale a GeoTIFF input is converted to."""

    SCALAR = "scalar"
    NOMINAL = "nominal"
    BOOLEAN = "boolean"
    LDD = "ldd"


def is_geotiff(path: PathInput) -> bool:
    return as_path(path).suffix.lower() in GEOTIFF_SUFFIXES


def set_clone(path: PathInput, projection: str | None = None) -> None:
    """Make ``path`` the PCRaster clone (a map, or a GeoTIFF through its geometry).

    :param projection: Reference coordinate reference system recorded for the
        read-time checks in :func:`read_field` (see
        :func:`~rubem.configuration.output_raster_base.reference_crs`).
        Defaults to ``None``: the clone's own CRS, read from ``path`` itself
        -- empty for a PCRaster ``.map`` clone, which carries none.

    :raises ValueError: If a GeoTIFF clone is rotated, has non-square cells, or is
        not north-up.
    """
    import pcraster as pcr

    global _clone_projection

    file = as_path(path)
    from ..configuration.output_raster_base import read_raster_geometry

    if not is_geotiff(file):
        pcr.setclone(str(file))
        file_projection = read_raster_geometry(file)[3]
        _clone_projection = projection if projection is not None else file_projection
        return

    cols, rows, (west, cell, rotation_x, north, rotation_y, cell_y), file_projection = (
        read_raster_geometry(file)
    )
    if rotation_x != 0 or rotation_y != 0:
        raise ValueError(
            f"The clone {file} is rotated or sheared; PCRaster grids are north-up only."
        )
    if abs(abs(cell_y) - abs(cell)) > 1e-9 * max(1.0, abs(cell)):
        raise ValueError(f"The clone {file} has non-square cells ({cell} x {cell_y}).")
    if cell <= 0 or cell_y >= 0:
        raise ValueError(
            f"The clone {file} is not north-up; cell size must be positive in x and "
            f"negative in y (got {cell} x {cell_y})."
        )
    pcr.setclone(rows, cols, abs(cell), west, north)
    _clone_projection = projection if projection is not None else file_projection


# PCRaster's own missing value of the INT4 (nominal/ordinal/LDD) cell
# representation; the range check keeps every valid class above it, so it
# never collides with data the way a -9999 sentinel could.
_INT32_MISSING = int(np.iinfo(np.int32).min)
# PCRaster's own missing value of the UINT1 (boolean) cell representation.
_UINT8_MISSING = 255


def _check_integer_classes(valid_values: np.ndarray, file: Path, scale: FieldScale) -> None:
    """Categorical values are cast to int32 classes: refuse what the cast would alter.

    Rounding would turn 1.5 into class 2 and a value beyond the int32 range
    would wrap onto another class; both are silent data corruption.
    """
    if not valid_values.size:
        return
    fractional = valid_values[np.mod(valid_values, 1) != 0]
    if fractional.size:
        raise ValueError(
            f"{file} is read on the {scale.value} scale but holds non-integer values "
            f"(for example {fractional[0]!r})."
        )
    lowest, highest = float(valid_values.min()), float(valid_values.max())
    if lowest <= _INT32_MISSING or highest > np.iinfo(np.int32).max:
        raise ValueError(
            f"{file} holds values outside the 32-bit integer range of the {scale.value} scale "
            f"({_INT32_MISSING + 1}..{np.iinfo(np.int32).max}): {lowest:.0f}..{highest:.0f}."
        )


def read_field(path: PathInput, scale: FieldScale):
    """Read a raster as a PCRaster field on the current clone.

    :raises RuntimeError: If PCRaster cannot read a map.
    :raises ValueError: If a GeoTIFF does not match the clone geometry, or if
        a GeoTIFF read on a categorical scale (nominal, boolean, LDD) holds a
        non-integer value or one outside the 32-bit integer range.
    """
    import pcraster as pcr
    import pcraster.framework as pcrfw

    file = as_path(path)
    if not is_geotiff(file):
        value = pcrfw.readmap(str(file))
        return pcr.ldd(value) if scale is FieldScale.LDD else value
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
    west, cell, _, north, _, cell_y = data.geotransform
    tolerance = 1e-9 * max(1.0, abs(clone_cell))
    if (
        data.is_rotated
        or abs(west - clone_west) > tolerance
        or abs(north - clone_north) > tolerance
        or abs(cell - clone_cell) > tolerance
        or abs(cell_y - (-clone_cell)) > tolerance
    ):
        raise ValueError(
            f"{file} does not share the clone geometry (west {west}, north {north}, "
            f"cell {cell} x {cell_y}; clone west {clone_west}, north {clone_north}, "
            f"cell {clone_cell})."
        )
    if data.projection and _clone_projection:
        from ..configuration.output_raster_base import same_crs

        if not same_crs(data.projection, _clone_projection):
            raise ValueError(f"{file} does not share the clone coordinate reference system.")
    mask = data.mask()
    if scale is FieldScale.SCALAR:
        array = np.where(mask, data.array, -9999.0).astype(np.float64)
        return pcr.numpy2pcr(pcr.Scalar, array, -9999.0)
    floats = np.asarray(data.array, dtype=np.float64)
    _check_integer_classes(floats[mask], file, scale)
    values = np.where(mask, floats, _INT32_MISSING).astype(np.int32)
    if scale is FieldScale.NOMINAL:
        return pcr.numpy2pcr(pcr.Nominal, values, _INT32_MISSING)
    if scale is FieldScale.BOOLEAN:
        # A valid False cell is 0, so the missing marker cannot be 0 as well.
        flags = np.where(mask, values != 0, _UINT8_MISSING).astype(np.uint8)
        return pcr.numpy2pcr(pcr.Boolean, flags, _UINT8_MISSING)
    return pcr.ldd(pcr.numpy2pcr(pcr.Nominal, values, _INT32_MISSING))


def raster_format(path: PathInput) -> str:
    """``"geotiff"`` or ``"map"``."""
    return "geotiff" if is_geotiff(path) else "map"


def geotiff_series_member(directory: PathInput, prefix: str, step: int) -> Path | None:
    """The GeoTIFF member of a series for ``step``, if one exists (``.tif`` or ``.tiff``).

    Matching is case-insensitive, since :func:`~rubem.file._naming.geotiff_series_pattern`
    (used to detect the series format) already matches names regardless of case.

    :raises ValueError: If more than one file in the directory matches the member's
        name case-insensitively. On a case-sensitive file system two differently-cased
        names (``prec000001.tif`` and ``PREC000001.TIF``) are distinct files that would
        both be counted as the same step; which one is read must not silently depend on
        directory iteration order.
    """
    from ._naming import output_raster_filename

    base = as_path(directory)
    if not base.is_dir():
        return None
    lower_names = {
        output_raster_filename(prefix, step, suffix[1:]).lower() for suffix in GEOTIFF_SUFFIXES
    }
    matches = sorted(
        (
            entry
            for entry in base.iterdir()
            if entry.is_file() and entry.name.lower() in lower_names
        ),
        key=lambda entry: entry.name,
    )
    if len(matches) > 1:
        raise ValueError(
            f"Step {step} of the GeoTIFF series in {base} matches more than one file: "
            f"{', '.join(str(match) for match in matches)}."
        )
    return matches[0] if matches else None
