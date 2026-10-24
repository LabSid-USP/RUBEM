"""The calibration itself: a differential evolution over the free parameters.

:func:`calibrate` loads and validates the configuration once, reads the observed
series, and hands SciPy's ``differential_evolution`` a process pool whose workers
run one model evaluation each and exit. The pool is the isolation layer: PCRaster
keeps its clone and its raster memory process-wide, so a worker that is reused
would accumulate the state of every run it made; ``spawn`` with
``max_tasks_per_child=1`` gives every evaluation a fresh interpreter.

The run directory receives, before the search, ``observed.csv``, the coverage
and the summary statistics of the observations over the compared steps, and
after it ``evaluations.csv``, one row per evaluation, ``stations.csv``, the
goodness of fit of the best candidate at every station, ``best_<variable>.csv``,
the observed and the simulated series of that candidate side by side,
``result.json``, the best candidate and the settings that found it, and
``<configuration>-calibrated.json``, the calibrated configuration in the format
the input was written in. The rows of the table of evaluations are ordered by the
candidate they evaluated and not by the moment they were written, so that the
order of the rows does not depend on the order in which the workers happened to
finish; the ``started_at`` column is what puts them back in the order they were
made in. It does not make the table itself reproducible: the ``id``, ``pid``,
``started_at`` and ``elapsed_seconds`` columns differ between two runs of one
seed, and from the
first generation on the selection reads the objective values, so two runs
evaluate the same candidates only when the simulation itself is reproducible
(on the real basins that requires a fixed ``RASTERS.ldd``, since ``lddcreate``
does not always derive the same directions twice; see the note on the LDD
raster in the user guide).

Number of evaluations
    The population of a ``sobol`` initialization is ``max(5, popsize * N)``,
    with ``N`` the number of free parameters, rounded up to the next power of
    two, since a Sobol' sequence is balanced only over a power-of-two sample:
    with the default ``popsize`` of 15 and the eight free parameters of a search
    without fixed ones that is 128 members, so a calibration costs one model run
    per member and per
    generation, ``128 * (maxiter + 1)`` runs at most. The number is logged when
    the calibration starts so that the budget can be checked before it runs.
    Members whose weights violate ``w_1 + w_2 <= 1`` are skipped by SciPy
    without a model run, so the real count is usually lower.

SciPy is an optional dependency, imported inside :func:`calibrate`; importing
this module without it works and raises nothing.
"""

import csv
import functools
import json
import logging
import math
import multiprocessing
import os
import shutil
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .. import _deps
from .._paths import PathInput, as_path
from ..configuration._ranges import variable_range
from ..configuration.model_configuration_file_v1 import (
    VARIABLE_IDS,
    Aggregation,
    ModelConfigurationFileV1,
)
from ..validation.lookup_tables import LookupTableError
from ._worker import _INADMISSIBLE_ERROR, EvaluationContext, evaluate, simulate_best
from .modflow_parameters import MODFLOW_PREFIX, ModflowCatalog, catalog
from .objective import Series, align_series, read_series, valid_mask
from .parameters import (
    CALIBRATION_PARAMETERS,
    FREE_PARAMETERS,
    DecisionSpace,
    decision_space,
)

logger = logging.getLogger(__name__)

progress = logging.getLogger("rubem.progress")
"""The logger of what a person watching a calibration wants to see.

The budget, one line per generation and the closing summary go here; the module
logger keeps the diagnostics, the warnings and the refusals. The command line
routes this logger to standard output, as it does for a simulation, so that an
embedded calibration stays silent unless its host asks for the progress.
"""

EVALUATIONS_DIRNAME = "evaluations"
"""Name of the directory under the run directory that collects the JSON records."""

EVALUATIONS_CSV = "evaluations.csv"
RESULT_JSON = "result.json"
OBSERVED_CSV = "observed.csv"
STATIONS_CSV = "stations.csv"

EVALUATION_COLUMNS = (
    "id",
    "pid",
    "started_at",
    *CALIBRATION_PARAMETERS,
    "nse",
    "objective",
    "elapsed_seconds",
    "error",
)
"""The columns of ``evaluations.csv``, one row per evaluation, when the run
calibrates no MODFLOW parameter; the MODFLOW parameters of a run follow ``x``."""

OBSERVED_COLUMNS = (
    "station",
    "in_selection",
    "pairs_in_window",
    "dropped",
    "mean",
    "std",
    "min",
    "max",
)
"""The columns of ``observed.csv``, one row per station of the observed series."""

STATION_COLUMNS = (
    "station",
    "in_selection",
    "pairs",
    "mean_observed",
    "std_observed",
    "mean_simulated",
    "std_simulated",
    "r",
    "rmse",
    "nse",
)
"""The columns of ``stations.csv``, one row per station the best candidate compared."""

STATION_SEPARATOR = ";"
"""The separator of the per-station tables, the one the model writes its own tables with."""


_MODFLOW_DEATH = (
    " With MODFLOW, a run that does not converge before the last time step of a stress "
    "period (dis.nstp > 1) also ends its worker process; dis.nstp = 1 turns it into a "
    "failed evaluation."
)
"""What a dead worker of a coupled calibration may also mean."""


class CalibrationError(RuntimeError):
    """A calibration that could not start, or that produced no usable evaluation."""


