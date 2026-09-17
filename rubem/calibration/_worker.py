"""Evaluation of one candidate, the entry point the calibration workers run.

The module lives at the top level of the package and keeps its entry point,
:func:`evaluate`, at module level, because the process pool of the calibration
starts its workers with the ``spawn`` method: the child imports this module by
name to find the function it has to call, so the function must be picklable by
reference and everything it needs must travel as plain data in an
:class:`EvaluationContext`.

One evaluation builds the configuration of the candidate from the document of
the calibrated configuration, runs the model in the current process, reads the
time series it wrote and compares it with the observed series. It never calls
:meth:`rubem.api.Model.run_isolated`: the worker is already the isolation layer,
and an isolated run inside it would nest one process pool in another.

:func:`evaluate` never raises: a candidate outside the admissible region is
rejected without a run, and any failure of the run or of the evaluation is
recorded and turned into
:data:`rubem.calibration.objective.INADMISSIBLE_OBJECTIVE`, so that one failing
candidate does not end the calibration. :func:`simulate_best`, which the search
calls once at the end to keep the series of the candidate it chose, does raise:
there is one named candidate and nothing to rank a failure behind.
"""

import copy
import dataclasses
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ..configuration.model_configuration_file_v1 import VARIABLE_IDS
from .objective import (
    INADMISSIBLE_OBJECTIVE,
    Series,
    StationMetrics,
    evaluate_series,
    objective,
    read_series,
)
from .parameters import DecisionSpace, decision_space

logger = logging.getLogger(__name__)

_INADMISSIBLE_ERROR = "inadmissible"
"""The error recorded for a candidate that was rejected without being run."""


@dataclass(frozen=True)
class EvaluationContext:
    """Everything an evaluation needs, as data that crosses to a worker process.

    :param document: The calibrated configuration as a format 1.0 document,
        with its paths already anchored.
    :type document: dict

    :param base_dir: Directory the relative paths of the document are anchored
        on, ``None`` when they are absolute already.
    :type base_dir: str | None

    :param variable: Id of the output variable the efficiency is computed on
        (``arn``, the accumulated total runoff, by default).
    :type variable: str

    :param observed: The observed series, read once by the parent.
    :type observed: rubem.calibration.objective.Series

    :param spinup_steps: Number of initial time steps excluded from the
        efficiency.
    :type spinup_steps: int

    :param temp_dir: Directory the per-evaluation output directories are
        created in and removed from.
    :type temp_dir: str

    :param evaluations_dir: Directory the JSON record of every evaluation is
        written to.
    :type evaluations_dir: str

    :param validate_input: Whether every evaluation revalidates the input files
        and their content. ``False`` by default: the parent validated them once
        before the calibration started, and they do not change during it.
    :type validate_input: bool

    :param space: The decision vector of the run, which turns a candidate into
        the nine parameters of the model. Defaults to the whole search, without
        fixed parameters and without narrowed bounds.
    :type space: rubem.calibration.parameters.DecisionSpace

    :param stations: Ids of the stations the objective averages. ``None``, the
        default, averages every station the two series share; the others are
        measured either way.
    :type stations: tuple[str, ...] | None
    """

    document: dict
    base_dir: str | None
    variable: str
    observed: Series
    spinup_steps: int
    temp_dir: str
    evaluations_dir: str
    validate_input: bool = False
    space: DecisionSpace = field(default_factory=decision_space)
    stations: tuple[str, ...] | None = None


