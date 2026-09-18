"""Class A pan coefficient (kp) series from wind speed and relative humidity rasters.

The coefficient follows equation S29 of the supplementary document (PDF page
9), evaluated by :func:`rubem.hydrological_processes._pan_coefficient.pan_coefficient`,
the implementation the model's
:meth:`~rubem.hydrological_processes.Evapotranspiration.get_pan_coef_et_open_water_area`
also uses::

    kp = 0.482 + 0.024 ln(B) - 0.000376 U2 + 0.0045 UR

The wind speed (U2, at 2 m above the ground) is given in m/s, the relative
humidity (UR) in %, and the fetch distance (B, the Class A pan border width)
in meters, either as one value for the whole grid or as a raster.

The two input series are members of the same grid, in the same order (natural
order of their file names): the nth wind speed raster is paired with the nth
relative humidity raster. One member of the ``kp`` series is written per pair,
named like the members the other series tools write.

The model refuses a ``kp`` raster with a cell that is not positive (it divides
the potential evapotranspiration), so every member is evaluated and checked
before anything is written: a run that would produce a cell where ``kp <= 0``
writes no member at all and reports every offending member. Two other rules the
model only reports, without refusing to run, are warned about here as well: a
cell above the maximum of the ``kp`` input range, and a cell missing in an
input and therefore in the member.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterator, Sequence
from enum import StrEnum
from pathlib import Path

import numpy as np

from .._paths import PathInput, as_path
from ..file._naming import get_raster_series_filepath, output_raster_filename
from ..hydrological_processes._pan_coefficient import (
    RECOMMENDED_FETCH_DISTANCE_RANGE,
    pan_coefficient,
)
from ._io import (
    PreprocessingError,
    RasterData,
    ValueScale,
    check_nodata_collision,
    check_not_manifest,
    check_same_geometry,
    dtype_for_nodata,
    read_raster,
    remove_stale_manifest,
    write_geotiff,
    write_manifest,
    write_pcraster_map,
)
from .minmax_series import series_files

logger = logging.getLogger(__name__)

LABEL = "kp"


class OutputFormat(StrEnum):
    """File format of the ``kp`` series members."""

    MAP = "map"
    TIF = "tif"


def kp_series(
    wind_inputs: Sequence[PathInput],
    humidity_inputs: Sequence[PathInput],
    output_dir: PathInput,
    prefix: str,
    fetch_distance: float | None = None,
    fetch_raster: PathInput | None = None,
    output_format: OutputFormat = OutputFormat.MAP,
    first_step: int = 1,
    nodata: float = -9999.0,
) -> list[Path]:
    """Write the Class A pan coefficient series of two input series.

    :param wind_inputs: Wind speed at 2 m [m/s] GeoTIFF files, or directories of them.
    :param humidity_inputs: Relative humidity [%] GeoTIFF files, or directories of them.
    :param output_dir: Where the members and ``manifest.csv`` are written.
    :param prefix: Series prefix, as in the other series tools.
    :param fetch_distance: Class A pan border width (B) [m] for the whole grid;
        give this or ``fetch_raster``, not both.
    :param fetch_raster: Raster of the Class A pan border width (B) [m], on the
        geometry of the series.
    :param output_format: ``map`` for PCRaster maps (the format the model
        reads), ``tif`` for GeoTIFF files.
    :param first_step: Step number of the first member.
    :param nodata: Missing value of the members; a cell missing in the wind
        speed, the relative humidity or the fetch raster is missing in ``kp``.
    :raises PreprocessingError: If the series have different numbers of
        members, if a raster does not share the geometry of the first wind
        speed raster, if neither or both fetch inputs are given, if the fetch
        distance is not positive, if a member would be written over one of
        the inputs, or if a member would carry a cell where ``kp`` is not
        positive or not finite.
    :return: The members written, in order.
    """
    wind_files = _series(wind_inputs, "The wind speed series")
    humidity_files = _series(humidity_inputs, "The relative humidity series")
    if len(wind_files) != len(humidity_files):
        raise PreprocessingError(
            f"{LABEL}: the series must have the same number of members, got "
            f"{len(wind_files)} wind speed raster(s) and "
            f"{len(humidity_files)} relative humidity raster(s)."
        )
    destination = as_path(output_dir)
    for file in (*wind_files, *humidity_files, fetch_raster):
        check_not_manifest(file, destination, "The input")
    fetch = _fetch_source(fetch_distance, fetch_raster)
    pairs = list(zip(wind_files, humidity_files))
    targets = [
        _target(destination, prefix, first_step + index, output_format)
        for index in range(len(pairs))
    ]
    _check_targets_are_not_inputs(
        targets, (*wind_files, *humidity_files, *([fetch_raster] if fetch_raster else []))
    )

    dtype = dtype_for_nodata(np.dtype(np.float32), nodata)
    maximum = _reported_maximum()
    failures: list[tuple[str, int]] = []
    for target, (wind, _humidity, kp, valid, _reference) in zip(targets, _evaluate(pairs, fetch)):
        offending = int(np.count_nonzero(valid & ~(np.isfinite(kp) & (kp > 0))))
        if offending:
            failures.append((wind.source, offending))
            continue
        above = int(np.count_nonzero(valid & (kp > maximum)))
        if above:
            logger.warning(
                "%s: %d cell(s) of %s are above %s, the maximum of the kp input range; the "
                "model reports such a member without refusing to run.",
                LABEL,
                above,
                target.name,
                maximum,
            )
        check_nodata_collision(
            _member_array(kp, valid, nodata, dtype), valid, nodata, f"{LABEL} {target.name}"
        )
        if not valid.all():
            logger.warning(
                "%s: %d cell(s) are missing in an input, so they are missing in %s; the model "
                "reports a kp member with missing cells.",
                LABEL,
                int(np.count_nonzero(~valid)),
                target.name,
            )
    if failures:
        detail = "; ".join(f"{source}: {count} cell(s)" for source, count in failures)
        raise PreprocessingError(
            f"{LABEL}: the pan coefficient must be positive and finite in every valid cell, "
            f"as the model refuses a kp raster that is not positive, but it is not in {detail}. "
            "Check the units of the inputs (wind speed at 2 m in m/s, relative humidity in %, "
            "fetch distance in m). No member was written."
        )

    remove_stale_manifest(destination)
    written: list[Path] = []
    manifest: list[tuple[str, str]] = []
    for target, (wind, humidity, kp, valid, reference) in zip(targets, _evaluate(pairs, fetch)):
        _write_member(
            target, _member_array(kp, valid, nodata, dtype), reference, output_format, nodata
        )
        logger.info("Wrote %s", target)
        written.append(target)
        manifest.extend([(wind.source, str(target)), (humidity.source, str(target))])
    write_manifest(destination, manifest)
    return written


def _reported_maximum() -> float:
    """The upper bound of the ``kp`` input range, above which the model reports a member."""
    from ..configuration._ranges import raster_range

    return float(raster_range("kp")["max"])


def _check_targets_are_not_inputs(targets: Sequence[Path], inputs: Sequence[PathInput]) -> None:
    """Refuse a run whose members would be written over its own inputs.

    The series is read twice, once to check every member and once to write it,
    so a member written over an input would change what the second pass reads.
    """
    sources = {as_path(file).resolve() for file in inputs}
    clashing = [target for target in targets if target.resolve() in sources]
    if clashing:
        raise PreprocessingError(
            f"{LABEL}: {clashing[0]} is both an input of the series and a member that would be "
            "written there; choose another output directory, prefix or format."
        )


def _series(inputs: Sequence[PathInput], label: str) -> list[Path]:
    """The members of one input series, in natural order."""
    try:
        return series_files(inputs)
    except PreprocessingError as e:
        raise PreprocessingError(f"{label}: {e}") from e


def _fetch_source(
    fetch_distance: float | None, fetch_raster: PathInput | None
) -> float | RasterData:
    """The fetch distance as a number or as a raster, whichever was given."""
    if (fetch_distance is None) == (fetch_raster is None):
        raise PreprocessingError(
            f"{LABEL}: give the fetch distance either as a value in meters or as a raster, "
            "not as neither or both."
        )
    low, high = RECOMMENDED_FETCH_DISTANCE_RANGE
    if fetch_raster is not None:
        data = read_raster(fetch_raster)
        values = np.asarray(data.array, dtype=np.float64)[data.mask()]
        if values.size and not (values > 0).all():
            raise PreprocessingError(
                f"{LABEL}: {int(np.count_nonzero(values <= 0))} cell(s) of {data.source} are not "
                "a positive fetch distance; the logarithm of the formula needs B > 0."
            )
        if values.size and (values.min() < low or values.max() > high):
            logger.warning(
                "The fetch distances of %s run from %s to %s m, outside the %s to %s m of the "
                "Class A pan the formula was fitted for.",
                data.source,
                values.min(),
                values.max(),
                low,
                high,
            )
        return data
    distance = float(fetch_distance)
    if not math.isfinite(distance) or distance <= 0:
        raise PreprocessingError(
            f"{LABEL}: the fetch distance must be a positive number of meters, got {fetch_distance}."
        )
    if not low <= distance <= high:
        logger.warning(
            "A fetch distance of %s m is outside the %s to %s m of the Class A pan the "
            "formula was fitted for.",
            distance,
            low,
            high,
        )
    return distance


def _target(directory: Path, prefix: str, step: int, output_format: OutputFormat) -> Path:
    """The path of one member, named as the other series tools name theirs."""
    if output_format is OutputFormat.TIF:
        return (directory / output_raster_filename(prefix, step, "tif")).absolute()
    return Path(get_raster_series_filepath(directory, prefix, step))


def _evaluate(
    pairs: Sequence[tuple[Path, Path]], fetch: float | RasterData
) -> Iterator[tuple[RasterData, RasterData, np.ndarray, np.ndarray, RasterData]]:
    """Yield ``(wind, humidity, kp, valid, reference)`` for every pair of the series.

    Every raster must share the geometry of the first wind speed raster, which
    is the reference of the whole run. A cell missing in any input is missing
    in ``kp``; its value in the yielded array is arbitrary but finite.
    """
    reference: RasterData | None = None
    for wind_file, humidity_file in pairs:
        wind = read_raster(wind_file)
        humidity = read_raster(humidity_file)
        if reference is None:
            reference = wind
            if isinstance(fetch, RasterData):
                check_same_geometry(reference, fetch, LABEL)
        check_same_geometry(reference, wind, LABEL)
        check_same_geometry(reference, humidity, LABEL)
        valid = wind.mask() & humidity.mask()
        if isinstance(fetch, RasterData):
            valid &= fetch.mask()
        distance = (
            np.where(valid, np.asarray(fetch.array, dtype=np.float64), 1.0)
            if isinstance(fetch, RasterData)
            else fetch
        )
        kp = pan_coefficient(
            distance,
            np.where(valid, np.asarray(wind.array, dtype=np.float64), 0.0),
            np.where(valid, np.asarray(humidity.array, dtype=np.float64), 0.0),
            log=np.log,
        )
        yield wind, humidity, np.asarray(kp, dtype=np.float64), valid, reference


def _member_array(kp: np.ndarray, valid: np.ndarray, nodata: float, dtype: np.dtype) -> np.ndarray:
    """One member as it is written: ``nodata`` on the cells no input covered."""
    return np.where(valid, kp, nodata).astype(dtype)


def _write_member(
    target: Path,
    array: np.ndarray,
    reference: RasterData,
    output_format: OutputFormat,
    nodata: float,
) -> None:
    """Write one member, whose values the first pass already checked."""
    if output_format is OutputFormat.TIF:
        write_geotiff(target, array, reference.geotransform, reference.projection, nodata)
    else:
        write_pcraster_map(target, array, ValueScale.SCALAR, reference.geotransform, nodata)