@dataclass(frozen=True)
class CalibrationSettings:
    """How the differential evolution is run.

    The differential evolution defaults follow the method the calibration of the
    model was designed around; the remaining fields are the knobs the command
    line exposes.

    :param variable: Id of the output variable compared with the observations.
        ``arn``, the accumulated total runoff in m3/s, by default; ``rnf`` is
        the total runoff per cell in mm.
    :type variable: str

    :param spinup_steps: Number of initial time steps excluded from the
        efficiency.
    :type spinup_steps: int

    :param maxiter: Maximum number of generations.
    :type maxiter: int

    :param popsize: Population multiplier; see the module docstring for the
        number of members it produces.
    :type popsize: int

    :param seed: Seed of the random generator of the search, for a reproducible
        calibration. ``None`` leaves the generator unseeded.
    :type seed: int | None

    :param workers: Number of worker processes. ``None``, the default, resolves
        at call time to one less than the number of CPUs, at least one, which
        leaves a core for the parent.
    :type workers: int | None

    :param temp_dir: Directory the per-evaluation output directories are
        created in. ``None`` uses the temporary directory of the system.
    :type temp_dir: str | None

    :param init: Initial population: the name of a SciPy initialization
        (``sobol`` by default) or an explicit ``(S, N)`` array with ``S > 4``
        members and one column per free parameter, which is one column fewer
        for every parameter :attr:`fixed` takes out of the decision vector.
    :type init: str | numpy.ndarray

    :param strategy: Differential evolution strategy.
    :type strategy: str

    :param mutation: Mutation constant, a ``(min, max)`` pair for dithering.
    :type mutation: tuple[float, float]

    :param recombination: Crossover probability.
    :type recombination: float

    :param polish: Whether a local search refines the best candidate. ``False``:
        the local search would spend model runs on gradients the objective, a
        simulation read from a table, does not provide reliably.
    :type polish: bool

    :param bounds: The ``(minimum, maximum)`` range to search a parameter in, by
        name; it narrows the range of the application settings, which is what a
        parameter left out of the mapping is searched in. ``None``, the default,
        searches every parameter in the range of the settings.
    :type bounds: dict[str, tuple[float, float]] | None

    :param fixed: The parameters that are not searched, by name, with the value
        every candidate carries. A fixed parameter leaves the decision vector,
        so the search loses one dimension, and keeps its value in the nine
        parameters of every run and of the result. ``None``, the default,
        searches every parameter.
    :type fixed: dict[str, float] | None

    :param stations: Ids of the stations whose efficiency the objective averages.
        ``None``, the default, uses every station the observed series and the
        run have in common.
    :type stations: tuple[str, ...] | None

    :param allow_blocking_problems: Whether the calibration loads, and searches
        on, a configuration whose inputs carry blocking problems. The checks
        still run and every problem is still reported; the search then starts
        instead of stopping. ``False``, the default, refuses such a
        configuration, as a run of the model does. The value is recorded in
        :file:`result.json`, since what the search fitted was measured on inputs
        the validation rejected.
    :type allow_blocking_problems: bool
    """

    variable: str = "arn"
    spinup_steps: int = 0
    maxiter: int = 100
    popsize: int = 15
    seed: int | None = None
    workers: int | None = None
    temp_dir: str | None = None
    init: str | np.ndarray = "sobol"
    strategy: str = "best1exp"
    mutation: tuple[float, float] = (0.5, 1.0)
    recombination: float = 0.7
    polish: bool = False
    bounds: dict[str, tuple[float, float]] | None = None
    fixed: dict[str, float] | None = None
    stations: tuple[str, ...] | None = None
    allow_blocking_problems: bool = False


@dataclass(frozen=True)
class CalibrationResult:
    """What a finished calibration found and where it wrote it.

    :param best_parameters: The nine calibration parameters of the best
        candidate, the derived ``w_3`` included, followed by the MODFLOW
        parameters the run searched or fixed.
    :type best_parameters: dict[str, float]

    :param best_nse: The mean Nash-Sutcliffe efficiency of the best candidate,
        ``None`` when no recorded evaluation reached one.
    :type best_nse: float | None

    :param best_objective: The objective value of the best candidate.
    :type best_objective: float

    :param evaluations: Number of objective evaluations the search spent.
    :type evaluations: int

    :param generations: Number of generations the search ran.
    :type generations: int

    :param success: Whether SciPy reports the search as successful.
    :type success: bool

    :param message: The termination message of SciPy.
    :type message: str

    :param run_dir: The run directory the artifacts were written to.
    :type run_dir: pathlib.Path

    :param evaluations_csv: The table of every evaluation.
    :type evaluations_csv: pathlib.Path

    :param result_json: The summary of the calibration.
    :type result_json: pathlib.Path

    :param calibrated_config: The input configuration with the best parameters.
    :type calibrated_config: pathlib.Path

    :param best_series: The observed and the simulated series of the best
        candidate, side by side on the compared steps.
    :type best_series: pathlib.Path

    :param stations_csv: The goodness of fit of the best candidate at every
        station the two series share.
    :type stations_csv: pathlib.Path
    """

    best_parameters: dict[str, float]
    best_nse: float | None
    best_objective: float
    evaluations: int
    generations: int
    success: bool
    message: str
    run_dir: Path
    evaluations_csv: Path
    result_json: Path
    calibrated_config: Path
    best_series: Path
    stations_csv: Path


def _prepare_worker() -> None:
    """Silence a worker process before it evaluates its candidate.

    The pool starts every worker as a fresh interpreter with no logging
    configuration, so the warnings the loader emits for a configuration whose
    inputs are not validated again would reach the terminal through the last
    resort handler of :mod:`logging`, once per evaluation; the parent already
    reported them when it validated the inputs. The PCRaster framework also
    prints a newline when an interpreter exits, one per evaluation. A null
    handler on the root logger and a standard output pointed at the null device
    keep both out of the terminal: every failure of an evaluation is recorded in
    its JSON record and summarized by the parent instead.
    """
    logging.getLogger().addHandler(logging.NullHandler())
    sys.stdout = Path(os.devnull).open("w", encoding="utf-8")


def _report_failures(records: list[dict[str, Any]]) -> None:
    """Log one summary of the evaluations that failed, if any did."""
    failures = [
        record["error"]
        for record in records
        if record.get("error") not in (None, _INADMISSIBLE_ERROR)
    ]
    if failures:
        logger.warning(
            "%d of %d evaluation(s) failed and were ranked behind every evaluated candidate; "
            "the first failure was: %s. Every failure is recorded in the evaluations table.",
            len(failures),
            len(records),
            failures[0],
        )


@dataclass
class _Progress:
    """The per-generation callback: it only logs, it never stops the search."""

    evaluations_dir: Path
    generations: int = field(default=0)

    def __call__(self, intermediate_result) -> bool:
        """Log the generation, the best objective and efficiency so far and the records.

        The best efficiency is read from the records the workers have written,
        which is where the efficiencies live: what SciPy reports is the
        objective, and the efficiency behind it is what a person watching a
        calibration reads.

        SciPy inspects the signature of the callback and passes the
        intermediate result by keyword under exactly this name; returning
        ``True`` would halt the search, so the callback always returns
        ``False``.
        """
        self.generations = int(getattr(intermediate_result, "nit", 0) or 0)
        records = _read_records(self.evaluations_dir)
        best = _best_record(records)
        best_nse = None if best is None else best.get("nse")
        progress.info(
            "Generation %d: best objective %.6g, best NSE %s, %d evaluation(s) recorded.",
            self.generations,
            float(intermediate_result.fun),
            "n/a" if best_nse is None else f"{float(best_nse):.6f}",
            len(records),
        )
        return False


