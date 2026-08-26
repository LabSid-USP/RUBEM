"""Content rules of the input rasters that the equations cannot tolerate.

Every check receives the band values and the no-data value read through
:class:`~rubem.configuration.raster_map.RasterMap` and returns a
:class:`~rubem.configuration._problems.Problem` when the rule is violated,
``None`` otherwise. Missing cells are ignored.
"""

import numpy as np

from ..configuration._problems import Problem

# Categorical GeoTIFF rasters (classes, identifiers, LDD codes) are cast to
# int32 by read_field, which refuses values the cast would alter; the same
# limits are reported here so that validation catches them first. The lowest
# int32 is PCRaster's own missing value on that scale. Plain integers: the
# documentation build mocks numpy, so no numpy call may run at import time.
_INT32_MAX = 2**31 - 1
_INT32_MIN = -(2**31) + 1


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
    """Values outside the int32 range cannot be read as classes from a GeoTIFF."""
    if ids.max() > _INT32_MAX or ids.min() < _INT32_MIN:
        return _blocking(
            f"{label} identifiers must fit a 32-bit integer.",
            f"Values range from {ids.min():.0f} to {ids.max():.0f}; a GeoTIFF raster is read "
            f"with the values cast to int32 ({_INT32_MIN}..{_INT32_MAX}).",
            file,
        )
    return None


def check_integer_values(values, no_data_value, file, label: str) -> Problem | None:
    """Every valid cell of a categorical raster must be an integer within the int32 range.

    Classes and codes are read from a GeoTIFF as int32; a fractional class
    would otherwise be rounded onto a neighbouring one.
    """
    valid = _valid(values, no_data_value)
    if valid.size == 0:
        return None
    fractional = valid[np.mod(valid, 1) != 0]
    if fractional.size:
        return _blocking(
            f"{label} raster has non-integer values.",
            f"Offending values: {sorted(set(fractional.tolist()))[:10]}.",
            file,
        )
    return _check_int32_range(valid, file, label)


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
