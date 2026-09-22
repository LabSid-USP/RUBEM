"""The calibration objective: Nash-Sutcliffe efficiency over the sample stations.

The module reads the observed and the simulated time series, masks the values
that stand for a missing observation, computes the goodness of fit of each
station and turns the mean Nash-Sutcliffe efficiency (NSE) into the objective
the optimizer minimizes.

Nothing here imports SciPy: the efficiency, the remaining statistics and the
objective are evaluated with NumPy alone.
"""

import csv
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .._paths import PathInput, as_path

logger = logging.getLogger(__name__)

MISSING_VALUES = (-9999.0,)
"""Values written by the model and by the usual observation tables for a gap.

``-9999`` is the one the model writes, and it is negative, so the sign rule of
:func:`valid_mask` would drop it on its own; it is named here because a table
that writes it is saying "gap" and not "an implausible discharge".
"""

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

    A value counts when it is finite, is not negative, is not one of
    :data:`MISSING_VALUES` and is below ``1e30``, which covers the PCRaster
    missing value in any of its round-trips.

    Every quantity the two series carry is a flux or a storage and cannot be
    negative, so a negative entry is not a measurement: the observation tables
    of the sample stations write the gaps of a gauge as ``-9999``, as ``-1`` or
    as another negative marker of their own, and the mask drops all of them
    alike. Zero is a value, not a gap: a station may well record no flow.

    :param values: Values of one station, in step order.
    :type values: numpy.ndarray

    :return: A boolean array of the shape of ``values``.
    :rtype: numpy.ndarray
    """
    array = np.asarray(values, dtype=np.float64)
    mask = np.isfinite(array) & (array < _MISSING_THRESHOLD) & (array >= 0.0)
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


@dataclass(frozen=True)
class StationMetrics:
    """The goodness of fit of one station over the pairs both series have.

    Every field but :attr:`pairs` is ``None`` where the statistic is not
    defined: a mean and a root mean squared error need one pair, a standard
    deviation with ``ddof=1`` and an efficiency need two, and a correlation and
    an efficiency need the series they divide by to vary.

    :param pairs: Number of time steps at which both series carry a value the
        mask of :func:`valid_mask` accepts.
    :type pairs: int

    :param mean_observed: Mean of the observed values of those pairs.
    :type mean_observed: float | None

    :param std_observed: Standard deviation of the observed values of those
        pairs, with one degree of freedom (``ddof=1``).
    :type std_observed: float | None

    :param mean_simulated: Mean of the simulated values of those pairs.
    :type mean_simulated: float | None

    :param std_simulated: Standard deviation of the simulated values of those
        pairs, with one degree of freedom (``ddof=1``).
    :type std_simulated: float | None

    :param r: Pearson correlation coefficient of the two series over those
        pairs, ``None`` when either of them is constant.
    :type r: float | None

    :param rmse: Root mean squared error over those pairs.
    :type rmse: float | None

    :param nse: Nash-Sutcliffe efficiency, as :func:`nash_sutcliffe` defines it.
    :type nse: float | None
    """

    pairs: int
    mean_observed: float | None
    std_observed: float | None
    mean_simulated: float | None
    std_simulated: float | None
    r: float | None
    rmse: float | None
    nse: float | None


def station_metrics(simulated: np.ndarray, observed: np.ndarray) -> StationMetrics:
    """Return the goodness of fit of one station.

    Every statistic is computed over the pairs whose two members pass
    :func:`valid_mask`, the same sample :func:`nash_sutcliffe` uses, so the
    efficiency and the statistics that explain it always describe one sample.

    :param simulated: Simulated values, in step order.
    :type simulated: numpy.ndarray

    :param observed: Observed values, aligned with ``simulated``.
    :type observed: numpy.ndarray

    :return: The statistics of the station.
    :rtype: StationMetrics

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
    pairs = int(np.count_nonzero(mask))
    if pairs == 0:
        return StationMetrics(0, None, None, None, None, None, None, None)

    simulated_valid = simulated[mask]
    observed_valid = observed[mask]
    mean_simulated = float(np.mean(simulated_valid))
    mean_observed = float(np.mean(observed_valid))
    rmse = float(np.sqrt(np.mean((simulated_valid - observed_valid) ** 2)))
    if pairs < 2:
        return StationMetrics(pairs, mean_observed, None, mean_simulated, None, None, rmse, None)

    return StationMetrics(
        pairs=pairs,
        mean_observed=mean_observed,
        std_observed=float(np.std(observed_valid, ddof=1)),
        mean_simulated=mean_simulated,
        std_simulated=float(np.std(simulated_valid, ddof=1)),
        r=_correlation(simulated_valid, observed_valid),
        rmse=rmse,
        nse=nash_sutcliffe(simulated_valid, observed_valid),
    )