def evaluate(vector: Sequence[float] | np.ndarray, context: EvaluationContext) -> float:
    """Run one candidate and return the objective value of its simulation.

    A candidate outside the admissible region is rejected before any model run
    and recorded with the error ``inadmissible``. Otherwise the model is run in
    the current process, into a temporary output directory that is removed
    again, and the efficiency of the resulting time series is turned into the
    objective. Every evaluation, successful or not, leaves one JSON record in
    the evaluations directory of the context.

    :param vector: The candidate, the free values in the order of the
        :attr:`~rubem.calibration.parameters.DecisionSpace.free_names` of the
        decision space of the context.
    :type vector: collections.abc.Sequence[float] | numpy.ndarray

    :param context: What the evaluation runs against.
    :type context: EvaluationContext

    :return: The objective value, or
        :data:`rubem.calibration.objective.INADMISSIBLE_OBJECTIVE` when the
        candidate was rejected or its evaluation failed.
    :rtype: float
    """
    started_at = datetime.now(UTC).isoformat()
    started = time.perf_counter()
    try:
        parameters = context.space.to_parameters(vector)
    except ValueError as error:
        _write_record(
            context, started_at, {}, None, {}, INADMISSIBLE_OBJECTIVE, 0.0, _describe(error)
        )
        return INADMISSIBLE_OBJECTIVE

    if not context.space.is_admissible(vector):
        logger.debug("Rejecting an inadmissible candidate without running the model.")
        _write_record(
            context,
            started_at,
            parameters,
            None,
            {},
            INADMISSIBLE_OBJECTIVE,
            time.perf_counter() - started,
            _INADMISSIBLE_ERROR,
        )
        return INADMISSIBLE_OBJECTIVE

    output_dir = tempfile.mkdtemp(prefix="evaluation-", dir=context.temp_dir)
    try:
        nse, metrics = _run_and_evaluate(context, parameters, output_dir)
    except Exception as error:
        # One failing candidate must not end the calibration: it is recorded and
        # ranked behind every candidate that was actually evaluated.
        logger.warning("The evaluation of a candidate failed: %s", error)
        _write_record(
            context,
            started_at,
            parameters,
            None,
            {},
            INADMISSIBLE_OBJECTIVE,
            time.perf_counter() - started,
            _describe(error),
        )
        return INADMISSIBLE_OBJECTIVE
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)

    value = objective(nse)
    _write_record(
        context,
        started_at,
        parameters,
        nse,
        metrics,
        value,
        time.perf_counter() - started,
        None,
    )
    return value


def simulate_best(
    document: dict,
    base_dir: str | None,
    parameters: dict[str, float],
    output_dir: str,
    variable: str,
) -> str:
    """Run one candidate and keep what it wrote.

    This is how the calibration obtains the series of the candidate it chose:
    the run is the very run an evaluation makes, from the same derived
    configuration, but the output directory is left in place so that the table
    can be read afterwards. It lives at module level and takes plain data for
    the same reason :func:`evaluate` does: the spawned workers import this
    module by name to find the function they have to call.

    Unlike :func:`evaluate` it raises: the caller asked for one named
    candidate's series and has nothing to rank a failure behind.

    :param document: The calibrated configuration as a format 1.0 document.
    :type document: dict

    :param base_dir: Directory the relative paths of the document are anchored
        on, ``None`` when they are absolute already.
    :type base_dir: str | None

    :param parameters: The nine calibration parameters of the candidate.
    :type parameters: dict[str, float]

    :param output_dir: Directory the run writes into. It is not removed.
    :type output_dir: str

    :param variable: Id of the output variable the table is wanted for.
    :type variable: str

    :return: The path of the CSV table the run wrote for ``variable``.
    :rtype: str

    :raises RuntimeError: If the run wrote no CSV table for the variable.
    """
    from ..api import Model

    derived = _document_for(document, variable, parameters, output_dir)
    result = Model.from_config(derived, validate_input=False, base_dir=base_dir).run()
    return str(_time_series_table(result, variable))


def _run_and_evaluate(
    context: EvaluationContext,
    parameters: dict[str, float],
    output_dir: str,
) -> tuple[float, dict[str, StationMetrics]]:
    """Run the candidate and return its mean efficiency and the statistics per station."""
    from ..api import Model

    document = _derived_document(context, parameters, output_dir)
    result = Model.from_config(
        document, validate_input=context.validate_input, base_dir=context.base_dir
    ).run()
    simulated = read_series(_time_series_table(result, context.variable))
    return evaluate_series(simulated, context.observed, context.spinup_steps, context.stations)


