"""Content rules of the input rasters that the equations cannot tolerate.

Every check receives the band values and the no-data value read through
:class:`~rubem.configuration.raster_map.RasterMap` and returns a
:class:`~rubem.configuration._problems.Problem` when the rule is violated,
``None`` otherwise. Missing cells are ignored.
"""

import numpy as np

from ..configuration._problems import Problem

# GeoTIFF sample/zone rasters are rounded and cast to int32 by read_field; an id
# above this saturates to a negative value and silently merges with another id.
_INT32_MAX = np.iinfo(np.int32).max


def _valid(values: np.ndarray, no_data_value) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    mask = np.isfinite(array)
    if no_data_value is not None:
        mask &= array != no_data_value
    return array[mask]


def _blocking(description: str, reason: str, file) -> Problem:
    return Problem(
        description=description,
        reason=reason,
        implication="The simulation cannot run with this raster.",
        file=str(file),
        blocking=True,
    )


def check_positive(values, no_data_value, file, label: str) -> Problem | None:
    """Every valid cell must be greater than zero (``kp`` divides the evapotranspiration)."""
    valid = _valid(values, no_data_value)
    if valid.size and not (valid > 0).all():
        return _blocking(
            f"{label} raster has cells that are not positive.",
            f"Minimum value: {valid.min()}.",
            file,
        )
    return None


def check_below_one(values, no_data_value, file, label: str) -> Problem | None:
    """Every valid cell must be below one (the simple ratio divides by ``1 - NDVI``)."""
    valid = _valid(values, no_data_value)
    if valid.size and not (valid < 1).all():
        return _blocking(
            f"{label} raster has cells equal to or above 1.",
            f"Maximum value: {valid.max()}.",
            file,
        )
    return None


def check_extremes(
    minimum_values, minimum_no_data, maximum_values, maximum_no_data, file
) -> Problem | None:
    """``ndvi_max`` must exceed ``ndvi_min`` in every cell valid in both rasters."""
    minimum = np.asarray(minimum_values, dtype=float)
    maximum = np.asarray(maximum_values, dtype=float)
    if minimum.shape != maximum.shape:
        return _blocking(
            "NDVI extremes rasters have different shapes.",
            f"{minimum.shape} versus {maximum.shape}.",
            file,
        )
    mask = np.isfinite(minimum) & np.isfinite(maximum)
    if minimum_no_data is not None:
        mask &= minimum != minimum_no_data
    if maximum_no_data is not None:
        mask &= maximum != maximum_no_data
    if mask.any() and not (maximum[mask] > minimum[mask]).all():
        count = int((maximum[mask] <= minimum[mask]).sum())
        return _blocking(
            "NDVI maximum is not above NDVI minimum in every cell.",
            f"Cells with ndvi_max <= ndvi_min: {count}.",
            file,
        )
    return None


def _check_int32_range(ids: np.ndarray, file, label: str) -> Problem | None:
    """Identifiers above the int32 range saturate when a GeoTIFF is read as Nominal."""
    if ids.max() > _INT32_MAX:
        return _blocking(
            f"{label} identifiers must fit a 32-bit integer.",
            f"Maximum value: {int(ids.max())}; a GeoTIFF raster is read with identifiers cast "
            f"to int32 (max {_INT32_MAX}).",
            file,
        )
    return None


def check_sample_ids(values, no_data_value, file) -> Problem | None:
    """Sample identifiers must be positive integers ``1..N`` without gaps.

    Zero and missing cells are not samples; they are ignored.
    """
    valid = _valid(values, no_data_value)
    ids = valid[valid != 0]
    if ids.size == 0:
        return _blocking(
            "Sample locations raster has no sample.", "Every cell is 0 or missing.", file
        )
    if not np.all(np.equal(np.mod(ids, 1), 0)) or (ids < 0).any():
        return _blocking(
            "Sample identifiers must be positive integers.",
            f"Offending values: {sorted(set(ids[(ids < 0) | (np.mod(ids, 1) != 0)].tolist()))[:10]}.",
            file,
        )
    problem = _check_int32_range(ids, file, "Sample")
    if problem is not None:
        return problem
    unique = sorted(set(int(value) for value in ids))
    expected = list(range(1, len(unique) + 1))
    if unique != expected:
        return _blocking(
            "Sample identifiers must be contiguous from 1.",
            f"Found {unique}, expected {expected}.",
            file,
        )
    return None


def check_zone_ids(values, no_data_value, file) -> Problem | None:
    """Zone identifiers must be positive integers; at least one cell must belong to a zone.

    Gaps between identifiers are allowed: the run remaps them to ``1..N``.
    """
    valid = _valid(values, no_data_value)
    ids = valid[valid != 0]
    if ids.size == 0:
        return _blocking("Zones raster has no zone.", "Every cell is 0 or missing.", file)
    if not np.all(np.equal(np.mod(ids, 1), 0)) or (ids < 0).any():
        return _blocking(
            "Zone identifiers must be positive integers.",
            f"Offending values: {sorted(set(ids[(ids < 0) | (np.mod(ids, 1) != 0)].tolist()))[:10]}.",
            file,
        )
    return _check_int32_range(ids, file, "Zone")