def _correlation(simulated: np.ndarray, observed: np.ndarray) -> float | None:
    """Return the Pearson correlation of two samples, or ``None``.

    The coefficient is undefined when either sample is constant, which leaves
    its own spread at zero and the quotient without a denominator. Constancy is
    tested on the values themselves, since the sum of the squared deviations of
    a constant sample is only approximately zero in floating point.
    """
    if np.all(simulated == simulated[0]) or np.all(observed == observed[0]):
        return None
    simulated_deviations = simulated - np.mean(simulated)
    observed_deviations = observed - np.mean(observed)
    spread = float(np.sqrt(np.sum(simulated_deviations**2) * np.sum(observed_deviations**2)))
    return float(np.sum(simulated_deviations * observed_deviations)) / spread


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


_ENCODING = "utf-8-sig"
"""The encoding both readers open a time series file with.

It is UTF-8 with the byte order mark removed when the file carries one. The
mark is invisible and belongs to no cell, but it is written at the start of the
first line: left in place it becomes part of the first header cell, where it
turns the time step of a header-less table into a word and hides the refusal
that :func:`_check_csv_header` owes the reader.
"""

_LAYOUTS = (
    "a time series file is either the table the model writes, whose first line is the "
    "header '0;<id>;<id>...' and whose every further line is one time step, or a PCRaster "
    "time series, whose header is a title line, the number of columns, and one line per "
    "column name starting with the time step column"
)
"""The two layouts a time series file is read in, named by every refusal of a header."""


def _read_csv(path: Path) -> Series:
    """Read the CSV layout of the model's time series tables.

    The separator is ``;``, the header is ``0;<id>;<id>...`` and every row
    carries the time step in the first column and one value per station.

    :raises ValueError: If the first record is a row of values instead of a
        header, which would otherwise read the first time step as the station
        ids and lose it from the series.
    """
    with path.open(encoding=_ENCODING, newline="") as table:
        records = [
            row for row in csv.reader(table, delimiter=";") if any(cell.strip() for cell in row)
        ]
    if not records:
        raise ValueError(f"The time series file {path} is empty.")

    header = [cell.strip() for cell in records[0]]
    _check_csv_header(header[0], path)
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


def _check_csv_header(label: str, path: Path) -> None:
    """Refuse a ``;``-separated table whose first record is already a time step.

    The first cell of the header is the label of the step column, ``0`` in the
    tables the model writes and any non-numeric word in a table written by
    hand. A first cell that is another number is a row of values: the file has
    no header, its first time step would be read as the station ids and the
    remaining columns would be labelled with that step's values.

    :raises ValueError: If the first cell is a number other than ``0``.
    """
    try:
        step = float(label)
    except ValueError:
        return
    if step == 0:
        return
    raise ValueError(
        f"The time series file {path} has no header: its first line, {label!r}, is "
        f"already a time step, and the station ids would be read from it. Add one: "
        f"{_LAYOUTS}."
    )


def _read_tss(path: Path) -> Series:
    """Read a PCRaster time series (``.tss``) file.

    The layout is a title line, a line with the number of columns, one line per
    column name starting with the time step column, and then one whitespace
    separated row per time step.

    :raises ValueError: If the header is not there. The columns of a time
        series carry the ids of the stations they were sampled at, and nothing
        in a header-less file says which station a column belongs to; numbering
        the columns instead would label them with a guess.
    """
    lines = [line for line in path.read_text(encoding=_ENCODING).splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"The time series file {path} is empty.")

    columns = int(lines[1].strip()) if len(lines) > 1 and lines[1].strip().isdigit() else 0
    names = [line.strip() for line in lines[2 : 2 + columns]]
    if columns < 2 or len(names) != columns:
        raise ValueError(
            f"The time series file {path} has no header: PCRaster time series files carry "
            f"one, and its column names are the ids of the stations the columns were "
            f"sampled at. Add it: {_LAYOUTS}."
        )
    ids = names[1:]
    data_start = 2 + columns

    rows: list[list[str]] = []
    steps: list[int] = []
    for number, line in enumerate(lines[data_start:], data_start + 1):
        cells = line.split()
        if len(cells) != len(ids) + 1:
            raise ValueError(
                f"Row {number} of the time series file {path} has {len(cells)} column(s), "
                f"the column names give {len(ids) + 1}."
            )
        steps.append(_as_step(cells[0], path, number))
        rows.append(cells[1:])
    return _build(ids, steps, rows, path)