def calibrate(
    config_path: PathInput,
    observed_path: PathInput,
    run_dir: PathInput,
    settings: CalibrationSettings = CalibrationSettings(),
) -> CalibrationResult:
    """Calibrate a configuration against an observed series and write the artifacts.

    :param config_path: The configuration file to calibrate, legacy or format 1.0.
    :type config_path: str | os.PathLike[str]

    :param observed_path: The observed series, in the CSV layout of the time
        series tables of the model or as a PCRaster TSS file.
    :type observed_path: str | os.PathLike[str]

    :param run_dir: Directory the artifacts of the calibration are written to.
        It is created when it does not exist.
    :type run_dir: str | os.PathLike[str]

    :param settings: How the search is run, defaults to :class:`CalibrationSettings`.
    :type settings: CalibrationSettings, optional

    :return: The best candidate and the artifacts of the run.
    :rtype: CalibrationResult

    :raises CalibrationError: If SciPy is not installed, if the configuration
        cannot be calibrated as asked, if the observed series shares no time
        step or no station with what the configuration will sample, if the
        station selection names none of those stations, if a conductivity
        lookup table of the MODFLOW section cannot be read, if a worker process
        died before finishing its evaluation, or if every evaluation of the run
        failed. An interrupted or crashed search still leaves the table of the
        evaluations it made behind.
    :raises ValueError: If the decision space the settings describe is not a
        search (an unknown or derived parameter, a fixed value or an overridden
        bound outside the range of the application settings, every parameter
        fixed, a MODFLOW name the configuration does not offer or a MODFLOW bound
        outside the values of its parameter), or if an explicit initial
        population does not have one column per free parameter.
    :raises ImportError: If PCRaster or GDAL are not installed.
    :raises FileNotFoundError: If the configuration or the observed series is
        not there.
    :raises ConfigurationError: If the configuration carries blocking problems.
    """
    differential_evolution = _require_scipy()

    from ..api import Model

    if settings.variable not in VARIABLE_IDS:
        raise CalibrationError(
            f"'{settings.variable}' is not an output variable of the model; "
            f"calibrate against one of {', '.join(VARIABLE_IDS)}."
        )
    if settings.spinup_steps < 0:
        raise CalibrationError(
            f"The number of spin-up steps must not be negative, got {settings.spinup_steps}."
        )
    if settings.workers is not None and settings.workers < 1:
        raise CalibrationError(
            f"The calibration needs at least one worker process, got {settings.workers}."
        )
    _check_stations(settings.stations)

    config_file = as_path(config_path).absolute()
    # The only validation of a whole calibration: the workers never revalidate,
    # so this is where a blocking problem stops the search, and where
    # ``allow_blocking_problems`` lets it start anyway.
    configuration = Model.from_file(
        config_file,
        validate_input=True,
        allow_blocking_problems=settings.allow_blocking_problems,
    ).configuration
    file_v1 = _as_v1(configuration)
    modflow = _modflow_catalog(configuration)
    if modflow is not None and configuration.modflow.dis.nstp > 1:
        # The extension ends the process, not the stress period, when MODFLOW
        # stops before the last time step; the pool cannot replace that worker.
        logger.warning(
            "The MODFLOW section has dis.nstp %d: a candidate whose solver does not "
            "converge before the last time step of a stress period ends its worker "
            "process, and with it the calibration, instead of being ranked last as a "
            "failed evaluation. Set dis.nstp to 1 to keep the search running past it.",
            configuration.modflow.dis.nstp,
        )
    # The MODFLOW names can only be resolved once the configuration says which
    # parameters its MODFLOW section offers.
    space = decision_space(fixed=settings.fixed, bounds=settings.bounds, modflow=modflow)
    if not isinstance(settings.init, str):
        shape = np.shape(settings.init)
        if len(shape) != 2 or shape[1] != space.dimension:
            raise ValueError(
                f"The initial population has the shape {shape} and the search has "
                f"{space.dimension} free parameter(s) ({', '.join(space.free_names)}); it must "
                f"be a two-dimensional array of {shape[0] if shape else 0} member(s) with one "
                "column per free parameter."
            )
    _check_sample_locations(configuration, file_v1)

    observed = read_series(observed_path)
    aggregation = file_v1.model_simulation_output.time_series_samples.aggregation
    sampled_ids = (
        None
        if aggregation is Aggregation.ZONES
        else _station_ids(configuration.raster_files.sample_locations)
    )
    compared_steps = _compared_steps(
        first_step=configuration.simulation_period.first_step,
        last_step=configuration.simulation_period.last_step,
        spinup_steps=settings.spinup_steps,
    )
    _check_observed_series(
        observed,
        first_step=configuration.simulation_period.first_step,
        last_step=configuration.simulation_period.last_step,
        spinup_steps=settings.spinup_steps,
        aggregation=aggregation,
        station_ids=sampled_ids,
    )
    _check_station_selection(settings.stations, observed, sampled_ids)
    x0 = _starting_point(
        space,
        {
            **configuration.calibration_parameters.model_dump(),
            **(modflow.values if modflow is not None else {}),
        },
    )

    run_directory = as_path(run_dir).absolute()
    evaluations_dir = run_directory / EVALUATIONS_DIRNAME
    evaluations_dir.mkdir(parents=True, exist_ok=True)
    previous = _record_paths(evaluations_dir)
    if previous:
        raise CalibrationError(
            f"The run directory {run_directory} already holds {len(previous)} evaluation "
            "record(s) of an earlier calibration; consolidating both runs into one table "
            "would mix them. Choose an empty run directory."
        )
    observed_csv = run_directory / OBSERVED_CSV
    _write_observed_csv(observed_csv, observed, compared_steps, settings.stations)
    _report_observed_coverage(observed, compared_steps, settings.stations)
    temp_dir = (
        as_path(settings.temp_dir).absolute()
        if settings.temp_dir is not None
        else Path(tempfile.gettempdir())
    )
    temp_dir.mkdir(parents=True, exist_ok=True)

    workers = (
        settings.workers if settings.workers is not None else max(1, (os.cpu_count() or 2) - 1)
    )
    context = EvaluationContext(
        document=file_v1.to_dict(),
        base_dir=configuration.base_dir,
        variable=settings.variable,
        observed=observed,
        spinup_steps=settings.spinup_steps,
        temp_dir=str(temp_dir),
        evaluations_dir=str(evaluations_dir),
        validate_input=False,
        space=space,
        stations=settings.stations,
        modflow=modflow,
    )
    columns = _evaluation_columns(space)

    planned_members = _population_size(settings, space.dimension)
    progress.info(
        "Calibrating %d free parameter(s) with %d population member(s) per generation and "
        "at most %d generation(s): up to %d model run(s), on %d worker process(es).",
        space.dimension,
        planned_members,
        settings.maxiter,
        planned_members * (settings.maxiter + 1),
        workers,
    )
    _report_decision_space(space, settings.stations)

    # A search with at most one free weight has no constraint to hand over: the
    # sum of the weights is then a bound of the decision space, and SciPy takes
    # a different code path for a constrained search, so the argument is left
    # out instead of being passed as ``None``.
    constraint = space.weights_constraint()
    callback = _Progress(evaluations_dir)
    if modflow is not None:
        # The extension launches mf2005 from PATH, and the spawned workers
        # inherit the environment of this process.
        _deps.ensure_mf2005_on_path()
    executor = _pool(workers)
    arguments: dict[str, Any] = {
        "strategy": settings.strategy,
        "maxiter": settings.maxiter,
        "popsize": settings.popsize,
        "mutation": settings.mutation,
        "recombination": settings.recombination,
        "rng": settings.seed,
        "polish": settings.polish,
        "init": settings.init,
        "x0": x0,
        "updating": "deferred",
        "workers": executor.map,
        "callback": callback,
    }
    if constraint is not None:
        arguments["constraints"] = constraint
    evaluations_csv = run_directory / EVALUATIONS_CSV
    try:
        try:
            optimum = differential_evolution(
                functools.partial(evaluate, context=context),
                list(space.bounds),
                **arguments,
            )
        finally:
            executor.shutdown(wait=True)
    except BaseException as error:
        # An interruption or a crash after the first evaluation still leaves a
        # table: the evaluations that were made are hours of model runs, and a
        # calibration that has to be stopped is read from them like any other.
        _consolidate(evaluations_csv, evaluations_dir, columns)
        if isinstance(error, BrokenProcessPool):
            raise CalibrationError(
                "A worker process died before finishing its evaluation, most often "
                "because the system killed it for lack of memory: every worker holds "
                "the rasters of one model run. Run the calibration again with a lower "
                f"--workers.{_MODFLOW_DEATH if modflow is not None else ''} The evaluations "
                f"made so far are in {evaluations_csv}."
            ) from error
        raise

    records = _read_records(evaluations_dir)
    _write_evaluations_csv(evaluations_csv, records, columns)

    _report_failures(records)
    best = _best_record(records)
    if best is None:
        raise CalibrationError(
            "Every evaluation of the calibration failed; the first failure was: "
            f"{_first_error(records)}. The table of the evaluations is {evaluations_csv}."
        )

    # The size of the population SciPy actually built, not the size this module
    # predicted for the budget: a named initialization resizes the population
    # (``sobol`` rounds it up to a power of two) and the summary must describe
    # the search that ran.
    population_size = int(np.shape(optimum.population)[0])
    if population_size != planned_members:
        logger.info(
            "The search used %d population member(s), %d were announced.",
            population_size,
            planned_members,
        )

    best_parameters = space.to_parameters(optimum.x)
    best_objective = float(optimum.fun)
    result_json = run_directory / RESULT_JSON
    calibrated_config = run_directory / f"{config_file.stem}-calibrated.json"
    stations_csv = run_directory / STATIONS_CSV
    best_series = run_directory / f"best_{settings.variable}.csv"
    _write_stations_csv(stations_csv, best.get("station_metrics") or {}, settings.stations)
    _write_calibrated_config(calibrated_config, configuration, file_v1, best_parameters, modflow)
    _write_best_series(
        best_series,
        document=file_v1.to_dict(),
        base_dir=configuration.base_dir,
        parameters=best_parameters,
        modflow=modflow,
        variable=settings.variable,
        observed=observed,
        spinup_steps=settings.spinup_steps,
        temp_dir=temp_dir,
        workers=workers,
        evaluations_csv=evaluations_csv,
    )
    _write_result_json(
        result_json,
        best_parameters=best_parameters,
        best_nse=best["nse"],
        best_objective=best_objective,
        optimum=optimum,
        settings=settings,
        space=space,
        workers=workers,
        temp_dir=temp_dir,
        population_size=population_size,
        artifacts={
            "evaluations_csv": str(evaluations_csv),
            "observed_csv": str(observed_csv),
            "stations_csv": str(stations_csv),
            "best_series": str(best_series),
            "calibrated_config": str(calibrated_config),
        },
    )

    progress.info(
        "Calibration finished after %d evaluation(s) in %d generation(s): best objective "
        "%.6g, best NSE %s.",
        int(optimum.nfev),
        int(optimum.nit),
        best_objective,
        "n/a" if best["nse"] is None else f"{float(best['nse']):.6f}",
    )
    return CalibrationResult(
        best_parameters=best_parameters,
        best_nse=best["nse"],
        best_objective=best_objective,
        evaluations=int(optimum.nfev),
        generations=int(optimum.nit),
        success=bool(optimum.success),
        message=str(optimum.message),
        run_dir=run_directory,
        evaluations_csv=evaluations_csv,
        result_json=result_json,
        calibrated_config=calibrated_config,
        best_series=best_series,
        stations_csv=stations_csv,
    )


