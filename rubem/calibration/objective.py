"""The calibration objective: Nash-Sutcliffe efficiency over the sample stations.

The module reads the observed and the simulated time series, masks the values
that stand for a missing observation, computes the Nash-Sutcliffe efficiency
(NSE) of each station and turns the mean efficiency into the objective the
optimizer minimizes.

Nothing here imports SciPy: the efficiency and the objective are evaluated with
NumPy alone.
"""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .._paths import PathInput, as_path

logger = logging.getLogger(__name__)

MISSING_VALUES = (-9999.0,)
"""Values written by the model and by the usual observation tables for a gap."""

PCRASTER_MISSING = 1e31
"""The PCRaster missing value.

Written as ``Float32`` it does not round-trip exactly (``float(np.float32(1e31))``
is ``9.999999...e30``), so the mask rejects everything at or above ``1e30``
instead of comparing with this constant: no streamflow or runoff of a real
basin comes anywhere near that magnitude.
"""

_MISSING_THRESHOLD = 1e30

INADMISSIBLE_OBJECTIVE = 1.0e30
"""The objective of a candidate that is not run.

The worst objective a run can produce is bounded by the efficiencies it can
reach: an NSE of -100, already an absurd simulation, gives
``1000 * (100 * 101) ** 2``, about ``1.0e11``. ``1.0e30`` is far above any such
value, so an inadmissible or failed candidate is always ranked behind every
candidate that was actually evaluated. It is finite so that it sorts, is
written to JSON and lands in the table of evaluations like any other objective.
"""


def valid_mask(values: np.ndarray) -> np.ndarray:
    """Return the mask of the values that count as an observation.

    A value counts when it is finite, is not one of :data:`MISSING_VALUES` and
    is below ``1e30``, which covers the PCRaster missing value in any of its
    round-trips.

    :param values: Values of one station, in step order.
    :type values: numpy.ndarray

    :return: A boolean array of the shape of ``values``.
    :rtype: numpy.ndarray
    """
    array = np.asarray(values, dtype=np.float64)
    mask = np.isfinite(array) & (array < _MISSING_THRESHOLD)
    for missing in MISSING_VALUES:
        mask &= array != missing
    return mask


def nash_sutcliffe(simulated: np.ndarray, observed: np.ndarray) -> float | None:
    """Return the Nash-Sutcliffe efficiency of one station, or ``None``.

    The efficiency is computed over the pairs whose two members are valid, from
    its definition::

        NSE = 1 - sum((simulated - observed) ** 2) / sum((observed - mean(observed)) ** 2)

    Both sums run over the same pairs, and the mean is the mean of the observed
    values of those pairs: a step dropped because the simulation has no value
    for it is dropped from the mean as well, so that the numerator and the
    denominator always describe the same sample.

    :param simulated: Simulated values, in step order.
    :type simulated: numpy.ndarray

    :param observed: Observed values, aligned with ``simulated``.
    :type observed: numpy.ndarray

    :return: The efficiency, or ``None`` when fewer than two pairs are valid or
        when the valid observed values are all equal, which leaves the
        denominator at zero and the efficiency undefined.
    :rtype: float | None

    :raises ValueError: If the two series do not have the same length.
    """
    simulated = np.asarray(simulated, dtype=np.float64)
    observed = np.asarray(observed, dtype=np.float64)
    if simulated.shape != observed.shape:
        raise ValueError(
            "The simulated and the observed series must have the same shape, got "
            f"{simulated.shape} and {observed.shape}."
        )

    mask = valid_mask(simulated) & valid_mask(observed)
    if int(np.count_nonzero(mask)) < 2:
        return None

    simulated_valid = simulated[mask]
    observed_valid = observed[mask]
    # The zero-variance guard: a station whose observations are all equal has no
    # variability for the efficiency to explain. Constancy is tested on the
    # values themselves, since the sum of the squared deviations of a constant
    # series is only approximately zero in floating point.
    if np.all(observed_valid == observed_valid[0]):
        return None

    residuals = float(np.sum((simulated_valid - observed_valid) ** 2))
    variability = float(np.sum((observed_valid - np.mean(observed_valid)) ** 2))
    return 1.0 - residuals / variability