def read_series(path: PathInput) -> Series:
    """Read a time series table, in the model's CSV layout or as a PCRaster TSS.

    The layout is recognised from the content: a first line carrying the ``;``
    separator is the CSV table the model writes, anything else is read as a
    PCRaster time series. Both layouts name their stations in a header, and a
    file without one is refused rather than read with numbered columns: the
    columns of a time series are stations, and a numbering would compare the
    observations of one gauge with the simulation of another. A byte order mark
    at the start of the file is dropped with the encoding, so that it cannot
    become part of the first header cell. Missing entries are kept as they are
    written; the mask of :func:`valid_mask` is what decides whether a value
    counts.

    :param path: The file to read.
    :type path: str | os.PathLike[str]

    :return: The parsed series.
    :rtype: Series

    :raises FileNotFoundError: If the file does not exist.
    :raises ValueError: If the file is empty, carries no header, has no station
        column, repeats a station id or has a row that does not match its
        header.
    """
    file_path = as_path(path)
    text = file_path.read_text(encoding=_ENCODING)
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    if ";" in first_line:
        return _read_csv(file_path)
    return _read_tss(file_path)


@dataclass(frozen=True)
class Alignment:
    """The steps and the stations two series are compared on.

    :param stations: The station ids both series carry, sorted.
    :type stations: list[str]

    :param steps: The time steps both series carry after the spin-up, sorted.
    :type steps: numpy.ndarray

    :param simulated_index: Rows of the simulated series, one per shared step.
    :type simulated_index: numpy.ndarray

    :param observed_index: Rows of the observed series, one per shared step.
    :type observed_index: numpy.ndarray
    """

    stations: list[str]
    steps: np.ndarray
    simulated_index: np.ndarray
    observed_index: np.ndarray


def align_series(simulated: Series, observed: Series, spinup_steps: int = 0) -> Alignment:
    """Return the steps and the stations two series have in common.

    The two series are aligned on the steps they share, after the steps up to
    ``spinup_steps`` have been dropped from both, and on the station ids they
    share: a station or a step present on one side only is ignored. This is the
    one definition of the compared window, used both by the objective and by the
    table of the best candidate, so that the two always describe one comparison.

    A step repeated in a table is aligned on its first row, since that is the
    occurrence :func:`numpy.intersect1d` reports for a repeated value.

    :param simulated: The series the run wrote.
    :type simulated: Series

    :param observed: The observed series.
    :type observed: Series

    :param spinup_steps: Number of initial steps to exclude, defaults to ``0``.
    :type spinup_steps: int, optional

    :return: The shared stations, the shared steps and the rows they are at.
    :rtype: Alignment

    :raises ValueError: If the two series share no station id or no time step.
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

    return Alignment(
        stations=shared_ids,
        steps=shared_steps,
        simulated_index=np.flatnonzero(simulated_kept)[simulated_rows],
        observed_index=np.flatnonzero(observed_kept)[observed_rows],
    )


def evaluate_series(
    simulated: Series,
    observed: Series,
    spinup_steps: int = 0,
    stations: Sequence[str] | None = None,
) -> tuple[float, dict[str, StationMetrics]]:
    """Return the mean efficiency of a run and the goodness of fit of each station.

    The two series are aligned by :func:`align_series`, and every station they
    share is measured, whether or not it enters the objective. ``stations``
    names the ones the mean efficiency is taken over, which is how a run
    calibrates on some of its gauges and reports the others as a validation;
    without it every shared station enters the mean. The mean is taken over the
    selected stations that have an efficiency, so that a station of zero
    variance, reported as ``None``, does not drag the mean.

    :param simulated: The series the run wrote.
    :type simulated: Series

    :param observed: The observed series.
    :type observed: Series

    :param spinup_steps: Number of initial steps to exclude, defaults to ``0``.
    :type spinup_steps: int, optional

    :param stations: Ids of the stations the mean is taken over. ``None``, the
        default, takes it over every shared station.
    :type stations: collections.abc.Sequence[str], optional

    :return: The mean efficiency of the selected stations and the statistics of
        every shared station.
    :rtype: tuple[float, dict[str, StationMetrics]]

    :raises ValueError: If the two series share no station id, share no time
        step, if the selection names no shared station, or if no selected
        station has an efficiency.
    """
    alignment = align_series(simulated, observed, spinup_steps)
    metrics = {
        station: station_metrics(
            simulated.stations[station][alignment.simulated_index],
            observed.stations[station][alignment.observed_index],
        )
        for station in alignment.stations
    }

    if stations is None:
        selected = list(alignment.stations)
    else:
        selected = [station for station in alignment.stations if station in set(stations)]
        if not selected:
            raise ValueError(
                f"The station(s) {', '.join(stations) or 'none'} of the objective are "
                "none of the stations the two series share "
                f"({', '.join(alignment.stations)})."
            )

    values = [metrics[station].nse for station in selected if metrics[station].nse is not None]
    if not values:
        raise ValueError(
            "No station has a Nash-Sutcliffe efficiency: every station of the objective "
            f"({', '.join(selected)}) has fewer than two valid pairs or observations "
            "without variance."
        )
    return float(np.mean(values)), metrics