def _require_scipy():
    """Return ``scipy.optimize.differential_evolution``, or explain how to install it.

    :raises CalibrationError: If SciPy is not installed.
    """
    from .. import _deps

    missing = _deps.missing_calibration_deps()
    if missing:
        raise CalibrationError(_deps.calibration_deps_message(missing))
    from scipy.optimize import differential_evolution

    return differential_evolution


def _check_stations(stations: tuple[str, ...] | None) -> None:
    """Refuse a station selection the objective could not be averaged over.

    :param stations: The ids the caller asked the objective to average, or
        ``None`` for every station the two series share.
    :type stations: tuple[str, ...] | None

    :raises CalibrationError: If the selection is not a non-empty sequence of
        non-empty station ids.
    """
    if stations is None:
        return
    if isinstance(stations, str) or not isinstance(stations, (tuple, list)):
        raise CalibrationError(
            "The stations of the objective must be given as a tuple of station ids, "
            f"got {type(stations).__name__}."
        )
    if not stations:
        raise CalibrationError(
            "The stations of the objective are an empty selection; name at least one station, "
            "or leave them unset to average every station the two series share."
        )
    wrong = [station for station in stations if not isinstance(station, str) or not station.strip()]
    if wrong:
        raise CalibrationError(
            f"The station id(s) {', '.join(repr(station) for station in wrong)} are not "
            "non-empty station ids; a station is named by the id it carries in the header of "
            "the time series table."
        )


