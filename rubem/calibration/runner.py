"""The calibration itself: a differential evolution over the free parameters.

:func:`calibrate` loads and validates the configuration once, reads the observed
series, and hands SciPy's ``differential_evolution`` a process pool whose workers
run one model evaluation each and exit. The pool is the isolation layer: PCRaster
keeps its clone and its raster memory process-wide, so a worker that is reused
would accumulate the state of every run it made; ``spawn`` with
``max_tasks_per_child=1`` gives every evaluation a fresh interpreter.

The run directory receives three artifacts: ``evaluations.csv``, one row per
evaluation, ``result.json``, the best candidate and the settings that found it,
and ``<configuration>-calibrated.json``, the calibrated configuration in the
format the input was written in. The rows of the table are ordered by the
candidate they evaluated and not by the moment they were written, so that two
calibrations of one configuration with one seed produce the same table.

Number of evaluations
    The population of a ``sobol`` initialization is ``max(5, popsize * 8)``
    rounded up to the next power of two, since a Sobol' sequence is balanced
    only over a power-of-two sample: with the default ``popsize`` of 15 that is
    128 members, so a calibration costs one model run per member and per
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
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .._paths import PathInput, as_path
from ..configuration.model_configuration_file_v1 import (
    VARIABLE_IDS,
    Aggregation,
    ModelConfigurationFileV1,
)
from ._worker import _INADMISSIBLE_ERROR, EvaluationContext, evaluate
from .objective import read_series
from .parameters import (
    CALIBRATION_PARAMETERS,
    FREE_PARAMETERS,
    bounds,
    parameters_to_vector,
    vector_to_parameters,
    weights_constraint,
)

logger = logging.getLogger(__name__)

EVALUATIONS_DIRNAME = "evaluations"
"""Name of the directory under the run directory that collects the JSON records."""

EVALUATIONS_CSV = "evaluations.csv"
RESULT_JSON = "result.json"

EVALUATION_COLUMNS = (
    "id",
    "pid",
    *CALIBRATION_PARAMETERS,
    "nse",
    "objective",
    "elapsed_seconds",
    "error",
)
"""The columns of ``evaluations.csv``, one row per evaluation."""


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
        (``sobol`` by default) or an explicit ``(S, 8)`` array with ``S > 4``.
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


@dataclass(frozen=True)
class CalibrationResult:
    """What a finished calibration found and where it wrote it.

    :param best_parameters: The nine calibration parameters of the best
        candidate, the derived ``w_3`` included.
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
        """Log the generation, the best objective so far and the records written.

        SciPy inspects the signature of the callback and passes the
        intermediate result by keyword under exactly this name; returning
        ``True`` would halt the search, so the callback always returns
        ``False``.
        """
        self.generations = int(getattr(intermediate_result, "nit", 0) or 0)
        logger.info(
            "Generation %d: best objective %.6g, %d evaluation(s) recorded.",
            self.generations,
            float(intermediate_result.fun),
            len(_record_paths(self.evaluations_dir)),
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
        cannot be calibrated as asked, or if every evaluation of the run failed.
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

    config_file = as_path(config_path).absolute()
    configuration = Model.from_file(config_file, validate_input=True).configuration
    file_v1 = _as_v1(configuration)
    _check_sample_locations(configuration, file_v1)

    observed = read_series(observed_path)
    x0 = parameters_to_vector(configuration.calibration_parameters.model_dump())

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
    )

    planned_members = _population_size(settings)
    logger.info(
        "Calibrating %d free parameter(s) with %d population member(s) per generation and "
        "at most %d generation(s): up to %d model run(s), on %d worker process(es).",
        len(FREE_PARAMETERS),
        planned_members,
        settings.maxiter,
        planned_members * (settings.maxiter + 1),
        workers,
    )

    progress = _Progress(evaluations_dir)
    executor = ProcessPoolExecutor(
        max_workers=workers,
        mp_context=multiprocessing.get_context("spawn"),
        max_tasks_per_child=1,
        initializer=_prepare_worker,
    )
    try:
        optimum = differential_evolution(
            functools.partial(evaluate, context=context),
            bounds(),
            strategy=settings.strategy,
            maxiter=settings.maxiter,
            popsize=settings.popsize,
            mutation=settings.mutation,
            recombination=settings.recombination,
            rng=settings.seed,
            polish=settings.polish,
            init=settings.init,
            x0=x0,
            updating="deferred",
            workers=executor.map,
            constraints=weights_constraint(),
            callback=progress,
        )
    finally:
        executor.shutdown(wait=True)

    records = _read_records(evaluations_dir)
    evaluations_csv = run_directory / EVALUATIONS_CSV
    _write_evaluations_csv(evaluations_csv, records)

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

    best_parameters = vector_to_parameters(optimum.x)
    best_objective = float(optimum.fun)
    result_json = run_directory / RESULT_JSON
    calibrated_config = run_directory / f"{config_file.stem}-calibrated.json"
    _write_result_json(
        result_json,
        best_parameters=best_parameters,
        best_nse=best["nse"],
        best_objective=best_objective,
        optimum=optimum,
        settings=settings,
        workers=workers,
        temp_dir=temp_dir,
        population_size=population_size,
    )
    _write_calibrated_config(calibrated_config, configuration, file_v1, best_parameters)

    logger.info(
        "Calibration finished after %d evaluation(s) in %d generation(s): best objective %.6g.",
        int(optimum.nfev),
        int(optimum.nit),
        best_objective,
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


def _population_size(settings: CalibrationSettings) -> int:
    """Return the number of population members the search will use.

    The arithmetic mirrors SciPy's: an explicit population is used as it is, a
    named initialization gives ``max(5, popsize * 8)`` members, and ``sobol``
    rounds that up to the next power of two.
    """
    if not isinstance(settings.init, str):
        return int(np.shape(settings.init)[0])
    members = max(5, settings.popsize * len(FREE_PARAMETERS))
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
    candidate they evaluated makes ``evaluations.csv`` a function of the seed
    alone, so two calibrations of the same configuration with the same seed
    produce the same table and can be compared line by line. The identifier only
    separates two evaluations of the very same candidate.
    """
    parameters = record.get("parameters") or {}
    values = tuple(float(parameters.get(name, math.inf)) for name in CALIBRATION_PARAMETERS)
    return values, str(record.get("id", ""))


def _write_evaluations_csv(path: Path, records: list[dict[str, Any]]) -> None:
    """Write one row per evaluation, in the columns of :data:`EVALUATION_COLUMNS`."""
    with path.open("w", encoding="utf-8", newline="") as table:
        writer = csv.writer(table)
        writer.writerow(EVALUATION_COLUMNS)
        for record in records:
            parameters = record.get("parameters") or {}
            writer.writerow(
                [
                    record.get("id", ""),
                    record.get("pid", ""),
                    *(_cell(parameters.get(name)) for name in CALIBRATION_PARAMETERS),
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
    """Return the record of the lowest objective among those that were evaluated."""
    evaluated = [record for record in records if not record.get("error")]
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
    workers: int,
    temp_dir: Path,
    population_size: int,
) -> None:
    """Write the summary of the calibration."""
    document = {
        "best_parameters": best_parameters,
        "best_nse": best_nse,
        "best_objective": best_objective,
        "nfev": int(optimum.nfev),
        "nit": int(optimum.nit),
        "success": bool(optimum.success),
        "message": str(optimum.message),
        "population_size": population_size,
        "settings": _settings_document(settings, workers, temp_dir),
    }
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _settings_document(
    settings: CalibrationSettings, workers: int, temp_dir: Path
) -> dict[str, Any]:
    """Return the settings as JSON-able data, resolved the way the run used them.

    The number of workers and the temporary directory are the values the run
    actually used, not the ``None`` the caller may have left them at, so that
    the summary describes a calibration that can be repeated.
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
    }


def _write_calibrated_config(
    path: Path,
    configuration,
    file_v1: ModelConfigurationFileV1,
    best_parameters: dict[str, float],
) -> None:
    """Write the calibrated configuration in the format the input was written in.

    The document goes through the configuration models, so what is written is a
    configuration the loader accepts. Its paths are the ones the loader resolved,
    which are absolute even when the input file wrote them relative to its own
    directory.
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
    document = (
        calibrated.to_dict()
        if configuration.file_v1 is not None
        else calibrated.to_legacy().to_dict()
    )
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
