"""Per-cell minimum and maximum over a series of rasters, ignoring missing cells."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from .._paths import PathInput, as_path
from ._io import (
    PreprocessingError,
    RasterData,
    check_nodata_collision,
    check_same_geometry,
    natural_sorted,
    read_raster,
    write_geotiff,
)
from .conversions import TIFF_SUFFIXES

logger = logging.getLogger(__name__)


def series_files(inputs: Sequence[PathInput]) -> list[Path]:
    """GeoTIFF files from files and directories, in natural order."""
    files: list[Path] = []
    for item in inputs:
        path = as_path(item)
        if path.is_dir():
            files.extend(
                natural_sorted(p for p in path.iterdir() if p.suffix.lower() in TIFF_SUFFIXES)
            )
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(f"Input not found: {path}")
    if not files:
        raise PreprocessingError("No raster in the series.")
    return files


def series_extremes(
    inputs: Sequence[PathInput], georeference: PathInput | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray, RasterData]:
    """Per-cell minimum and maximum of a raster series.

    Missing cells (the raster's no-data value or non-finite values) are
    ignored; a cell missing in every raster is missing in the result. Every
    raster must share the geometry of the first one (or of ``georeference``).

    :return: ``(minimum, maximum, valid, reference)`` where ``valid`` marks the
        cells with at least one value and ``reference`` carries the geometry
        (and the projection of ``georeference`` when given).
    """
    files = series_files(inputs)
    reference = read_raster(georeference) if georeference is not None else None
    minimum = maximum = valid = None
    for file in files:
        data = read_raster(file)
        if reference is None:
            reference = data
        else:
            check_same_geometry(reference, data, "minmax")
        mask = data.mask()
        values = np.asarray(data.array, dtype=np.float64)
        if minimum is None:
            minimum = np.where(mask, values, np.inf)
            maximum = np.where(mask, values, -np.inf)
            valid = mask.copy()
        else:
            minimum = np.where(mask, np.minimum(minimum, values), minimum)
            maximum = np.where(mask, np.maximum(maximum, values), maximum)
            valid |= mask
    logger.info("Computed the extremes of %d raster(s).", len(files))
    return minimum, maximum, valid, reference


def minmax(
    inputs: Sequence[PathInput],
    minimum_path: PathInput,
    maximum_path: PathInput,
    georeference: PathInput | None = None,
    nodata: float = -9999.0,
) -> tuple[Path, Path]:
    """Write the per-cell minimum and maximum of a raster series as GeoTIFF files.

    :raises PreprocessingError: If ``minimum_path`` and ``maximum_path`` resolve
        to the same file, or if a cell with at least one valid value already
        equals ``nodata`` in the minimum or the maximum.
    :return: The minimum and maximum files written.
    """
    minimum_target = as_path(minimum_path).resolve()
    maximum_target = as_path(maximum_path).resolve()
    if minimum_target == maximum_target:
        raise PreprocessingError(
            f"The minimum and maximum outputs would both be written to {minimum_target}."
        )
    minimum, maximum, valid, reference = series_extremes(inputs, georeference)
    minimum = np.where(valid, minimum, nodata).astype(np.float32)
    maximum = np.where(valid, maximum, nodata).astype(np.float32)
    check_nodata_collision(minimum, valid, nodata, "minmax minimum")
    check_nodata_collision(maximum, valid, nodata, "minmax maximum")
    written_min = write_geotiff(
        minimum_path, minimum, reference.geotransform, reference.projection, nodata
    )
    written_max = write_geotiff(
        maximum_path, maximum, reference.geotransform, reference.projection, nodata
    )
    logger.info("Wrote %s and %s", written_min, written_max)
    return written_min, written_max
