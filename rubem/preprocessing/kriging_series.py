"""Ordinary kriging of station series onto the clone grid, one map per step.

Two station file layouts are read. The legacy matrix layout has one row per
station: ``x;y;value_step1;value_step2;...``. The long layout has one row per
station and step: ``step;id;x;y;value``. Coordinates are given in the
coordinate reference system of the clone raster; the kriging distance metric
follows that system (geographic for a geographic CRS, euclidean for a
projected one, geographic when the clone has none, as the legacy script
assumed).
"""

from __future__ import annotations

import csv
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import numpy as np

from .._paths import PathInput, as_path
from ..file._naming import get_raster_series_filepath
from ._io import (
    PreprocessingError,
    ValueScale,
    check_nodata_collision,
    check_not_manifest,
    read_raster,
    remove_stale_manifest,
    write_manifest,
    write_pcraster_map,
)

logger = logging.getLogger(__name__)

MINIMUM_STATIONS = 3


class NegativePolicy(StrEnum):
    """What to do with negative interpolated values (the legacy script clamped)."""

    CLAMP = "clamp"
    KEEP = "keep"
    ERROR = "error"


class CoordinatesType(StrEnum):
    AUTO = "auto"
    GEOGRAPHIC = "geographic"
    EUCLIDEAN = "euclidean"


class StationsFormat(StrEnum):
    MATRIX = "matrix"
    LONG = "long"


class VariogramModel(StrEnum):
    """Variogram models both scikit-gstat and PyKrige fit with three parameters.

    scikit-gstat fits the empirical variogram (``psill``, ``range``, ``nugget``
    in that order); PyKrige's ``OrdinaryKriging`` accepts the same three for
    these models, in ``[psill, range, nugget]`` order. Other models either
    library offers (``linear``, ``power``, ``cubic``, ``stable``, ``matern``,
    ``hole-effect``, ...) are not supported by both with the same parameter
    count, so they are excluded here.
    """

    SPHERICAL = "spherical"
    EXPONENTIAL = "exponential"
    GAUSSIAN = "gaussian"


@dataclass(frozen=True)
class Stations:
    """Station coordinates and their values per step (``values[step_index, station]``)."""

    x: np.ndarray
    y: np.ndarray
    values: np.ndarray
    ids: tuple[str, ...]

    @property
    def steps(self) -> int:
        return int(self.values.shape[0])


def read_stations_matrix(path: PathInput, delimiter: str = ";") -> Stations:
    """Read the legacy layout: one row per station, ``x;y;v1;v2;...``."""
    file = as_path(path)
    rows = _read_rows(file, delimiter)
    parsed = []
    for number, row in rows:
        if len(row) < 3:
            raise PreprocessingError(f"{file}: line {number} needs x, y and at least one value.")
        try:
            values_row = [float(cell) for cell in row]
        except ValueError as e:
            raise PreprocessingError(f"{file}: line {number} has a non-numeric cell.") from e
        if not all(math.isfinite(v) for v in values_row):
            raise PreprocessingError(f"{file}: line {number} has a non-finite value.")
        parsed.append(values_row)
    widths = {len(row) for row in parsed}
    if len(widths) != 1:
        raise PreprocessingError(
            f"{file}: the rows have different numbers of columns {sorted(widths)}."
        )
    table = np.array(parsed, dtype=float)
    return Stations(
        x=table[:, 0],
        y=table[:, 1],
        values=table[:, 2:].T.copy(),
        ids=tuple(str(i + 1) for i in range(table.shape[0])),
    )


def read_stations_long(path: PathInput, delimiter: str = ";") -> Stations:
    """Read the long layout: ``step;id;x;y;value`` with a header line.

    Every station must appear once for every step, with the same coordinates.
    """
    file = as_path(path)
    rows = _read_rows(file, delimiter)
    if not rows:
        raise PreprocessingError(f"{file}: the station file is empty.")
    header = [cell.strip().lower() for cell in rows[0][1]]
    expected = ["step", "id", "x", "y", "value"]
    if header != expected:
        raise PreprocessingError(
            f"{file}: expected the header {';'.join(expected)}, got {';'.join(header)}."
        )
    coordinates: dict[str, tuple[float, float]] = {}
    values: dict[int, dict[str, float]] = {}
    for number, row in rows[1:]:
        if len(row) != 5:
            raise PreprocessingError(f"{file}: line {number} needs 5 columns.")
        try:
            step = int(row[0])
            station = row[1].strip()
            x, y, value = float(row[2]), float(row[3]), float(row[4])
        except ValueError as e:
            raise PreprocessingError(f"{file}: line {number} has a non-numeric cell.") from e
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(value)):
            raise PreprocessingError(f"{file}: line {number} has a non-finite value.")
        if step < 1:
            raise PreprocessingError(f"{file}: line {number}: steps start at 1.")
        known = coordinates.setdefault(station, (x, y))
        if known != (x, y):
            raise PreprocessingError(
                f"{file}: station {station} has different coordinates on line {number}."
            )
        if station in values.setdefault(step, {}):
            raise PreprocessingError(f"{file}: station {station} appears twice for step {step}.")
        values[step][station] = value
    steps = sorted(values)
    if steps != list(range(1, len(steps) + 1)):
        raise PreprocessingError(f"{file}: steps must run from 1 without gaps, got {steps}.")
    ids = tuple(sorted(coordinates, key=lambda s: (len(s), s)))
    matrix = np.empty((len(steps), len(ids)), dtype=float)
    for step in steps:
        missing = [station for station in ids if station not in values[step]]
        if missing:
            raise PreprocessingError(f"{file}: step {step} lacks the station(s) {missing}.")
        matrix[step - 1] = [values[step][station] for station in ids]
    return Stations(
        x=np.array([coordinates[s][0] for s in ids]),
        y=np.array([coordinates[s][1] for s in ids]),
        values=matrix,
        ids=ids,
    )