def objective(nse: float) -> float:
    """Return the objective value of an efficiency, ``1000 (100 (1 - NSE))^2``.

    The objective is zero for a perfect simulation and grows quadratically as
    the efficiency falls, which is what the differential evolution minimizes.

    :param nse: The Nash-Sutcliffe efficiency of the candidate.
    :type nse: float

    :return: The objective value.
    :rtype: float
    """
    return 1000.0 * (100.0 * (1.0 - nse)) ** 2


@dataclass(frozen=True)
class Series:
    """A time series table: the steps and the values of each station.

    :param steps: The time steps, one entry per row, as integers.
    :type steps: numpy.ndarray

    :param stations: Station id to the values of that station, as ``float64``
        arrays aligned with :attr:`steps`.
    :type stations: dict[str, numpy.ndarray]
    """

    steps: np.ndarray
    stations: dict[str, np.ndarray]


def _as_value(token: str) -> float:
    """Return ``token`` as a float, or ``NaN`` when it is empty or not a number.

    An entry a table leaves empty or writes in a form that is not a number is a
    gap; it becomes ``NaN`` and the mask drops it, as it drops the gaps written
    as ``-9999`` or as the PCRaster missing value.
    """
    try:
        return float(token)
    except ValueError:
        return float("nan")


def _as_step(token: str, path: Path, number: int) -> int:
    """Return the time step written in the first column of a row.

    :raises ValueError: If the token is not a number, naming the file and the
        row, since a table whose first column is a date or a label is a common
        mistake and the bare conversion error does not say where it came from.
    """
    try:
        return int(float(token))
    except ValueError:
        raise ValueError(
            f"Row {number} of the time series file {path} does not start with a time "
            f"step: {token!r} is not a number."
        ) from None


def _build(ids: list[str], steps: list[int], rows: list[list[str]], path: Path) -> Series:
    """Assemble a :class:`Series` from the parsed header, steps and value rows."""
    duplicated = sorted({station for station in ids if ids.count(station) > 1})
    if duplicated:
        raise ValueError(
            f"The time series file {path} has repeated station ids: {', '.join(duplicated)}."
        )
    if not ids:
        raise ValueError(f"The time series file {path} has no station column.")
    if not rows:
        raise ValueError(f"The time series file {path} has no data rows.")

    values = np.array(
        [[_as_value(token) for token in row] for row in rows],
        dtype=np.float64,
    )
    return Series(
        steps=np.asarray(steps, dtype=np.int64),
        stations={station: values[:, column] for column, station in enumerate(ids)},
    )


def _read_csv(path: Path) -> Series:
    """Read the CSV layout of the model's time series tables.

    The separator is ``;``, the header is ``0;<id>;<id>...`` and every row
    carries the time step in the first column and one value per station.
    """
    with path.open(encoding="utf8", newline="") as table:
        records = [
            row for row in csv.reader(table, delimiter=";") if any(cell.strip() for cell in row)
        ]
    if not records:
        raise ValueError(f"The time series file {path} is empty.")

    header = [cell.strip() for cell in records[0]]
    ids = header[1:]
    steps: list[int] = []
    rows: list[list[str]] = []
    for number, record in enumerate(records[1:], 2):
        cells = [cell.strip() for cell in record]
        if len(cells) != len(header):
            raise ValueError(
                f"Row {number} of the time series file {path} has {len(cells)} column(s), "
                f"the header gives {len(header)}."
            )
        steps.append(_as_step(cells[0], path, number))
        rows.append(cells[1:])
    return _build(ids, steps, rows, path)


def _read_tss(path: Path) -> Series:
    """Read a PCRaster time series (``.tss``) file.

    The layout is a title line, a line with the number of columns, one line per
    column name starting with the time step column, and then one whitespace
    separated row per time step. The model writes its own ``.tss`` files
    without that header (see ``rubem.file._file_conversions.tss2csv``, which
    reads every line of them as data); such a file is read as well, and its
    stations are then numbered ``1``, ``2``, ... in column order, which is the
    numbering of the sample locations of a usual dataset.
    """
    lines = [line for line in path.read_text(encoding="utf8").splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"The time series file {path} is empty.")

    ids: list[str] | None = None
    data_start = 0
    if len(lines) > 1 and lines[1].strip().isdigit():
        columns = int(lines[1].strip())
        names = [line.strip() for line in lines[2 : 2 + columns]]
        if len(names) == columns and columns >= 2:
            ids = names[1:]
            data_start = 2 + columns

    rows: list[list[str]] = []
    steps: list[int] = []
    for number, line in enumerate(lines[data_start:], data_start + 1):
        cells = line.split()
        if ids is None:
            ids = [str(column) for column in range(1, len(cells))]
        if len(cells) != len(ids) + 1:
            raise ValueError(
                f"Row {number} of the time series file {path} has {len(cells)} column(s), "
                f"the column names give {len(ids) + 1}."
            )
        steps.append(_as_step(cells[0], path, number))
        rows.append(cells[1:])
    return _build(ids or [], steps, rows, path)