def _pool(workers: int) -> ProcessPoolExecutor:
    """Return the process pool one evaluation at a time is run in.

    ``spawn`` with one task per worker is what isolates the runs from each
    other: PCRaster keeps its clone and its raster memory process-wide, so a
    worker reused for a second evaluation would carry the state of the first.
    """
    return ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("spawn"),
        max_tasks_per_child=1,
        initializer=_prepare_worker,
    )


def _consolidate(evaluations_csv: Path, evaluations_dir: Path, columns: tuple[str, ...]) -> None:
    """Write the table of the evaluations recorded so far, if there are any.

    This is what an interrupted or crashed search leaves behind: the records
    are already on disk, one per evaluation, and consolidating them costs
    nothing next to the model runs they stand for. A failure to write the table
    is reported and swallowed, since the exception that brought the search down
    is the one the caller has to see.
    """
    try:
        records = _read_records(evaluations_dir)
        if records:
            _write_evaluations_csv(evaluations_csv, records, columns)
            logger.warning(
                "The search ended early; the %d evaluation(s) it recorded are in %s.",
                len(records),
                evaluations_csv,
            )
    except Exception as error:  # pragma: no cover - the original failure must win
        logger.warning("The evaluations of the interrupted search could not be written: %s", error)


def _compared_steps(*, first_step: int, last_step: int, spinup_steps: int) -> list[int]:
    """Return the simulated time steps the efficiency is computed on, in order."""
    return [step for step in range(first_step, last_step + 1) if step > spinup_steps]


def _check_station_selection(
    stations: tuple[str, ...] | None,
    observed: Series,
    sampled_ids: set[str] | None,
) -> None:
    """Refuse a station selection that names none of the stations of the run.

    The selection is applied inside every evaluation, so a misspelt id would
    make every one of them fail and the whole budget would be spent finding
    out. The comparable stations are the ones the observed series and the run
    have in common; under the ``zones`` aggregation the parent does not know
    the ids of the run, so the selection is only checked against the
    observations.

    :param stations: The ids the objective averages, or ``None``.
    :type stations: tuple[str, ...] | None

    :param observed: The observed series, as the parent read it.
    :type observed: rubem.calibration.objective.Series

    :param sampled_ids: The ids the run will sample, or ``None`` when they are
        not known before the run.
    :type sampled_ids: set[str] | None

    :raises CalibrationError: If none of the selected ids is comparable.
    """
    if stations is None:
        return
    comparable = set(observed.stations)
    if sampled_ids is not None:
        comparable &= sampled_ids
    unknown = [station for station in stations if station not in comparable]
    if len(unknown) == len(stations):
        raise CalibrationError(
            f"The station(s) {', '.join(stations)} of the objective are none of the "
            f"station(s) {', '.join(sorted(comparable)) or 'none'} the observed series and "
            "the run have in common; every evaluation would fail."
        )
    if unknown:
        logger.warning(
            "The objective names %d station(s) the comparison does not have (%s); it is "
            "averaged over the remaining ones.",
            len(unknown),
            ", ".join(unknown),
        )


def _starting_point(space: DecisionSpace, parameters: dict[str, float]) -> np.ndarray:
    """Return the ``x0`` of the search: the configuration, inside the bounds of the run.

    The starting point is the parameter set of the configuration being
    calibrated. A bound narrowed for this run may exclude it, and SciPy refuses
    a starting point outside the bounds, so every coordinate that falls outside
    is moved onto the bound it crosses and the move is reported: the run then
    starts from the admissible point closest to the configuration instead of
    ending before its first evaluation.

    :param space: The decision vector of the run.
    :type space: rubem.calibration.parameters.DecisionSpace

    :param parameters: The calibration parameters of the configuration.
    :type parameters: dict[str, float]

    :return: The free values of the starting point, in the order of the space.
    :rtype: numpy.ndarray
    """
    x0 = space.from_parameters(parameters)
    for index, (name, (minimum, maximum)) in enumerate(
        zip(space.free_names, space.bounds, strict=True)
    ):
        value = float(x0[index])
        moved = min(max(value, minimum), maximum)
        if moved != value:
            x0[index] = moved
            logger.warning(
                "The configuration has %s = %g, outside the bound [%g, %g] of this "
                "calibration; the search starts from %g instead.",
                name,
                value,
                minimum,
                maximum,
                moved,
            )
    if not space.is_admissible(x0):
        logger.warning(
            "The parameters of the configuration are not an admissible candidate of this "
            "calibration; the search starts from the rest of the initial population."
        )
    return x0


def _report_decision_space(space: DecisionSpace, stations: tuple[str, ...] | None) -> None:
    """Log what this run searches: the fixed parameters, the narrowed bounds and the stations."""
    if space.fixed:
        logger.info(
            "Fixed, not searched: %s.",
            ", ".join(f"{name} = {value:g}" for name, value in space.fixed.items()),
        )
    # A MODFLOW parameter has no range in the application settings: its bound
    # is always the caller's.
    narrowed = [
        (name, bound)
        for name, bound in zip(space.free_names, space.bounds, strict=True)
        if name.startswith(MODFLOW_PREFIX) or bound != variable_range(name)
    ]
    if narrowed:
        logger.info(
            "Searched in a narrowed range: %s.",
            ", ".join(
                f"{name} in [{minimum:g}, {maximum:g}]" for name, (minimum, maximum) in narrowed
            ),
        )
    if stations is not None:
        logger.info("The objective averages the station(s) %s.", ", ".join(stations))


def _as_v1(configuration) -> ModelConfigurationFileV1:
    """Return the configuration as a format 1.0 model, converting a legacy one."""
    if configuration.file_v1 is not None:
        return configuration.file_v1
    return ModelConfigurationFileV1.from_legacy(configuration.file)


def _check_sample_locations(configuration, file_v1: ModelConfigurationFileV1) -> None:
    """Refuse a configuration whose time series would have nowhere to be sampled.

    :raises CalibrationError: If the raster the configured aggregation needs is
        not part of the configuration.
    """
    aggregation = file_v1.model_simulation_output.time_series_samples.aggregation
    if aggregation is Aggregation.ZONES:
        if not configuration.raster_files.zones:
            raise CalibrationError(
                "The configuration aggregates its time series over zones but names no "
                "zones raster; the calibration has no station to compare."
            )
        return
    if not configuration.raster_files.sample_locations:
        raise CalibrationError(
            "The configuration names no sample locations raster; the calibration has no "
            "station to compare the observed series with."
        )