def _read_rows(file: Path, delimiter: str) -> list[tuple[int, list[str]]]:
    if not file.is_file():
        raise FileNotFoundError(f"Station file not found: {file}")
    with file.open(encoding="utf-8", newline="") as handle:
        return [
            (number, row)
            for number, row in enumerate(csv.reader(handle, delimiter=delimiter), start=1)
            if any(cell.strip() for cell in row)
        ]


def _duplicate_station_coordinates(stations: Stations) -> str | None:
    """Describe every coordinate shared by more than one station, or ``None``.

    Two stations at the same coordinate make the kriging matrix singular as
    soon as a step has non-constant values (``OrdinaryKriging`` inverts it
    with ``pseudo_inv=False`` by default), so this must be checked before any
    step is interpolated, not just when it happens to be reached.
    """
    stations_by_coordinate: dict[tuple[float, float], list[str]] = {}
    for station_id, x, y in zip(stations.ids, stations.x, stations.y):
        stations_by_coordinate.setdefault((float(x), float(y)), []).append(station_id)
    duplicated = {
        coordinate: ids for coordinate, ids in stations_by_coordinate.items() if len(ids) > 1
    }
    if not duplicated:
        return None
    return "; ".join(
        f"stations {', '.join(ids)} share coordinate {coordinate}"
        for coordinate, ids in duplicated.items()
    )


def coordinates_type_for(projection: str) -> CoordinatesType:
    """The kriging metric implied by a CRS (geographic when the raster has none)."""
    if not projection:
        return CoordinatesType.GEOGRAPHIC
    from osgeo import osr

    reference = osr.SpatialReference()
    reference.ImportFromWkt(projection)
    return CoordinatesType.GEOGRAPHIC if reference.IsGeographic() else CoordinatesType.EUCLIDEAN


def _great_circle_dist_func(u: np.ndarray, v: np.ndarray) -> float:
    """Angular great-circle distance (degrees) between two ``(x, y)`` points.

    Matches :func:`pykrige.core.great_circle_distance` (``x`` as longitude,
    ``y`` as latitude, both in degrees), so a variogram fitted with this
    function as ``dist_func`` uses the same metric ``OrdinaryKriging`` uses
    internally for ``coordinates_type="geographic"``. Suitable as the
    ``metric`` callable of :func:`scipy.spatial.distance.pdist`, which is how
    :class:`skgstat.Variogram` uses a ``dist_func`` that is not a string.
    """
    from pykrige.core import great_circle_distance

    return float(great_circle_distance(u[0], u[1], v[0], v[1]))


def apply_negative_policy(values: np.ndarray, policy: NegativePolicy, label: str) -> np.ndarray:
    negatives = int((values < 0).sum())
    if negatives == 0 or policy is NegativePolicy.KEEP:
        return values
    if policy is NegativePolicy.ERROR:
        raise PreprocessingError(f"{label}: {negatives} interpolated cell(s) are negative.")
    logger.warning("%s: %d negative interpolated cell(s) clamped to 0.", label, negatives)
    return np.where(values < 0, 0.0, values)


def krige_step(
    stations: Stations,
    step_index: int,
    gridx: np.ndarray,
    gridy: np.ndarray,
    coordinates_type: CoordinatesType,
    variogram_model: str = VariogramModel.SPHERICAL,
    n_lags: int = 25,
) -> np.ndarray:
    """Interpolate one step onto the grid (rows north to south, like the raster)."""
    values = stations.values[step_index]
    if np.all(values == values[0]):
        return np.full((gridy.size, gridx.size), values[0], dtype=float)
    import skgstat as skg
    from pykrige.ok import OrdinaryKriging

    # Fit the empirical variogram with the same distance metric PyKrige uses
    # to build the kriging system below, so the fitted range is expressed in
    # the same units PyKrige will interpret it with: geographic coordinates
    # are compared with the angular great-circle distance (in degrees), not
    # the Euclidean distance between raw longitude/latitude numbers, which
    # distorts distances away from the equator.
    dist_func = (
        _great_circle_dist_func if coordinates_type is CoordinatesType.GEOGRAPHIC else "euclidean"
    )
    variogram = skg.Variogram(
        coordinates=np.column_stack([stations.x, stations.y]),
        values=values,
        model=variogram_model,
        bin_func="uniform",
        n_lags=n_lags,
        dist_func=dist_func,
    )
    variogram_range, sill, nugget = variogram.parameters[:3]
    kriging = OrdinaryKriging(
        stations.x,
        stations.y,
        values,
        variogram_model=variogram_model,
        variogram_parameters=[sill, variogram_range, nugget],
        verbose=False,
        nlags=n_lags,
        weight=True,
        enable_plotting=False,
        coordinates_type=coordinates_type.value,
    )
    grid, _ = kriging.execute("grid", gridx, gridy)
    return np.asarray(grid, dtype=float)