def read_series(path: PathInput) -> Series:
    """Read a time series table, in the model's CSV layout or as a PCRaster TSS.

    The layout is recognised from the content: a first line carrying the ``;``
    separator is the CSV table the model writes, anything else is read as a
    PCRaster time series. Missing entries are kept as they are written; the
    mask of :func:`valid_mask` is what decides whether a value counts.

    :param path: The file to read.
    :type path: str | os.PathLike[str]

    :return: The parsed series.
    :rtype: Series

    :raises FileNotFoundError: If the file does not exist.
    :raises ValueError: If the file is empty, has no station column, repeats a
        station id or has a row that does not match its header.
    """
    file_path = as_path(path)
    text = file_path.read_text(encoding="utf8")
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    if ";" in first_line:
        return _read_csv(file_path)
    return _read_tss(file_path)


def evaluate_series(
    simulated: Series,
    observed: Series,
    spinup_steps: int = 0,
) -> tuple[float, dict[str, float | None]]:
    """Return the mean efficiency of a run and the efficiency of each station.

    The two series are aligned on the steps they share, after the steps up to
    ``spinup_steps`` have been dropped from both, and on the station ids they
    share: a station or a step present on one side only is ignored. The mean is
    taken over the stations that have an efficiency, so that a station of zero
    variance, reported as ``None``, does not drag the mean.

    A step repeated in a table is aligned on its first row, since that is the
    occurrence :func:`numpy.intersect1d` reports for a repeated value.

    :param simulated: The series the run wrote.
    :type simulated: Series

    :param observed: The observed series.
    :type observed: Series

    :param spinup_steps: Number of initial steps to exclude, defaults to ``0``.
    :type spinup_steps: int, optional

    :return: The mean efficiency and the efficiency of every shared station.
    :rtype: tuple[float, dict[str, float | None]]

    :raises ValueError: If the two series share no station id, share no time
        step, or if no shared station has an efficiency.
    """
    shared_ids = sorted(set(simulated.stations) & set(observed.stations))
    if not shared_ids:
        raise ValueError(
            "The simulated and the observed series have no station in common: the "
            f"simulation has {', '.join(sorted(simulated.stations)) or 'none'} and the "
            f"observations have {', '.join(sorted(observed.stations)) or 'none'}."
        )

    simulated_steps = np.asarray(simulated.steps, dtype=np.int64)
    observed_steps = np.asarray(observed.steps, dtype=np.int64)
    simulated_kept = simulated_steps > spinup_steps
    observed_kept = observed_steps > spinup_steps
    shared_steps, simulated_rows, observed_rows = np.intersect1d(
        simulated_steps[simulated_kept],
        observed_steps[observed_kept],
        return_indices=True,
    )
    if shared_steps.size == 0:
        raise ValueError(
            "The simulated and the observed series have no time step in common after "
            f"the {spinup_steps} spin-up step(s): the simulation has "
            f"{simulated_steps[simulated_kept].tolist()} and the observations have "
            f"{observed_steps[observed_kept].tolist()}."
        )

    simulated_index = np.flatnonzero(simulated_kept)[simulated_rows]
    observed_index = np.flatnonzero(observed_kept)[observed_rows]

    station_nse: dict[str, float | None] = {
        station: nash_sutcliffe(
            simulated.stations[station][simulated_index],
            observed.stations[station][observed_index],
        )
        for station in shared_ids
    }

    values = [nse for nse in station_nse.values() if nse is not None]
    if not values:
        raise ValueError(
            "No station has a Nash-Sutcliffe efficiency: every shared station "
            f"({', '.join(shared_ids)}) has fewer than two valid pairs or observations "
            "without variance."
        )
    return float(np.mean(values)), station_nse