def _time_series_table(result, variable: str) -> Path:
    """Return the CSV table the run wrote for ``variable``.

    :raises RuntimeError: If the run reports no table for the variable.
    """
    tables = result.time_series.get(variable, ())
    for path in tables:
        if path.suffix.lower() == ".csv":
            return path
    raise RuntimeError(
        f"The run wrote no CSV time series for the variable '{variable}'; it reports "
        f"{', '.join(str(path) for path in tables) or 'no table'}."
    )


def _derived_document(
    context: EvaluationContext,
    parameters: dict[str, float],
    output_dir: str,
) -> dict:
    """Return the configuration document of one candidate of an evaluation."""
    return _document_for(context.document, context.variable, parameters, output_dir)


def _document_for(
    base_document: dict,
    variable: str,
    parameters: dict[str, float],
    output_dir: str,
) -> dict:
    """Return the configuration document of one candidate.

    The calibrated document is copied and four things are changed: the
    calibration parameters become the candidate's, the outputs go to the
    directory of the run, every raster series is disabled (an evaluation reads
    no raster, and writing them would dominate its cost) and the time series are
    reduced to the calibrated variable, as CSV. The aggregation the user
    configured is kept, since it decides which areas the observed stations
    correspond to.
    """
    document = copy.deepcopy(base_document)
    document["model_calibration_parameters"] = {
        "alpha": parameters["alpha"],
        "b": parameters["beta"],
        "w_1": parameters["w_1"],
        "w_2": parameters["w_2"],
        "w_3": parameters["w_3"],
        "rcd": parameters["rcd"],
        "f": parameters["f"],
        "alpha_gw": parameters["alpha_gw"],
        "x": parameters["x"],
    }
    output = document.setdefault("model_simulation_output", {})
    previous_rasters = output.get("raster_series", {})
    previous_samples = output.get("time_series_samples", {})
    output["dir_path"] = output_dir
    output["raster_series"] = {
        "no_data_value": previous_rasters.get("no_data_value", -9999),
        "formats": [],
    }
    output["time_series_samples"] = {
        **dict.fromkeys(VARIABLE_IDS, False),
        variable: True,
        "formats": ["CSV"],
        "aggregation": previous_samples.get("aggregation", "point"),
    }
    return document


def _describe(error: BaseException) -> str:
    """Return the recorded description of an exception: its type and its message."""
    return f"{type(error).__name__}: {error}"


def _write_record(
    context: EvaluationContext,
    started_at: str,
    parameters: dict[str, float],
    nse: float | None,
    metrics: dict[str, StationMetrics],
    value: float,
    elapsed_seconds: float,
    error: str | None,
) -> None:
    """Write the JSON record of one evaluation, atomically.

    Every worker writes into the same directory while the parent may be reading
    it, so a record is written to a temporary file next to its destination and
    renamed onto it: a reader either does not see the record yet or sees it
    whole. The name is a fresh UUID, so two workers never collide.

    The record carries the goodness of fit of every station under
    ``station_metrics`` and, under ``station_nse``, the efficiencies alone,
    taken from the very same statistics so that the two can never disagree.
    ``started_at`` is the wall-clock moment the evaluation began, in UTC: the
    records are consolidated in the order of the candidates they evaluated, and
    this is what puts them back in the order they were made in.
    """
    station_metrics = {
        station: dataclasses.asdict(measured) for station, measured in metrics.items()
    }
    record = {
        "id": uuid.uuid4().hex,
        "pid": os.getpid(),
        "started_at": started_at,
        "parameters": parameters,
        "nse": nse,
        "station_nse": {station: measured["nse"] for station, measured in station_metrics.items()},
        "station_metrics": station_metrics,
        "objective": value,
        "elapsed_seconds": elapsed_seconds,
        "error": error,
    }
    directory = Path(context.evaluations_dir)
    target = directory / f"{record['id']}.json"
    handle, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(record, file)
        Path(temporary).replace(target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