def krige_series(
    stations: Stations,
    clone: PathInput,
    output_dir: PathInput,
    prefix: str,
    steps: int | None = None,
    first_step: int = 1,
    negative_policy: NegativePolicy = NegativePolicy.CLAMP,
    coordinates_type: CoordinatesType = CoordinatesType.AUTO,
    variogram_model: str = VariogramModel.SPHERICAL,
    n_lags: int = 25,
    nodata: float = -9999.0,
) -> list[Path]:
    """Write one PCRaster map per step of the station series on the clone grid.

    :param steps: How many steps to interpolate (default: all in the file).
    :raises PreprocessingError: With fewer than three stations, two stations
        sharing a coordinate, an unsupported variogram model, more steps than
        the file carries, a clone geometry the maps cannot express (rotated
        or south-up), a clone that is the output directory's ``manifest.csv``
        (removed before writing), or a step whose interpolated grid already
        has a valid cell equal to ``nodata``.
    """
    if len(stations.ids) < MINIMUM_STATIONS:
        raise PreprocessingError(
            f"Kriging needs at least {MINIMUM_STATIONS} stations, got {len(stations.ids)}."
        )
    duplicated_coordinates = _duplicate_station_coordinates(stations)
    if duplicated_coordinates:
        raise PreprocessingError(
            f"Kriging needs distinct station coordinates: {duplicated_coordinates}."
        )
    try:
        variogram_model = VariogramModel(variogram_model)
    except ValueError as e:
        supported = ", ".join(model.value for model in VariogramModel)
        raise PreprocessingError(
            f"Unsupported variogram model {variogram_model!r}; choose one of: {supported}."
        ) from e
    count = stations.steps if steps is None else steps
    if count < 1 or count > stations.steps:
        raise PreprocessingError(
            f"The station file carries {stations.steps} step(s); cannot interpolate {count}."
        )
    reference = read_raster(clone)
    if reference.is_rotated:
        raise PreprocessingError("The clone geometry is rotated; PCRaster maps are north-up only.")
    if reference.geotransform[5] >= 0:
        raise PreprocessingError("The clone geometry is south-up; PCRaster maps are north-up only.")
    west, cell, _, north, _, cell_y = reference.geotransform
    gridx = west + cell * (np.arange(reference.cols) + 0.5)
    gridy = north + cell_y * (np.arange(reference.rows) + 0.5)
    east, south = west + cell * reference.cols, north + cell_y * reference.rows
    outside = [
        station
        for station, x, y in zip(stations.ids, stations.x, stations.y)
        if not (
            min(west, east) <= x <= max(west, east) and min(south, north) <= y <= max(south, north)
        )
    ]
    if outside:
        logger.warning("Station(s) outside the clone extent: %s.", outside)
    metric = (
        coordinates_type_for(reference.projection)
        if coordinates_type is CoordinatesType.AUTO
        else coordinates_type
    )
    destination = as_path(output_dir)
    check_not_manifest(clone, destination, "The clone")
    remove_stale_manifest(destination)
    written: list[Path] = []
    manifest: list[tuple[str, str]] = []
    for index in range(count):
        step = first_step + index
        label = f"{prefix} step {step}"
        grid = krige_step(stations, index, gridx, gridy, metric, variogram_model, n_lags)
        grid = apply_negative_policy(grid, negative_policy, label)
        check_nodata_collision(grid, np.isfinite(grid), nodata, label)
        target = get_raster_series_filepath(destination, prefix, step)
        write_pcraster_map(target, grid, ValueScale.SCALAR, reference.geotransform, nodata)
        logger.info("Wrote %s", target)
        written.append(Path(target))
        manifest.append((f"step {index + 1}", target))
    write_manifest(destination, manifest)
    return written


def read_stations(path: PathInput, layout: StationsFormat, delimiter: str = ";") -> Stations:
    return (
        read_stations_long(path, delimiter)
        if layout is StationsFormat.LONG
        else read_stations_matrix(path, delimiter)
    )


def krige_file(
    stations_file: PathInput,
    clone: PathInput,
    output_dir: PathInput,
    prefix: str,
    layout: StationsFormat = StationsFormat.MATRIX,
    delimiter: str = ";",
    **options,
) -> list[Path]:
    """Read a station file and interpolate every step; see :func:`krige_series`.

    :raises PreprocessingError: If the station file is the output directory's
        ``manifest.csv``; :func:`krige_series` removes a stale manifest before
        writing and would delete the input.
    """
    check_not_manifest(stations_file, output_dir, "The station file")
    return krige_series(
        read_stations(stations_file, layout, delimiter), clone, output_dir, prefix, **options
    )
