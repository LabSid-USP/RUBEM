"""Agreement between the declared grid cell size and the raster geometry.

``GRID.grid`` (``raster_info.grid_size`` in configuration format 1.0) is typed
by the user and gives the cell area that converts the accumulated runoff from
millimetres to cubic metres per second, so a wrong value scales the result
quadratically without any other symptom. When the reference coordinate
reference system is projected, the declared value can be compared with the
pixel size of the clone, once the linear unit of the system is converted to
metres. In geographic coordinates (the published basins are in degrees with a
nominal metric resolution), or without any coordinate reference system (a
PCRaster map carries none), no comparison is possible and the declared value is
kept as given.
"""

from __future__ import annotations

import logging

from osgeo import osr

from ..configuration._problems import Problem

logger = logging.getLogger(__name__)

#: Largest relative difference between the declared and the measured cell size
#: that is still considered a match.
TOLERANCE = 1e-6


def _spatial_reference(crs_wkt: str | None) -> osr.SpatialReference | None:
    """The coordinate reference system of ``crs_wkt``, or ``None`` when unusable."""
    if not crs_wkt:
        return None
    reference = osr.SpatialReference()
    if reference.ImportFromWkt(crs_wkt) != 0:
        return None
    return reference


def check_grid_cell_size(
    grid: float,
    pixel_width: float,
    pixel_height: float,
    crs_wkt: str | None,
    file,
) -> Problem | None:
    """Compare the declared cell size with the pixel size of a raster.

    The comparison only happens when ``crs_wkt`` describes a projected
    coordinate reference system: the pixel size is then converted to metres
    through the linear unit of the system and compared with ``grid``. A
    geographic system, an engineering (local) system and a raster without any
    coordinate reference system yield no problem; an informational message
    states the declared cell size and what the raster offers instead.

    :param grid: Cell size declared by the configuration, in metres.
    :param pixel_width: Pixel size along x, in the unit of the system (signed).
    :param pixel_height: Pixel size along y, in the unit of the system (signed).
    :param crs_wkt: The reference coordinate reference system as WKT, if any.
    :param file: The raster the geometry was read from, named by the problem.

    :return: A blocking :class:`~rubem.configuration._problems.Problem` when the
        relative difference of either axis exceeds ``TOLERANCE``, ``None``
        otherwise.
    """
    width = abs(float(pixel_width))
    height = abs(float(pixel_height))
    reference = _spatial_reference(crs_wkt)

    if reference is None or not reference.IsProjected():
        if reference is None:
            resolution = (
                f"the raster resolution is {width} x {height} in unknown units, since no "
                "coordinate reference system is available"
            )
        elif reference.IsGeographic():
            unit = reference.GetAngularUnitsName() or "angular unit"
            resolution = f"the raster resolution is {width} x {height} [{unit}]"
        else:
            resolution = (
                f"the coordinate reference system is not projected and the raster "
                f"resolution is {width} x {height}"
            )
        logger.info(
            "Grid cell size %s [m] not compared with %s: %s.",
            grid,
            file,
            resolution,
        )
        return None

    to_metres = reference.GetLinearUnits()
    unit = reference.GetLinearUnitsName() or "unknown unit"
    width_in_metres = width * to_metres
    height_in_metres = height * to_metres
    if all(abs(size - grid) / grid <= TOLERANCE for size in (width_in_metres, height_in_metres)):
        return None

    return Problem(
        description="Grid cell size does not match the raster.",
        reason=(
            f"The configuration declares {grid} [m], but the raster cell measures "
            f"{width} x {height} [{unit}], that is {width_in_metres} x {height_in_metres} [m]."
        ),
        implication=(
            "The cell area converts the accumulated runoff from mm to m³/s, so a wrong "
            "cell size scales it quadratically."
        ),
        file=str(file),
        blocking=True,
    )