def _station_ids(sample_locations: PathInput) -> set[str]:
    """Return the station ids of a sample locations raster.

    The raster is a nominal map, so its cells read as integers. Neither the
    no-data cells nor the zeroes are stations, which is what the validation of
    the inputs already asks of a sample raster: its ids are ``1..N`` and its
    background is missing or zero. Every remaining value becomes the string the
    model writes in the header of its time series table, ``str(int(value))``.

    :param sample_locations: The sample locations raster of the configuration.
    :type sample_locations: str | os.PathLike[str]

    :return: The distinct station ids, as strings.
    :rtype: set[str]
    """
    from osgeo import gdal

    gdal.UseExceptions()
    gdal.AllRegister()
    dataset = gdal.Open(str(as_path(sample_locations)))
    try:
        band = dataset.GetRasterBand(1)
        values = np.unique(np.asarray(band.ReadAsArray()))
        no_data = band.GetNoDataValue()
    finally:
        dataset = None

    if no_data is not None:
        values = values[values != no_data]
    return {str(int(value)) for value in values.tolist() if math.isfinite(value) and value != 0}


def _check_observed_series(
    observed: Series,
    *,
    first_step: int,
    last_step: int,
    spinup_steps: int,
    aggregation: Aggregation,
    station_ids: set[str] | None,
) -> None:
    """Refuse an observed series that cannot be compared with what the run samples.

    Every evaluation aligns the observed series with the table its own
    simulation wrote, so a series that shares no step or no station with that
    table makes every evaluation fail. The mismatch is the same for every
    candidate, so it is settled here, in the parent, before a single model run
    is spent on it.

    The compared steps are the simulated steps, ``first_step`` to ``last_step``,
    that survive the spin-up. The stations are the ids the ``point`` and the
    ``subcatchment`` aggregations sample, the values of the sample locations
    raster; the ``zones`` aggregation remaps the zone ids to ``1..N`` at run
    time (the mapping is written to ``zones_mapping.csv``), so the parent cannot
    know the ids of its stations and the station check is skipped for it.

    :param observed: The observed series, as the parent read it.
    :type observed: rubem.calibration.objective.Series

    :param first_step: Number of the first simulated step.
    :type first_step: int

    :param last_step: Number of the last simulated step.
    :type last_step: int

    :param spinup_steps: Number of initial time steps excluded from the
        efficiency.
    :type spinup_steps: int

    :param aggregation: The aggregation the time series of the run use.
    :type aggregation: Aggregation

    :param station_ids: The ids of the stations the run will sample, or ``None``
        when they are not known before the run.
    :type station_ids: set[str] | None

    :raises CalibrationError: If no observed step is compared, or if no observed
        station id is one of the stations of the run.
    """
    compared_steps = {step for step in range(first_step, last_step + 1) if step > spinup_steps}
    observed_steps = {int(step) for step in np.asarray(observed.steps).tolist()}
    if not compared_steps & observed_steps:
        raise CalibrationError(
            f"The observed series covers the step(s) {min(observed_steps)} to "
            f"{max(observed_steps)}, and the configuration simulates the step(s) "
            f"{first_step} to {last_step}, of which the {spinup_steps} spin-up step(s) "
            "are excluded from the efficiency: the two series would have no time step "
            "in common and every evaluation would fail."
        )

    if aggregation is Aggregation.ZONES or station_ids is None:
        return

    observed_ids = set(observed.stations)
    if not observed_ids & station_ids:
        raise CalibrationError(
            f"The observed series has the station(s) {', '.join(sorted(observed_ids)) or 'none'} "
            f"and the configuration samples the station(s) "
            f"{', '.join(sorted(station_ids)) or 'none'}: the two series would have no "
            "station in common and every evaluation would fail."
        )

    foreign = sorted(observed_ids - station_ids)
    if foreign:
        logger.warning(
            "The observed series has %d station(s) the configuration does not sample "
            "(%s); they are ignored by the calibration.",
            len(foreign),
            ", ".join(foreign),
        )


def _observed_window(observed: Series, compared_steps: list[int]) -> np.ndarray:
    """Return the rows of the observed series that fall on the compared steps."""
    steps = np.asarray(observed.steps, dtype=np.int64)
    return np.flatnonzero(np.isin(steps, np.asarray(compared_steps, dtype=np.int64)))


def _in_selection(station: str, stations: tuple[str, ...] | None) -> str:
    """Return whether a station enters the objective, as the tables spell it."""
    return "true" if stations is None or station in stations else "false"


def _write_observed_csv(
    path: Path,
    observed: Series,
    compared_steps: list[int],
    stations: tuple[str, ...] | None,
) -> None:
    """Write what the observations offer on the compared steps, one row per station.

    The row of a station carries how many of the compared steps it observes
    (``pairs_in_window``), how many values on those steps the mask of
    :func:`rubem.calibration.objective.valid_mask` rejected as gaps
    (``dropped``, the negative values among them) and the summary statistics of
    the values that were kept. It is written before the search: a station whose
    gauge is nearly empty over the simulated window explains a mean efficiency
    afterwards, and it is cheaper to read it first.
    """
    window = _observed_window(observed, compared_steps)
    with path.open("w", encoding="utf-8", newline="") as table:
        writer = csv.writer(table, delimiter=STATION_SEPARATOR)
        writer.writerow(OBSERVED_COLUMNS)
        for station in sorted(observed.stations):
            values = np.asarray(observed.stations[station], dtype=np.float64)[window]
            mask = valid_mask(values)
            kept = values[mask]
            writer.writerow(
                [
                    station,
                    _in_selection(station, stations),
                    int(kept.size),
                    int(values.size - kept.size),
                    _cell(float(np.mean(kept)) if kept.size else None),
                    _cell(float(np.std(kept, ddof=1)) if kept.size > 1 else None),
                    _cell(float(np.min(kept)) if kept.size else None),
                    _cell(float(np.max(kept)) if kept.size else None),
                ]
            )


def _report_observed_coverage(
    observed: Series,
    compared_steps: list[int],
    stations: tuple[str, ...] | None,
) -> None:
    """Log how much of the compared window the observations cover, per station."""
    window = _observed_window(observed, compared_steps)
    covered = np.asarray(observed.steps, dtype=np.int64)[window]
    if covered.size:
        span = f"the step(s) {int(covered.min())} to {int(covered.max())}"
    else:
        span = "no step of it"
    progress.info(
        "The calibration compares %d time step(s); the observed series covers %d of them, %s.",
        len(compared_steps),
        int(covered.size),
        span,
    )
    for station in sorted(observed.stations):
        values = np.asarray(observed.stations[station], dtype=np.float64)[window]
        kept = int(np.count_nonzero(valid_mask(values)))
        progress.info(
            "Station %s%s: %d observed value(s) on the compared steps, %d dropped as gaps.",
            station,
            "" if stations is None or station in stations else " (not in the objective)",
            kept,
            int(values.size) - kept,
        )


def _write_stations_csv(
    path: Path,
    station_metrics: dict[str, Any],
    stations: tuple[str, ...] | None,
) -> None:
    """Write the goodness of fit of the best candidate, one row per station.

    The statistics are the ones its own evaluation recorded, not a
    recomputation: the table and the record of that evaluation therefore always
    agree. A station outside the selection is measured like any other and
    marked as such, which is what makes the stations left out of the objective a
    validation of the calibration.
    """
    with path.open("w", encoding="utf-8", newline="") as table:
        writer = csv.writer(table, delimiter=STATION_SEPARATOR)
        writer.writerow(STATION_COLUMNS)
        for station in sorted(station_metrics):
            measured = station_metrics[station] or {}
            writer.writerow(
                [
                    station,
                    _in_selection(station, stations),
                    int(measured.get("pairs") or 0),
                    # The remaining columns are the statistics, under the very
                    # names the record spells them with.
                    *(_cell(measured.get(name)) for name in STATION_COLUMNS[3:]),
                ]
            )


def _write_best_series(
    path: Path,
    *,
    document: dict,
    base_dir: str | None,
    parameters: dict[str, float],
    modflow: ModflowCatalog | None,
    variable: str,
    observed: Series,
    spinup_steps: int,
    temp_dir: Path,
    workers: int,
    evaluations_csv: Path,
) -> None:
    """Run the best candidate once more and write its series beside the observed one.

    The search keeps no output: every evaluation writes into a temporary
    directory that is removed when it ends, which is what keeps a calibration of
    thousands of runs from filling a disk. The candidate that won is therefore
    run one last time, in a worker of its own, so that the series behind the
    reported efficiency can be plotted against the observations. The steps and
    the stations of the table are the ones the objective compared, from the same
    alignment, and a value either series does not offer is left as an empty
    cell.

    :raises CalibrationError: If the run of the best candidate failed.
    """
    output_dir = Path(tempfile.mkdtemp(prefix="best-", dir=str(temp_dir)))
    executor = _pool(workers)
    try:
        table = executor.submit(
            simulate_best, document, base_dir, parameters, str(output_dir), variable, modflow
        ).result()
        simulated = read_series(table)
    except Exception as error:
        raise CalibrationError(
            "The best candidate of the search could not be run again to keep its series: "
            f"{type(error).__name__}: {error}. The calibration itself finished; its "
            f"evaluations are in {evaluations_csv}."
        ) from error
    finally:
        executor.shutdown(wait=True)
        shutil.rmtree(output_dir, ignore_errors=True)

    alignment = align_series(simulated, observed, spinup_steps)
    columns = [
        column
        for station in alignment.stations
        for column in (f"observed_{station}", f"simulated_{station}")
    ]
    with path.open("w", encoding="utf-8", newline="") as best:
        writer = csv.writer(best, delimiter=STATION_SEPARATOR)
        writer.writerow(["step", *columns])
        for row, step in enumerate(alignment.steps.tolist()):
            cells: list[str] = []
            for station in alignment.stations:
                cells.append(
                    _observation(observed.stations[station], alignment.observed_index[row])
                )
                cells.append(
                    _observation(simulated.stations[station], alignment.simulated_index[row])
                )
            writer.writerow([int(step), *cells])


def _observation(values: np.ndarray, row: int) -> str:
    """Return one value of a series, or an empty cell when the mask rejects it."""
    value = float(np.asarray(values, dtype=np.float64)[row])
    return _cell(value) if bool(valid_mask(np.asarray([value]))[0]) else ""


def _population_size(settings: CalibrationSettings, dimension: int = len(FREE_PARAMETERS)) -> int:
    """Return the number of population members the search will use.

    The arithmetic mirrors SciPy's: an explicit population is used as it is, a
    named initialization gives ``max(5, popsize * dimension)`` members, with
    ``dimension`` the number of free parameters, and ``sobol`` alone rounds that
    up to the next power of two.
    """
    if not isinstance(settings.init, str):
        return int(np.shape(settings.init)[0])
    members = max(5, settings.popsize * dimension)
    if settings.init == "sobol":
        return 1 << (members - 1).bit_length()
    return members


def _record_paths(evaluations_dir: Path) -> list[Path]:
    """Return the JSON records written so far, without the files still being staged."""
    return sorted(path for path in evaluations_dir.glob("*.json") if not path.name.startswith("."))


def _read_records(evaluations_dir: Path) -> list[dict[str, Any]]:
    """Read every JSON record of the run, in the order of :func:`_record_order`.

    A record that cannot be read is reported and skipped: an unreadable record
    of one evaluation must not hide the result of all the others.
    """
    records = []
    for path in _record_paths(evaluations_dir):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as error:
            logger.warning("Skipping the unreadable evaluation record %s: %s", path, error)
    records.sort(key=_record_order)
    return records


def _record_order(record: dict[str, Any]) -> tuple[tuple[float, ...], str]:
    """Return the sort key of a record: its parameters, then its identifier.

    The records are not ordered by the moment they were written: the workers run
    in parallel, so that order changes from run to run. Ordering them by the
    candidate they evaluated takes that scheduling order out of
    ``evaluations.csv``. It does not make the table reproducible on its own: the
    ``id``, ``pid`` and ``elapsed_seconds`` columns differ between two runs, and
    from the first generation on the selection reads the objective values, so
    two runs of one seed evaluate the same candidates only when the simulation
    itself is reproducible (on the real basins that requires a fixed
    ``RASTERS.ldd``, since ``lddcreate`` does not always derive the same
    directions twice; see the note on the LDD raster in the user guide). The
    identifier only separates two evaluations of the very same candidate.
    """
    parameters = record.get("parameters") or {}
    names = (
        *CALIBRATION_PARAMETERS,
        *sorted(name for name in parameters if name.startswith(MODFLOW_PREFIX)),
    )
    values = tuple(float(parameters.get(name, math.inf)) for name in names)
    return values, str(record.get("id", ""))


def _evaluation_columns(space: DecisionSpace) -> tuple[str, ...]:
    """Return the columns of ``evaluations.csv``: the MODFLOW parameters follow ``x``."""
    position = EVALUATION_COLUMNS.index(CALIBRATION_PARAMETERS[-1]) + 1
    return (
        *EVALUATION_COLUMNS[:position],
        *space.modflow_names,
        *EVALUATION_COLUMNS[position:],
    )


def _write_evaluations_csv(
    path: Path, records: list[dict[str, Any]], columns: tuple[str, ...]
) -> None:
    """Write one row per evaluation, in ``columns``, which :func:`_evaluation_columns` gives.

    The columns are always given: a default of :data:`EVALUATION_COLUMNS` would
    silently drop the MODFLOW parameters of a run on a path that forgot them.
    """
    names = columns[columns.index(CALIBRATION_PARAMETERS[0]) : columns.index("nse")]
    with path.open("w", encoding="utf-8", newline="") as table:
        writer = csv.writer(table)
        writer.writerow(columns)
        for record in records:
            parameters = record.get("parameters") or {}
            writer.writerow(
                [
                    record.get("id", ""),
                    record.get("pid", ""),
                    record.get("started_at", ""),
                    *(_cell(parameters.get(name)) for name in names),
                    _cell(record.get("nse")),
                    _cell(record.get("objective")),
                    _cell(record.get("elapsed_seconds")),
                    record.get("error") or "",
                ]
            )


def _cell(value) -> str:
    """Return a numeric cell with full precision, or an empty cell for a missing value."""
    return "" if value is None else repr(float(value))


def _best_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the record of the lowest objective among those that were evaluated.

    A record without an objective is not a candidate for the best one: the
    records are written by other processes, and the parent reads whatever is in
    the directory rather than assuming every file there is complete.
    """
    evaluated = [
        record
        for record in records
        if not record.get("error") and record.get("objective") is not None
    ]
    if not evaluated:
        return None
    return min(evaluated, key=lambda record: float(record["objective"]))


def _first_error(records: list[dict[str, Any]]) -> str:
    """Return the error of the first record that carries one."""
    return next((str(record["error"]) for record in records if record.get("error")), "unknown")


def _write_result_json(
    path: Path,
    *,
    best_parameters: dict[str, float],
    best_nse: float | None,
    best_objective: float,
    optimum,
    settings: CalibrationSettings,
    space: DecisionSpace,
    workers: int,
    temp_dir: Path,
    population_size: int,
    artifacts: dict[str, str],
) -> None:
    """Write the summary of the calibration.

    The ``artifacts`` object names every file the run wrote next to this one, so
    that the summary is the one file a reader has to open to find the rest.
    """
    document = {
        "best_parameters": best_parameters,
        "best_nse": best_nse,
        "best_objective": best_objective,
        "nfev": int(optimum.nfev),
        "nit": int(optimum.nit),
        "success": bool(optimum.success),
        "message": str(optimum.message),
        "population_size": population_size,
        "settings": _settings_document(settings, space, workers, temp_dir),
        "artifacts": artifacts,
    }
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _settings_document(
    settings: CalibrationSettings, space: DecisionSpace, workers: int, temp_dir: Path
) -> dict[str, Any]:
    """Return the settings as JSON-able data, resolved the way the run used them.

    The number of workers, the temporary directory and the bounds are the values
    the run actually used, not the ``None`` the caller may have left them at, so
    that the summary describes a calibration that can be repeated: the bounds are
    the effective ones, one entry per searched parameter, the ranges of the
    application settings narrowed by whatever the caller asked for, and the
    caller's own bound for a MODFLOW parameter.
    """
    init = settings.init if isinstance(settings.init, str) else np.asarray(settings.init).tolist()
    return {
        "variable": settings.variable,
        "spinup_steps": settings.spinup_steps,
        "maxiter": settings.maxiter,
        "popsize": settings.popsize,
        "seed": settings.seed,
        "workers": workers,
        "temp_dir": str(temp_dir),
        "init": init,
        "strategy": settings.strategy,
        "mutation": list(settings.mutation),
        "recombination": settings.recombination,
        "polish": settings.polish,
        "bounds": {
            name: [minimum, maximum]
            for name, (minimum, maximum) in zip(space.free_names, space.bounds, strict=True)
        },
        "fixed": dict(space.fixed),
        "stations": list(settings.stations) if settings.stations is not None else None,
        "allow_blocking_problems": settings.allow_blocking_problems,
    }


def _write_calibrated_config(
    path: Path,
    configuration,
    file_v1: ModelConfigurationFileV1,
    best_parameters: dict[str, float],
    modflow: ModflowCatalog | None = None,
) -> None:
    """Write the calibrated configuration in the format the input was written in.

    The document goes through the configuration models, so what is written is a
    configuration the loader accepts. Its paths are the ones the loader resolved,
    which are absolute even when the input file wrote them relative to its own
    directory. The MODFLOW values of the best candidate replace the ones of its
    section, and a conductivity table with a calibrated class is written next
    to the configuration as ``<name>-kh<n>.tbl``, ``<name>`` being the name of
    the configuration without its extension.
    """
    calibrated = file_v1.model_copy(
        update={
            "model_calibration_parameters": type(file_v1.model_calibration_parameters)(
                alpha=best_parameters["alpha"],
                b=best_parameters["beta"],
                w_1=best_parameters["w_1"],
                w_2=best_parameters["w_2"],
                w_3=best_parameters["w_3"],
                rcd=best_parameters["rcd"],
                f=best_parameters["f"],
                alpha_gw=best_parameters["alpha_gw"],
                x=best_parameters["x"],
            )
        }
    )
    if modflow is not None:
        patched = calibrated.to_dict()
        modflow.apply(patched, best_parameters, path.parent, table_prefix=f"{path.stem}-kh")
        calibrated = ModelConfigurationFileV1.model_validate(patched)
    document = (
        calibrated.to_dict()
        if configuration.file_v1 is not None
        else calibrated.to_legacy().to_dict()
    )
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _modflow_catalog(configuration) -> ModflowCatalog | None:
    """Return the MODFLOW parameters of a configuration, ``None`` when it does not enable MODFLOW.

    :raises CalibrationError: If a conductivity lookup table cannot be read,
        which the validation reports as blocking and
        ``allow_blocking_problems`` may have let through.
    """
    if not configuration.modflow_enabled:
        return None
    try:
        return catalog(configuration.modflow)
    except (OSError, LookupTableError) as error:
        raise CalibrationError(
            f"The MODFLOW parameters of the configuration cannot be read: {error}"
        ) from error
