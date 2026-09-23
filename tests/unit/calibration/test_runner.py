"""The calibration runner: a small deterministic differential evolution and its artifacts."""

import csv
import inspect
import json
import logging
import multiprocessing
import os
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import numpy as np
import pytest

from rubem import _deps
from rubem.api import Model
from rubem.calibration import runner
from rubem.calibration.objective import Series
from rubem.calibration.parameters import (
    CALIBRATION_PARAMETERS,
    FREE_PARAMETERS,
    bounds,
    parameters_to_vector,
)
from rubem.calibration.runner import (
    EVALUATION_COLUMNS,
    OBSERVED_COLUMNS,
    STATION_COLUMNS,
    CalibrationError,
    CalibrationSettings,
    _check_observed_series,
    _population_size,
    _Progress,
    _station_ids,
    calibrate,
)
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.model_configuration_file import ModelConfigurationFile
from rubem.configuration.model_configuration_file_v1 import (
    Aggregation,
    ModelConfigurationFileV1,
)
from tests.helpers.config import REPO_ROOT
from tests.helpers.synthetic import (
    MODFLOW_HEAD,
    MODFLOW_KH_TABLE,
    write_grid_map,
    write_modflow_inputs,
    write_synthetic_dataset,
)

# SciPy is the optional ``rubem[calibration]`` extra, and an environment
# without it (the frozen one of the byte-exact job, for instance) still
# collects this file; the whole module is skipped there instead of failing to
# import.
scipy_optimize = pytest.importorskip("scipy.optimize")

TIMESTEPS = 3

# Five admissible members, the second one far from the configuration under
# calibration. SciPy replaces the first member with x0, so the configuration
# itself is always part of the initial population.
INIT = np.array(
    [
        [1.0, 0.20, 0.20, 0.20, 2.0, 0.20, 0.20, 0.20],
        [9.5, 0.90, 0.10, 0.80, 9.0, 0.90, 0.90, 0.90],
        [2.0, 0.30, 0.40, 0.40, 3.0, 0.30, 0.30, 0.30],
        [6.0, 0.70, 0.25, 0.25, 7.0, 0.70, 0.70, 0.70],
        [3.0, 0.40, 0.50, 0.30, 4.0, 0.40, 0.40, 0.40],
    ]
)


class Dataset:
    """The synthetic dataset, its configuration file and the series a plain run wrote."""

    def __init__(self, tmp_path):
        self.config = write_synthetic_dataset(str(tmp_path), timesteps=TIMESTEPS)
        self.config_file = tmp_path / "config.json"
        self.config_file.write_text(json.dumps(self.config), encoding="utf8")
        written = Model.from_config(self.config).run().time_series["arn"][0]
        self.observed = tmp_path / "observed.csv"
        shutil.copyfile(written, self.observed)
        self.run_dir = tmp_path / "calibration"
        self.temp_dir = tmp_path / "temp"
        self.parameters = ModelConfiguration(
            self.config, validate_input=False
        ).calibration_parameters.model_dump()

    def settings(self, **overrides):
        """The deterministic small search of the tests."""
        defaults = {
            "variable": "arn",
            "maxiter": 1,
            "popsize": 5,
            "seed": 1,
            "workers": 2,
            "temp_dir": str(self.temp_dir),
            "init": INIT,
            "polish": False,
        }
        return CalibrationSettings(**{**defaults, **overrides})

    def calibrate(self, observed=None, **overrides):
        return calibrate(
            self.config_file,
            observed or self.observed,
            self.run_dir,
            self.settings(**overrides),
        )


def read_evaluations(path):
    with path.open(encoding="utf-8", newline="") as table:
        return list(csv.DictReader(table))


def read_station_table(path):
    """Read one of the ``;``-separated per-station tables of a run directory."""
    with path.open(encoding="utf-8", newline="") as table:
        return list(csv.DictReader(table, delimiter=";"))


@pytest.fixture
def progress_log(caplog):
    """Capture the ``rubem.progress`` lines whatever the logging configuration is.

    The command line detaches that logger from the root one so that its lines
    are printed verbatim, and a test that ran the command line before this one
    may have left it detached; attaching the capture handler to the logger
    itself is what makes the capture independent of that.
    """
    captured = logging.getLogger("rubem.progress")
    handlers, level, propagate = captured.handlers[:], captured.level, captured.propagate
    captured.handlers = [caplog.handler]
    captured.setLevel(logging.INFO)
    captured.propagate = False
    caplog.set_level(logging.INFO)
    try:
        yield caplog
    finally:
        captured.handlers[:] = handlers
        captured.setLevel(level)
        captured.propagate = propagate


@pytest.fixture
def dataset(tmp_path):
    return Dataset(tmp_path)


@pytest.fixture(scope="class")
def calibrated(tmp_path_factory):
    """One calibration, shared by the assertions that inspect its artifacts."""
    data = Dataset(tmp_path_factory.mktemp("calibration"))
    return data, data.calibrate()


class TestCalibration:
    @pytest.mark.unit
    def test_the_configuration_that_produced_the_observations_is_the_optimum(self, calibrated):
        data, result = calibrated

        # The observed series is what the configuration itself wrote, so the
        # global optimum of the search is the configuration, with NSE 1.
        assert result.best_objective == pytest.approx(0.0, abs=1e-9)
        assert result.best_nse == pytest.approx(1.0, abs=1e-12)
        assert result.best_parameters == pytest.approx(data.parameters, abs=1e-12)
        assert set(result.best_parameters) == set(CALIBRATION_PARAMETERS)

    @pytest.mark.unit
    def test_every_evaluation_is_a_row_of_the_table(self, calibrated):
        data, result = calibrated
        rows = read_evaluations(result.evaluations_csv)

        assert list(rows[0]) == list(EVALUATION_COLUMNS)
        assert len(rows) == result.evaluations
        assert result.best_objective == pytest.approx(min(float(row["objective"]) for row in rows))
        assert {row["id"] for row in rows} == {row["id"] for row in rows if row["id"]}
        assert len(rows) >= len(INIT)
        # The linear constraint keeps the candidates whose weights do not add up
        # away from the workers, so no evaluation is ever rejected as
        # inadmissible and none of them failed.
        assert [row["error"] for row in rows if row["error"]] == []

    @pytest.mark.unit
    def test_the_evaluations_ran_in_other_processes_and_none_lingers(self, calibrated):
        _, result = calibrated
        rows = read_evaluations(result.evaluations_csv)

        pids = [int(row["pid"]) for row in rows]

        assert pids, "at least one evaluation was recorded"
        assert os.getpid() not in pids
        # One task per child: PCRaster keeps its clone and its rasters for the
        # life of the process, so no two evaluations may share one.
        assert len(set(pids)) == len(pids)
        assert multiprocessing.active_children() == []

    @pytest.mark.unit
    def test_the_summary_carries_the_settings_and_the_population_size(self, calibrated):
        data, result = calibrated
        summary = json.loads(result.result_json.read_text(encoding="utf-8"))

        assert summary["nfev"] == result.evaluations
        assert summary["nit"] == result.generations
        assert summary["population_size"] == len(INIT)
        assert summary["best_objective"] == pytest.approx(result.best_objective)
        assert summary["best_nse"] == pytest.approx(result.best_nse)
        assert summary["best_parameters"] == pytest.approx(result.best_parameters)
        assert summary["settings"]["seed"] == 1
        assert summary["settings"]["workers"] == 2
        assert summary["settings"]["variable"] == "arn"
        assert summary["settings"]["maxiter"] == 1
        assert summary["settings"]["polish"] is False
        assert summary["settings"]["temp_dir"] == str(data.temp_dir)
        assert summary["settings"]["init"] == INIT.tolist()
        assert summary["settings"]["allow_blocking_problems"] is False

    @pytest.mark.unit
    def test_the_calibrated_configuration_loads_with_the_best_parameters(self, calibrated):
        data, result = calibrated

        assert result.calibrated_config.name == "config-calibrated.json"
        configuration = ModelConfiguration(result.calibrated_config, validate_input=False)
        assert configuration.calibration_parameters.model_dump() == pytest.approx(
            result.best_parameters, abs=1e-12
        )
        document = json.loads(result.calibrated_config.read_text(encoding="utf-8"))
        assert "CALIBRATION" in document, "a legacy configuration stays legacy"

    @pytest.mark.unit
    def test_the_best_row_of_the_table_is_what_was_written_back(self, calibrated):
        _, result = calibrated
        rows = read_evaluations(result.evaluations_csv)
        best = min(rows, key=lambda row: float(row["objective"]))
        parameters = {name: float(best[name]) for name in CALIBRATION_PARAMETERS}

        # The optimum SciPy reports and the best record of the run are one and
        # the same evaluation, down to the last bit, and it is that evaluation
        # the calibrated configuration carries.
        assert float(best["objective"]) == result.best_objective
        assert float(best["nse"]) == result.best_nse
        assert parameters == result.best_parameters
        configuration = ModelConfiguration(result.calibrated_config, validate_input=False)
        assert configuration.calibration_parameters.model_dump() == pytest.approx(
            parameters, abs=1e-12
        )

    @pytest.mark.unit
    def test_the_temporary_directory_is_left_empty(self, calibrated):
        data, _ = calibrated

        assert list(data.temp_dir.iterdir()) == []

    @pytest.mark.unit
    def test_the_run_directory_holds_every_artifact(self, calibrated):
        _, result = calibrated

        assert result.run_dir.is_dir()
        assert result.evaluations_csv.is_file()
        assert result.result_json.is_file()
        assert result.calibrated_config.is_file()
        assert result.stations_csv.is_file()
        assert result.best_series.is_file()
        assert (result.run_dir / "observed.csv").is_file()
        assert result.best_series.name == "best_arn.csv"
        assert result.message
        assert result.generations == 1

    @pytest.mark.unit
    def test_the_summary_names_every_artifact_it_wrote(self, calibrated):
        _, result = calibrated
        artifacts = json.loads(result.result_json.read_text(encoding="utf-8"))["artifacts"]

        assert Path(artifacts["evaluations_csv"]) == result.evaluations_csv
        assert Path(artifacts["observed_csv"]) == result.run_dir / "observed.csv"
        assert Path(artifacts["stations_csv"]) == result.stations_csv
        assert Path(artifacts["best_series"]) == result.best_series
        assert Path(artifacts["calibrated_config"]) == result.calibrated_config

    @pytest.mark.unit
    def test_the_observations_are_summarized_before_the_search(self, calibrated):
        _, result = calibrated
        rows = read_station_table(result.run_dir / "observed.csv")

        assert list(rows[0]) == list(OBSERVED_COLUMNS)
        assert [row["station"] for row in rows] == ["1", "2"]
        for row in rows:
            # The observed file is the table the configuration itself wrote:
            # every compared step is observed and nothing is a gap.
            assert row["in_selection"] == "true"
            assert row["pairs_in_window"] == str(TIMESTEPS)
            assert row["dropped"] == "0"
            assert float(row["min"]) <= float(row["mean"]) <= float(row["max"])
            assert float(row["std"]) >= 0.0

    @pytest.mark.unit
    def test_the_stations_of_the_best_candidate_are_a_table_of_their_own(self, calibrated):
        _, result = calibrated
        rows = read_station_table(result.stations_csv)

        assert list(rows[0]) == list(STATION_COLUMNS)
        assert [row["station"] for row in rows] == ["1", "2"]
        for row in rows:
            # The optimum reproduces the observations exactly.
            assert row["in_selection"] == "true"
            assert int(row["pairs"]) == TIMESTEPS
            assert float(row["nse"]) == pytest.approx(1.0, abs=1e-12)
            assert float(row["rmse"]) == pytest.approx(0.0, abs=1e-9)
            assert float(row["r"]) == pytest.approx(1.0, abs=1e-9)
            assert float(row["mean_observed"]) == pytest.approx(float(row["mean_simulated"]))
            assert float(row["std_observed"]) == pytest.approx(float(row["std_simulated"]))

    @pytest.mark.unit
    def test_the_series_of_the_best_candidate_is_kept_beside_the_observed_one(self, calibrated):
        _, result = calibrated
        rows = read_station_table(result.best_series)

        assert list(rows[0]) == [
            "step",
            "observed_1",
            "simulated_1",
            "observed_2",
            "simulated_2",
        ]
        assert [int(row["step"]) for row in rows] == list(range(1, TIMESTEPS + 1))
        for row in rows:
            for station in ("1", "2"):
                # The best candidate is the configuration that wrote the
                # observations, so the two columns of a station are one series.
                assert float(row[f"simulated_{station}"]) == pytest.approx(
                    float(row[f"observed_{station}"]), abs=1e-9
                )

    @pytest.mark.unit
    def test_the_table_of_the_best_candidate_is_read_back_by_the_reader(self, calibrated):
        from rubem.calibration.objective import read_series

        _, result = calibrated
        table = read_series(result.best_series)

        # It is written in the layout the readers accept, header included.
        assert table.steps.tolist() == list(range(1, TIMESTEPS + 1))
        assert sorted(table.stations) == ["observed_1", "observed_2", "simulated_1", "simulated_2"]

    @pytest.mark.unit
    def test_every_row_of_the_table_carries_the_moment_it_started(self, calibrated):
        import datetime

        _, result = calibrated
        rows = read_evaluations(result.evaluations_csv)

        assert "started_at" in EVALUATION_COLUMNS
        moments = [datetime.datetime.fromisoformat(row["started_at"]) for row in rows]
        assert all(moment.tzinfo is not None for moment in moments)
        # The rows are ordered by the candidate they evaluated; the moments are
        # what puts them back in the order the evaluations were made in.
        assert sorted(moments) != [] and len(moments) == len(rows)


class _RecordingExecutor(ProcessPoolExecutor):
    """A process pool that remembers how it was built and when it was closed."""

    built: list["_RecordingExecutor"] = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.built_with = kwargs
        self.shutdowns = 0
        _RecordingExecutor.built.append(self)

    def shutdown(self, *args, **kwargs):
        self.shutdowns += 1
        super().shutdown(*args, **kwargs)


@pytest.fixture
def broken_search(monkeypatch):
    """Record what the search is given, and let it fail without running a model."""
    call = {}

    def explode(function, search_bounds, **kwargs):
        call["function"] = function
        call["bounds"] = search_bounds
        call.update(kwargs)
        raise RuntimeError("the search broke")

    _RecordingExecutor.built.clear()
    monkeypatch.setattr(scipy_optimize, "differential_evolution", explode)
    monkeypatch.setattr(runner, "ProcessPoolExecutor", _RecordingExecutor)
    return call


class TestProcessTopology:
    @pytest.mark.unit
    def test_the_pool_is_a_spawned_one_and_is_closed_when_the_search_fails(
        self, dataset, broken_search
    ):
        with pytest.raises(RuntimeError, match="the search broke"):
            dataset.calibrate()

        (executor,) = _RecordingExecutor.built
        assert executor.built_with["max_workers"] == 2
        assert executor.built_with["max_tasks_per_child"] == 1
        assert executor.built_with["mp_context"].get_start_method() == "spawn"
        # The pool is closed even though the search raised, and the map of that
        # very pool is what the search was told to evaluate with.
        assert executor.shutdowns == 1
        assert broken_search["workers"].__self__ is executor
        assert multiprocessing.active_children() == []

    @pytest.mark.unit
    def test_the_search_is_given_the_documented_arguments(self, dataset, broken_search):
        with pytest.raises(RuntimeError, match="the search broke"):
            dataset.calibrate()

        assert broken_search["bounds"] == bounds()
        assert broken_search["strategy"] == "best1exp"
        assert broken_search["maxiter"] == 1
        assert broken_search["popsize"] == 5
        assert broken_search["mutation"] == (0.5, 1.0)
        assert broken_search["recombination"] == 0.7
        assert broken_search["updating"] == "deferred"
        assert broken_search["polish"] is False
        assert broken_search["rng"] == 1
        assert broken_search["init"] is INIT
        # The configuration under calibration is the first member of the
        # population: SciPy puts x0 in place of the first row of init.
        assert broken_search["x0"] == pytest.approx(parameters_to_vector(dataset.parameters))

    @pytest.mark.unit
    def test_the_search_is_constrained_to_weights_that_add_up_to_at_most_one(
        self, dataset, broken_search
    ):
        with pytest.raises(RuntimeError, match="the search broke"):
            dataset.calibrate()

        constraint = broken_search["constraints"]
        coefficients = np.atleast_2d(constraint.A)
        expected = [
            [1.0 if name in ("w_1", "w_2") else 0.0 for name in FREE_PARAMETERS],
        ]

        assert coefficients.tolist() == expected
        assert np.atleast_1d(constraint.ub).tolist() == [1.0]
        assert np.all(np.isneginf(np.atleast_1d(constraint.lb)))


class TestProgress:
    @pytest.mark.unit
    def test_the_callback_takes_the_argument_scipy_passes_by_keyword(self):
        # SciPy reads the signature of the callback: only a callback whose one
        # parameter is called ``intermediate_result`` is given the result of the
        # generation, any other is called with the old ``(x, convergence)`` pair.
        assert set(inspect.signature(_Progress(Path())).parameters) == {"intermediate_result"}

    @pytest.mark.unit
    def test_the_callback_logs_the_generation_and_lets_the_search_go_on(
        self, tmp_path, progress_log, capfd
    ):
        evaluations = tmp_path / "evaluations"
        evaluations.mkdir()
        (evaluations / "one.json").write_text("{}", encoding="utf8")
        callback = _Progress(evaluations)

        stop = callback(scipy_optimize.OptimizeResult(fun=12.5, nit=3))

        assert stop is False, "the callback never halts the search"
        assert callback.generations == 3
        assert "Generation 3" in progress_log.text
        assert "12.5" in progress_log.text
        assert "1 evaluation" in progress_log.text
        # A record without an objective is not the best one; a callback that
        # read it as a candidate would end the search it is only watching.
        assert "best NSE n/a" in progress_log.text
        assert capfd.readouterr().out == "", "the library logs, it does not print"

    @pytest.mark.unit
    def test_the_generation_line_carries_the_best_efficiency_of_the_records(
        self, tmp_path, progress_log
    ):
        evaluations = tmp_path / "evaluations"
        evaluations.mkdir()
        for name, objective_value, nse in (("a", 4.0, 0.25), ("b", 1.0, 0.75)):
            (evaluations / f"{name}.json").write_text(
                json.dumps({"id": name, "objective": objective_value, "nse": nse, "error": None}),
                encoding="utf8",
            )

        _Progress(evaluations)(scipy_optimize.OptimizeResult(fun=1.0, nit=2))

        # SciPy reports the objective; the efficiency behind it is read from
        # the records, which is where the workers write it.
        assert "Generation 2" in progress_log.text
        assert "best NSE 0.750000" in progress_log.text
        assert "2 evaluation(s) recorded" in progress_log.text


class TestReproducibility:
    @pytest.mark.unit
    def test_two_runs_of_one_seed_write_the_same_table(self, dataset, capfd):
        first = calibrate(
            dataset.config_file,
            dataset.observed,
            dataset.run_dir / "first",
            dataset.settings(),
        )
        second = calibrate(
            dataset.config_file,
            dataset.observed,
            dataset.run_dir / "second",
            dataset.settings(),
        )

        def candidates(result):
            return [
                tuple(row[name] for name in CALIBRATION_PARAMETERS)
                for row in read_evaluations(result.evaluations_csv)
            ]

        # Same seed, same initial population, same candidates, in the same
        # order: the synthetic dataset carries a fixed LDD, so the simulation
        # itself is reproducible and the two searches follow the same path. Only
        # the identifiers, the process ids and the elapsed times differ.
        assert candidates(first) == candidates(second)
        assert first.best_parameters == second.best_parameters
        assert first.best_objective == second.best_objective
        assert first.evaluations == second.evaluations
        # The library logs, the command line prints, and the workers are silent:
        # the newline the PCRaster framework prints when a worker exits goes to
        # the null device, and the warnings of an unvalidated load, which the
        # parent already reported, meet a null handler instead of the last
        # resort handler of logging. Captured at file-descriptor level, so the
        # children are included.
        out, err = capfd.readouterr()
        assert out == ""
        assert "WARNING" not in err and "No handlers could be found" not in err


class TestFailures:
    @pytest.mark.unit
    def test_a_run_whose_evaluations_all_fail_is_reported_with_its_first_error(
        self, dataset, tmp_path
    ):
        # The stations and the steps of this file are the ones the run samples,
        # so the parent lets it through; every value is a gap, so every worker
        # fails inside the evaluation of the series.
        gaps = tmp_path / "gaps.csv"
        gaps.write_text(
            "0;1;2\n" + "".join(f"{step};-9999;-9999\n" for step in range(1, TIMESTEPS + 1)),
            encoding="utf8",
        )

        with pytest.raises(CalibrationError, match="Nash-Sutcliffe") as failure:
            dataset.calibrate(observed=gaps, maxiter=1)

        # The search ran: what is reported is the summary of the finished run,
        # carrying the first error a worker recorded, not a refusal of the parent.
        assert "Every evaluation of the calibration failed" in str(failure.value)

        rows = read_evaluations(dataset.run_dir / "evaluations.csv")
        assert rows, "the table of the evaluations is written even when every one failed"
        assert all(row["error"] for row in rows)
        assert all(row["nse"] == "" for row in rows)

    @pytest.mark.unit
    def test_a_variable_the_model_does_not_write_is_refused(self, dataset):
        with pytest.raises(CalibrationError, match="not an output variable"):
            dataset.calibrate(variable="flow")

    @pytest.mark.unit
    def test_a_run_directory_of_an_earlier_calibration_is_refused(self, dataset):
        evaluations = dataset.run_dir / "evaluations"
        evaluations.mkdir(parents=True)
        (evaluations / "deadbeef.json").write_text("{}", encoding="utf8")

        with pytest.raises(CalibrationError, match="already holds 1 evaluation"):
            dataset.calibrate()

    @pytest.mark.unit
    def test_a_negative_spin_up_is_refused(self, dataset):
        with pytest.raises(CalibrationError, match="must not be negative"):
            dataset.calibrate(spinup_steps=-1)

    @pytest.mark.unit
    def test_a_search_without_a_worker_is_refused(self, dataset):
        with pytest.raises(CalibrationError, match="at least one worker"):
            dataset.calibrate(workers=0)

    @pytest.mark.unit
    def test_without_scipy_the_optional_extra_is_named(self, dataset, monkeypatch):
        monkeypatch.setattr(_deps, "missing_calibration_deps", lambda: ["scipy"])

        with pytest.raises(CalibrationError, match=r"rubem\[calibration\]"):
            dataset.calibrate()

        assert not dataset.run_dir.exists(), "nothing is written when the search cannot start"


@pytest.fixture
def no_pool(monkeypatch):
    """Let a test prove that no worker process was ever started."""
    _RecordingExecutor.built.clear()
    monkeypatch.setattr(runner, "ProcessPoolExecutor", _RecordingExecutor)
    return _RecordingExecutor.built


class TestObservedSeries:
    @pytest.mark.unit
    def test_an_observed_series_of_foreign_stations_is_refused_before_the_search(
        self, dataset, tmp_path, no_pool
    ):
        foreign = tmp_path / "foreign.csv"
        foreign.write_text("0;A;B\n1;1.0;2.0\n2;2.0;3.0\n3;3.0;4.0\n", encoding="utf8")

        with pytest.raises(CalibrationError, match="no station in common") as failure:
            dataset.calibrate(observed=foreign, maxiter=1)

        # Both sets are named, and the refusal comes before anything is written
        # or any worker is started: a wrong observed file costs no model run.
        assert "A, B" in str(failure.value)
        assert "1, 2" in str(failure.value)
        assert not dataset.run_dir.exists()
        assert no_pool == []
        assert multiprocessing.active_children() == []

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("steps", "overrides"),
        [
            ([TIMESTEPS + 1, TIMESTEPS + 2], {}),
            ([-1, 0], {}),
            ([1, TIMESTEPS], {"spinup_steps": TIMESTEPS}),
        ],
        ids=["after the window", "before the window", "inside the spin-up"],
    )
    def test_an_observed_series_outside_the_compared_steps_is_refused(
        self, dataset, tmp_path, no_pool, steps, overrides
    ):
        elsewhere = tmp_path / "elsewhere.csv"
        elsewhere.write_text(
            "0;1;2\n" + "".join(f"{step};1.0;2.0\n" for step in steps), encoding="utf8"
        )

        with pytest.raises(CalibrationError, match="no time step in common") as failure:
            dataset.calibrate(observed=elsewhere, **overrides)

        message = str(failure.value)
        assert f"{min(steps)} to {max(steps)}" in message
        assert f"1 to {TIMESTEPS}" in message
        assert f"{overrides.get('spinup_steps', 0)} spin-up" in message
        assert not dataset.run_dir.exists()
        assert no_pool == []

    @pytest.mark.unit
    def test_an_observed_station_the_run_does_not_sample_is_warned_about_and_ignored(
        self, dataset, caplog
    ):
        rows = dataset.observed.read_text(encoding="utf8").splitlines()
        extra = dataset.observed.with_name("extra.csv")
        extra.write_text(
            "".join(f"{row};{'3' if number == 0 else '1.0'}\n" for number, row in enumerate(rows)),
            encoding="utf8",
        )

        exact = calibrate(
            dataset.config_file, dataset.observed, dataset.run_dir / "exact", dataset.settings()
        )
        with caplog.at_level(logging.WARNING, logger="rubem.calibration.runner"):
            with_extra = calibrate(
                dataset.config_file, extra, dataset.run_dir / "extra", dataset.settings()
            )

        # The foreign column is named once and then ignored by the alignment, so
        # the calibration is the one the exact file produces.
        assert "does not sample (3)" in caplog.text
        assert with_extra.best_parameters == exact.best_parameters
        assert with_extra.best_objective == exact.best_objective
        assert with_extra.best_nse == exact.best_nse
        assert with_extra.evaluations == exact.evaluations

    @pytest.mark.unit
    def test_a_negative_observation_is_counted_as_a_gap_before_the_search(
        self, dataset, broken_search, progress_log
    ):
        rows = dataset.observed.read_text(encoding="utf8").splitlines()
        first = rows[1].split(";")
        # The gauge of station 1 has no reading at the first step, written as
        # the negative marker an observation table marks a gap with.
        first[1] = "-1.5"
        gapped = dataset.observed.with_name("gapped.csv")
        gapped.write_text("\n".join([rows[0], ";".join(first), *rows[2:]]) + "\n", encoding="utf8")

        with pytest.raises(RuntimeError, match="the search broke"):
            dataset.calibrate(observed=gapped)

        summarized = {
            row["station"]: row for row in read_station_table(dataset.run_dir / "observed.csv")
        }
        # The negative value never reaches the statistics, and both the table
        # and the line the run prints count it as a gap of that station alone.
        assert summarized["1"]["dropped"] == "1"
        assert summarized["1"]["pairs_in_window"] == str(TIMESTEPS - 1)
        assert float(summarized["1"]["min"]) > 0.0
        assert summarized["2"]["dropped"] == "0"
        assert summarized["2"]["pairs_in_window"] == str(TIMESTEPS)
        assert (
            f"Station 1: {TIMESTEPS - 1} observed value(s) on the compared steps, "
            "1 dropped as gaps." in progress_log.text
        )

    @pytest.mark.unit
    def test_the_stations_are_the_values_of_the_sample_locations_raster(self, dataset):
        samples = ModelConfiguration(
            dataset.config, validate_input=False
        ).raster_files.sample_locations

        # The no-data cells of the nominal map are not stations, and the ids are
        # the strings the model writes in the header of its table.
        assert _station_ids(samples) == {"1", "2"}

    @pytest.mark.unit
    def test_a_background_of_zeroes_is_not_a_station(self, tmp_path):
        from osgeo import gdal

        gdal.UseExceptions()
        gdal.AllRegister()
        raster = tmp_path / "samples-with-zeroes.tif"
        handle = gdal.GetDriverByName("GTiff").Create(str(raster), 3, 3, 1, gdal.GDT_Int32)
        try:
            values = np.zeros((3, 3), dtype=np.int32)
            values[0, 0], values[2, 2] = 1, 2
            handle.GetRasterBand(1).WriteArray(values)
            handle.FlushCache()
        finally:
            handle = None

        # A raster may mark its background with zeroes and declare no no-data
        # value at all; the validation of the inputs counts neither the zeroes
        # nor the missing cells as a sample, and neither does this.
        assert _station_ids(raster) == {"1", "2"}

    @pytest.mark.unit
    def test_the_stations_of_a_zones_aggregation_are_not_checked(self):
        # The model remaps the zone ids to 1..N at run time, so the parent has
        # no station id to compare and the check only covers the steps.
        observed = Series(steps=np.array([1, 2, 3]), stations={"A": np.zeros(3)})

        assert (
            _check_observed_series(
                observed,
                first_step=1,
                last_step=3,
                spinup_steps=0,
                aggregation=Aggregation.ZONES,
                station_ids={"1", "2"},
            )
            is None
        )


class TestSettings:
    @pytest.mark.unit
    def test_the_default_decision_vector_is_the_configuration_under_calibration(self, dataset):
        vector = parameters_to_vector(dataset.parameters)

        assert vector == pytest.approx([4.5, 0.5, 0.333, 0.333, 5.0, 0.5, 0.5, 0.5])

    @pytest.mark.unit
    def test_the_defaults_are_the_documented_ones(self):
        settings = CalibrationSettings()

        assert (settings.variable, settings.spinup_steps) == ("arn", 0)
        assert (settings.maxiter, settings.popsize) == (100, 15)
        assert settings.init == "sobol"
        assert settings.strategy == "best1exp"
        assert settings.mutation == (0.5, 1.0)
        assert settings.recombination == 0.7
        assert settings.polish is False
        assert settings.workers is None
        assert settings.allow_blocking_problems is False

    @pytest.mark.unit
    @pytest.mark.parametrize("allowed", [False, True])
    def test_allow_blocking_problems_reaches_the_configuration_loader(
        self, dataset, monkeypatch, allowed
    ):
        """The single load of a calibration carries the option to ``Model.from_file``.

        The workers never revalidate, so this call is the only place the option
        can have an effect, and the search itself is irrelevant to the question.
        """
        seen = {}
        original = Model.from_file

        def recording_from_file(path, **keywords):
            seen.update(keywords)
            return original(path, **keywords)

        def stop(*_args, **_keywords):
            raise RuntimeError("the load is all this test exercises")

        monkeypatch.setattr(Model, "from_file", staticmethod(recording_from_file))
        # The search that follows the load is irrelevant here, so the next step
        # of the calibration ends it.
        monkeypatch.setattr(runner, "read_series", stop)

        with pytest.raises(RuntimeError, match="the load is all this test exercises"):
            runner.calibrate(
                dataset.config_file,
                dataset.observed,
                dataset.run_dir / "allowed",
                CalibrationSettings(allow_blocking_problems=allowed),
            )

        assert seen["allow_blocking_problems"] is allowed
        assert seen["validate_input"] is True


@pytest.fixture(scope="class")
def calibrated_v1(tmp_path_factory):
    """One calibration of the same dataset written as a format 1.0 configuration."""
    tmp_path = tmp_path_factory.mktemp("calibration-v1")
    data = Dataset(tmp_path)
    legacy = ModelConfigurationFile.model_validate(data.config)
    data.config_file = tmp_path / "basin.json"
    data.config_file.write_text(
        json.dumps(ModelConfigurationFileV1.from_legacy(legacy).to_dict()), encoding="utf8"
    )
    return data, data.calibrate()


class TestFormatV1Configuration:
    @pytest.mark.unit
    def test_a_format_1_0_configuration_is_calibrated_and_written_back_in_its_format(
        self, calibrated_v1
    ):
        data, result = calibrated_v1

        assert result.best_objective == pytest.approx(0.0, abs=1e-9)
        assert result.best_parameters == pytest.approx(data.parameters, abs=1e-12)
        assert result.calibrated_config.name == "basin-calibrated.json"
        document = json.loads(result.calibrated_config.read_text(encoding="utf-8"))
        assert document["version"] == "1.0"
        assert document["model_calibration_parameters"]["b"] == pytest.approx(
            result.best_parameters["beta"], abs=1e-12
        )
        configuration = ModelConfiguration(result.calibrated_config, validate_input=False)
        assert configuration.calibration_parameters.model_dump() == pytest.approx(
            result.best_parameters, abs=1e-12
        )


class TestEvaluationBudget:
    @pytest.mark.unit
    def test_a_sobol_population_is_rounded_up_to_a_power_of_two(self):
        # The documented arithmetic: max(5, popsize * 8) members, rounded up to
        # the next power of two, because a Sobol' sequence is balanced only over
        # a power-of-two sample.
        assert _population_size(CalibrationSettings()) == 128
        assert _population_size(CalibrationSettings(popsize=1)) == 8
        assert _population_size(CalibrationSettings(popsize=16)) == 128

    @pytest.mark.unit
    def test_another_initialization_uses_the_members_it_asks_for(self):
        assert _population_size(CalibrationSettings(init="latinhypercube", popsize=3)) == 24
        assert _population_size(CalibrationSettings(init="random", popsize=15)) == 120
        assert _population_size(CalibrationSettings(init=INIT)) == len(INIT)

    @pytest.mark.unit
    def test_a_smaller_decision_space_needs_fewer_members(self):
        # One fixed parameter takes a dimension out of the search, and the
        # number of members follows it.
        assert _population_size(CalibrationSettings(popsize=15), 7) == 128
        assert _population_size(CalibrationSettings(popsize=15, init="latinhypercube"), 7) == 105
        assert _population_size(CalibrationSettings(popsize=1, init="random"), 1) == 5

    @pytest.mark.unit
    @pytest.mark.parametrize("popsize", [1, 5, 15, 16])
    @pytest.mark.parametrize("init", ["sobol", "halton", "latinhypercube", "random"])
    @pytest.mark.parametrize("dimension", [7, 8])
    def test_the_announced_population_is_the_one_scipy_builds(self, popsize, init, dimension):
        # The announced number is what the command line reports as the budget,
        # so it has to be SciPy's own arithmetic and not an approximation of it:
        # only ``sobol`` rounds the population up to a power of two, and the
        # number of free parameters is a factor of it.
        optimum = scipy_optimize.differential_evolution(
            lambda vector: float(np.sum(vector)),
            bounds()[:dimension],
            init=init,
            popsize=popsize,
            maxiter=0,
            polish=False,
            rng=0,
        )

        assert len(optimum.population) == _population_size(
            CalibrationSettings(popsize=popsize, init=init), dimension
        )

    @pytest.mark.unit
    def test_the_summary_reports_the_population_the_search_really_built(self, dataset, monkeypatch):
        # A named initialization resizes the population, so the summary must
        # report the population of the result and not the number this module
        # announced for the budget.
        def stub(function, search_bounds, **kwargs):
            population = np.asarray(kwargs["init"], dtype=np.float64)
            energies = np.asarray([function(member) for member in population[:2]])
            enlarged = np.repeat(population, 2, axis=0)
            return scipy_optimize.OptimizeResult(
                x=population[0],
                fun=float(energies[0]),
                nfev=len(energies),
                nit=1,
                success=True,
                message="stub",
                population=enlarged,
                population_energies=np.full(len(enlarged), np.inf),
            )

        monkeypatch.setattr(scipy_optimize, "differential_evolution", stub)

        result = dataset.calibrate()
        summary = json.loads(result.result_json.read_text(encoding="utf-8"))

        assert summary["population_size"] == 2 * len(INIT)
        assert _population_size(dataset.settings()) == len(INIT)


class TestOptionalDependency:
    @pytest.mark.unit
    def test_importing_the_package_does_not_import_scipy(self, tmp_path):
        # An installation without the rubem[calibration] extra must still be
        # able to import the package, so SciPy is imported inside the functions
        # that need it. A fresh interpreter is the only honest probe: the test
        # session has SciPy loaded already.
        probe = tmp_path / "probe.py"
        probe.write_text(
            "import sys\n"
            "import rubem.calibration.runner\n"
            "import rubem.calibration._worker\n"
            "import rubem.calibration.parameters\n"
            "print('scipy' in sys.modules)\n",
            encoding="utf8",
        )

        environment = {**os.environ, "PYTHONPATH": REPO_ROOT}
        completed = subprocess.run(
            [sys.executable, str(probe)],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
            env=environment,
        )

        assert completed.stdout.strip() == "False"


@pytest.fixture(scope="class")
def calibrated_with_a_fixed_parameter(tmp_path_factory):
    """One calibration in which ``x`` is pinned and only seven parameters are searched."""
    data = Dataset(tmp_path_factory.mktemp("calibration-fixed"))
    free = np.delete(INIT, FREE_PARAMETERS.index("x"), axis=1)
    return data, data.calibrate(fixed={"x": 0.0}, init=free, stations=("1", "2"))


class TestFixedParameters:
    @pytest.mark.unit
    def test_the_fixed_parameter_is_not_searched_and_is_in_every_candidate(
        self, calibrated_with_a_fixed_parameter
    ):
        _, result = calibrated_with_a_fixed_parameter
        rows = read_evaluations(result.evaluations_csv)

        assert set(result.best_parameters) == set(CALIBRATION_PARAMETERS)
        assert result.best_parameters["x"] == 0.0
        assert rows, "the search ran"
        assert [row["error"] for row in rows if row["error"]] == []
        # Every candidate the search proposed carries the pinned value, and the
        # column is still in the table: the parameter left the decision vector,
        # not the model.
        assert {row["x"] for row in rows} == {"0.0"}

    @pytest.mark.unit
    def test_the_summary_records_the_fixed_value_the_bounds_and_the_stations(
        self, calibrated_with_a_fixed_parameter
    ):
        _, result = calibrated_with_a_fixed_parameter
        settings = json.loads(result.result_json.read_text(encoding="utf-8"))["settings"]

        assert settings["fixed"] == {"x": 0.0}
        assert settings["stations"] == ["1", "2"]
        assert list(settings["bounds"]) == [name for name in FREE_PARAMETERS if name != "x"]
        assert settings["bounds"]["rcd"] == [1.0, 10.0]

    @pytest.mark.unit
    def test_the_calibrated_configuration_carries_the_fixed_value(
        self, calibrated_with_a_fixed_parameter
    ):
        _, result = calibrated_with_a_fixed_parameter
        configuration = ModelConfiguration(result.calibrated_config, validate_input=False)

        assert configuration.calibration_parameters.model_dump()["x"] == 0.0

    @pytest.mark.unit
    def test_a_fixed_weight_replaces_the_constraint_with_a_narrowed_bound(
        self, dataset, broken_search
    ):
        free = np.delete(INIT, FREE_PARAMETERS.index("w_1"), axis=1)

        with pytest.raises(RuntimeError, match="the search broke"):
            dataset.calibrate(fixed={"w_1": 0.7}, init=free)

        searched = [name for name in FREE_PARAMETERS if name != "w_1"]
        # One free weight is a bound, not a constraint: the argument is left out
        # instead of being handed over as ``None``.
        assert "constraints" not in broken_search
        assert len(broken_search["bounds"]) == len(searched) == 7
        assert broken_search["bounds"][searched.index("w_2")] == (0.0, pytest.approx(0.3))
        assert len(broken_search["x0"]) == 7

    @pytest.mark.unit
    def test_a_decision_space_the_settings_cannot_describe_is_refused(self, dataset, no_pool):
        with pytest.raises(ValueError, match="cannot be fixed"):
            dataset.calibrate(fixed={"x": 5.0})

        assert not dataset.run_dir.exists()
        assert no_pool == []

    @pytest.mark.unit
    def test_an_initial_population_of_the_wrong_width_is_refused(self, dataset, no_pool):
        # ``INIT`` has one column per parameter of the whole search, and the
        # fixed one has left the decision vector.
        with pytest.raises(ValueError, match="one column per free parameter") as failure:
            dataset.calibrate(fixed={"x": 0.0})

        assert "(5, 8)" in str(failure.value)
        assert "7 free parameter(s)" in str(failure.value)
        assert not dataset.run_dir.exists()
        assert no_pool == []

    @pytest.mark.unit
    def test_an_initial_population_that_is_not_a_table_of_members_is_refused(
        self, dataset, no_pool
    ):
        with pytest.raises(ValueError, match="two-dimensional array"):
            dataset.calibrate(init=INIT[0])

        assert not dataset.run_dir.exists()
        assert no_pool == []


class TestNarrowedBounds:
    @pytest.mark.unit
    def test_the_search_is_given_the_narrowed_bounds(self, dataset, broken_search):
        with pytest.raises(RuntimeError, match="the search broke"):
            dataset.calibrate(bounds={"rcd": (2.0, 5.0)})

        expected = bounds()
        expected[FREE_PARAMETERS.index("rcd")] = (2.0, 5.0)
        assert broken_search["bounds"] == expected

    @pytest.mark.unit
    def test_a_starting_point_outside_a_narrowed_bound_is_moved_onto_it(
        self, dataset, broken_search, caplog
    ):
        with caplog.at_level(logging.WARNING, logger="rubem.calibration.runner"):
            with pytest.raises(RuntimeError, match="the search broke"):
                dataset.calibrate(bounds={"alpha": (5.0, 8.0)})

        # The configuration has alpha = 4.5, which this run does not search;
        # SciPy refuses a starting point outside the bounds, so it is moved onto
        # the bound and the move is reported instead of ending the run.
        assert broken_search["x0"][FREE_PARAMETERS.index("alpha")] == 5.0
        assert "alpha" in caplog.text
        assert "4.5" in caplog.text

    @pytest.mark.unit
    def test_a_bound_that_does_not_narrow_the_settings_range_is_refused(self, dataset, no_pool):
        with pytest.raises(ValueError, match="not a narrower range"):
            dataset.calibrate(bounds={"rcd": (0.5, 12.0)})

        assert not dataset.run_dir.exists()
        assert no_pool == []


class TestStationSelection:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        "stations",
        [(), ("1", ""), ("1", 2), "12"],
        ids=["empty", "a blank id", "not a string", "a bare string"],
    )
    def test_a_selection_that_names_no_station_is_refused(self, dataset, no_pool, stations):
        with pytest.raises(CalibrationError):
            dataset.calibrate(stations=stations)

        assert not dataset.run_dir.exists()
        assert no_pool == []

    @pytest.mark.unit
    def test_the_selected_stations_are_logged_before_the_search(
        self, dataset, broken_search, caplog
    ):
        with caplog.at_level(logging.INFO, logger="rubem.calibration.runner"):
            with pytest.raises(RuntimeError, match="the search broke"):
                dataset.calibrate(stations=("1",))

        assert "the station(s) 1" in caplog.text


def _record_then_raise(error, modflow=None):
    """A search that records one evaluation and then fails, without a worker.

    The records are what an interrupted calibration has to leave behind, and
    the failure has to happen where the real one does, inside the search. The
    evaluations directory is read out of the objective the search was handed,
    which is where the parent put it. ``modflow`` adds MODFLOW values to the
    parameters of the record.
    """

    def stub(function, search_bounds, **kwargs):
        evaluations_dir = Path(function.keywords["context"].evaluations_dir)
        record = {
            "id": "deadbeef",
            "pid": 4321,
            "started_at": "2000-01-01T00:00:00+00:00",
            "parameters": {**dict.fromkeys(CALIBRATION_PARAMETERS, 0.5), **(modflow or {})},
            "nse": 0.25,
            "station_nse": {"1": 0.25},
            "station_metrics": {},
            "objective": 5625000.0,
            "elapsed_seconds": 1.5,
            "error": None,
        }
        (evaluations_dir / "deadbeef.json").write_text(json.dumps(record), encoding="utf8")
        raise error

    return stub


class TestInterruptedSearch:
    @pytest.mark.unit
    def test_an_interrupted_search_still_writes_the_evaluations_it_made(self, dataset, monkeypatch):
        monkeypatch.setattr(
            scipy_optimize, "differential_evolution", _record_then_raise(KeyboardInterrupt())
        )

        with pytest.raises(KeyboardInterrupt):
            dataset.calibrate()

        # The evaluations are hours of model runs on a real basin; a
        # calibration that has to be stopped is read from them like any other.
        rows = read_evaluations(dataset.run_dir / "evaluations.csv")
        assert [row["id"] for row in rows] == ["deadbeef"]
        assert rows[0]["started_at"] == "2000-01-01T00:00:00+00:00"
        assert rows[0]["nse"] == repr(0.25)

    @pytest.mark.unit
    def test_a_crashed_search_still_writes_the_evaluations_it_made(self, dataset, monkeypatch):
        monkeypatch.setattr(
            scipy_optimize, "differential_evolution", _record_then_raise(RuntimeError("boom"))
        )

        with pytest.raises(RuntimeError, match="boom"):
            dataset.calibrate()

        assert read_evaluations(dataset.run_dir / "evaluations.csv")

    @pytest.mark.unit
    def test_a_search_that_recorded_nothing_leaves_no_table(self, dataset, broken_search):
        with pytest.raises(RuntimeError, match="the search broke"):
            dataset.calibrate()

        assert not (dataset.run_dir / "evaluations.csv").exists()

    @pytest.mark.unit
    def test_a_worker_killed_by_the_system_is_reported_with_the_advice(self, dataset, monkeypatch):
        monkeypatch.setattr(
            scipy_optimize,
            "differential_evolution",
            _record_then_raise(BrokenProcessPool("A process in the process pool was terminated")),
        )

        with pytest.raises(CalibrationError, match="--workers") as failure:
            dataset.calibrate()

        message = str(failure.value)
        assert "died before finishing" in message
        assert "memory" in message
        # The cause is kept, so the traceback still says what the pool reported.
        assert isinstance(failure.value.__cause__, BrokenProcessPool)
        assert read_evaluations(dataset.run_dir / "evaluations.csv")

    @pytest.mark.unit
    @pytest.mark.parametrize("function", ["_consolidate", "_write_evaluations_csv"])
    def test_the_columns_of_the_table_are_always_given(self, function):
        # A default would silently fall back to the nine parameters and drop the
        # MODFLOW columns of the one path that forgot to pass them.
        parameter = inspect.signature(getattr(runner, function)).parameters["columns"]
        assert parameter.default is inspect.Parameter.empty


class TestProgressReporting:
    @pytest.mark.unit
    def test_the_budget_the_coverage_the_generations_and_the_summary_are_reported(
        self, dataset, progress_log
    ):
        result = dataset.calibrate()

        text = progress_log.text
        # The budget, before anything is spent on it.
        assert "8 free parameter(s)" in text
        assert f"{len(INIT)} population member(s)" in text
        assert "2 worker process(es)" in text
        # The coverage of the compared window, per station.
        assert f"compares {TIMESTEPS} time step(s)" in text
        assert f"covers {TIMESTEPS} of them" in text
        assert f"Station 1: {TIMESTEPS} observed value(s)" in text
        assert "0 dropped as gaps" in text
        # One line per generation, and the closing summary.
        assert "Generation 1:" in text
        assert "best NSE" in text
        assert "Calibration finished after" in text
        assert f"{result.evaluations} evaluation(s)" in text

    @pytest.mark.unit
    def test_the_progress_is_logged_and_never_printed(self, dataset, progress_log, capfd):
        dataset.calibrate()

        assert "Generation 1:" in progress_log.text
        out, _ = capfd.readouterr()
        assert out == "", "the library logs, the command line prints"


class TestStationsOfTheObjective:
    @pytest.mark.unit
    def test_a_station_left_out_of_the_objective_is_measured_and_marked(self, dataset):
        result = dataset.calibrate(stations=("1",))

        observed = {
            row["station"]: row for row in read_station_table(result.run_dir / "observed.csv")
        }
        stations = {row["station"]: row for row in read_station_table(result.stations_csv)}

        assert observed["1"]["in_selection"] == "true"
        assert observed["2"]["in_selection"] == "false"
        # The station outside the objective is measured all the same: that is
        # the validation half of a calibration/validation split.
        assert stations["1"]["in_selection"] == "true"
        assert stations["2"]["in_selection"] == "false"
        assert float(stations["2"]["nse"]) == pytest.approx(1.0, abs=1e-12)
        assert int(stations["2"]["pairs"]) == TIMESTEPS
        assert json.loads(result.result_json.read_text(encoding="utf-8"))["settings"][
            "stations"
        ] == ["1"]

    @pytest.mark.unit
    def test_a_selection_of_stations_the_run_does_not_have_is_refused_before_the_search(
        self, dataset, no_pool
    ):
        with pytest.raises(CalibrationError, match="none of the station") as failure:
            dataset.calibrate(stations=("7", "8"))

        # A misspelt id would otherwise fail every evaluation of the run and
        # spend the whole budget finding out.
        assert "7, 8" in str(failure.value)
        assert "1, 2" in str(failure.value)
        assert not dataset.run_dir.exists()
        assert no_pool == []

    @pytest.mark.unit
    def test_a_selection_that_names_one_unknown_station_warns_and_keeps_the_rest(
        self, dataset, broken_search, caplog
    ):
        with caplog.at_level(logging.WARNING, logger="rubem.calibration.runner"):
            with pytest.raises(RuntimeError, match="the search broke"):
                dataset.calibrate(stations=("1", "7"))

        assert "does not have (7)" in caplog.text


SPECIFIC_YIELD = "modflow.layers.1.specific_yield"
KH = "modflow.layers.1.kh.2"

needs_mf2005 = pytest.mark.skipif(
    _deps.resolve_mf2005() is None, reason="the MODFLOW-2005 executable is not installed"
)


class ModflowDataset(Dataset):
    """The synthetic dataset coupled to MODFLOW, and a series another candidate wrote.

    The configuration under calibration has the specific yield 0.15 and the
    class 2 conductivity 0.1 of :func:`write_modflow_inputs`; the observed
    series is what the same configuration writes with ``truth`` instead, so a
    search that finds the observations has to move the MODFLOW values.

    The river stage lies below the initial head, so the aquifer drains into the
    river and the baseflow, hence ``arn``, depends on the specific yield (with
    the stage of :func:`write_modflow_inputs` above the heads the river only
    loses water and the baseflow is zero whatever the MODFLOW values). One time
    step per stress period: a worker whose MODFLOW run fails before the last
    time step of a period ends its process (phase 4 finding), and the search
    could not tell that from a bug of the calibration.
    """

    def __init__(self, tmp_path, truth=None):
        self.config = write_synthetic_dataset(str(tmp_path), timesteps=TIMESTEPS)
        section = write_modflow_inputs(self.config)
        section["dis"] = {"nstp": 1}
        river = section["river"]["entries"][0]
        directory = Path(section["top"]).parent
        river["stage"] = write_grid_map(directory / "drained_stage.map", MODFLOW_HEAD - 5.0)
        river["bottom"] = write_grid_map(directory / "drained_bottom.map", MODFLOW_HEAD - 8.0)
        self.config["MODFLOW"] = section
        self.config_file = tmp_path / "config.json"
        self.config_file.write_text(json.dumps(self.config), encoding="utf8")
        self.truth = truth or {}
        observed_config = json.loads(json.dumps(self.config))
        layer = observed_config["MODFLOW"]["layers"][0]
        if SPECIFIC_YIELD in self.truth:
            layer["specific_yield"] = self.truth[SPECIFIC_YIELD]
        if KH in self.truth:
            table = tmp_path / "kh_truth.tbl"
            table.write_text(f"1 {MODFLOW_KH_TABLE[1]}\n2 {self.truth[KH]}\n", encoding="utf8")
            layer["horizontal_conductivity"]["table"] = str(table)
        written = Model.from_config(observed_config).run().time_series["arn"][0]
        self.observed = tmp_path / "observed.csv"
        shutil.copyfile(written, self.observed)
        self.run_dir = tmp_path / "calibration"
        self.temp_dir = tmp_path / "temp"
        self.parameters = ModelConfiguration(
            self.config, validate_input=False
        ).calibration_parameters.model_dump()

    def tmp_run_dir(self, name):
        """A fresh run directory, for the tests that share one dataset."""
        return self.run_dir.parent / f"calibration-{name}"

    def init(self, columns):
        """``INIT`` widened by one column per MODFLOW name, with one member at the truth.

        The second member is the configuration's own eight free parameters with
        the MODFLOW values of the observations, so the global optimum is in the
        initial population and the search is deterministic.

        :param columns: The five values of each MODFLOW name, in the order of
            the decision vector.
        """
        rows = [
            [*row, *(values[member] for values in columns.values())]
            for member, row in enumerate(INIT.tolist())
        ]
        rows[1] = [
            *parameters_to_vector(self.parameters).tolist(),
            *(self.truth.get(name, values[1]) for name, values in columns.items()),
        ]
        return np.asarray(rows, dtype=np.float64)


@pytest.fixture(scope="class")
def calibrated_modflow(tmp_path_factory):
    """One search of the specific yield of layer 1, with one class conductivity pinned.

    The conductivity of a class barely moves ``arn`` on this grid (the sixth
    significant digit), so it is fixed at the value of the observations rather
    than searched; the fixed value still goes through every evaluation and into
    the calibrated configuration.
    """
    data = ModflowDataset(
        tmp_path_factory.mktemp("calibration-modflow"), truth={SPECIFIC_YIELD: 0.25, KH: 0.2}
    )
    result = data.calibrate(
        bounds={SPECIFIC_YIELD: (0.05, 0.3)},
        fixed={KH: 0.2},
        init=data.init({SPECIFIC_YIELD: (0.1, 0.25, 0.2, 0.3, 0.05)}),
    )
    return data, result


@needs_mf2005
class TestModflowCalibration:
    @pytest.mark.unit
    def test_the_modflow_values_of_the_observations_are_found(self, calibrated_modflow):
        data, result = calibrated_modflow

        assert result.best_nse == pytest.approx(1.0, abs=1e-9)
        assert result.best_parameters == pytest.approx(
            {**data.parameters, SPECIFIC_YIELD: 0.25, KH: 0.2}, abs=1e-12
        )
        assert list(result.best_parameters) == [*CALIBRATION_PARAMETERS, SPECIFIC_YIELD, KH]

    @pytest.mark.unit
    def test_the_modflow_names_are_columns_of_the_table(self, calibrated_modflow):
        _, result = calibrated_modflow
        rows = read_evaluations(result.evaluations_csv)
        columns = list(EVALUATION_COLUMNS)
        columns[columns.index("x") + 1 : columns.index("x") + 1] = [SPECIFIC_YIELD, KH]

        assert list(rows[0]) == columns
        assert [row["error"] for row in rows if row["error"]] == []
        assert all(row[SPECIFIC_YIELD] for row in rows)
        assert len({row[SPECIFIC_YIELD] for row in rows}) > 1
        assert {row[KH] for row in rows} == {"0.2"}

    @pytest.mark.unit
    def test_the_series_of_the_best_candidate_is_the_one_of_its_modflow_values(
        self, calibrated_modflow
    ):
        _, result = calibrated_modflow

        # The best candidate reproduces the observations only when it is run
        # again with its own MODFLOW values, not the ones of the configuration.
        rows = read_station_table(result.best_series)
        assert rows
        for row in rows:
            for station in ("1", "2"):
                assert float(row[f"simulated_{station}"]) == pytest.approx(
                    float(row[f"observed_{station}"]), rel=1e-9, abs=1e-12
                )

    @pytest.mark.unit
    def test_the_summary_lists_the_modflow_parameters(self, calibrated_modflow):
        _, result = calibrated_modflow
        summary = json.loads(result.result_json.read_text(encoding="utf-8"))

        assert summary["best_parameters"][SPECIFIC_YIELD] == pytest.approx(0.25)
        assert summary["best_parameters"][KH] == pytest.approx(0.2)
        assert summary["settings"]["bounds"][SPECIFIC_YIELD] == [0.05, 0.3]
        assert summary["settings"]["fixed"] == {KH: 0.2}

    @pytest.mark.unit
    def test_the_calibrated_configuration_carries_the_modflow_values(self, calibrated_modflow):
        data, result = calibrated_modflow
        table = result.run_dir / "config-calibrated-kh1.tbl"

        document = json.loads(result.calibrated_config.read_text(encoding="utf-8"))
        layer = document["MODFLOW"]["layers"][0]

        assert layer["specific_yield"] == pytest.approx(0.25)
        assert Path(layer["horizontal_conductivity"]["table"]) == table
        assert table.read_text(encoding="utf8").split() == ["1", "0.5", "2", "0.2"]
        # The configured table is left as it was.
        configured = Path(data.config["MODFLOW"]["layers"][0]["horizontal_conductivity"]["table"])
        assert configured.read_text(encoding="utf8").split() == ["1", "0.5", "2", "0.1"]
        configuration = ModelConfiguration(result.calibrated_config, validate_input=False)
        assert configuration.modflow.layers[0].specific_yield == pytest.approx(0.25)

    @pytest.mark.unit
    def test_no_modflow_directory_or_table_is_left_in_the_temporary_directory(
        self, calibrated_modflow
    ):
        data, _ = calibrated_modflow

        assert list(data.temp_dir.iterdir()) == []


@pytest.fixture(scope="class")
def calibrated_modflow_without_names(tmp_path_factory):
    """A coupled configuration calibrated on the nine parameters only."""
    data = ModflowDataset(tmp_path_factory.mktemp("calibration-modflow-nine"))
    return data, data.calibrate()


@needs_mf2005
class TestModflowConfigurationWithoutModflowNames:
    @pytest.mark.unit
    def test_the_table_has_the_columns_of_today(self, calibrated_modflow_without_names):
        _, result = calibrated_modflow_without_names
        rows = read_evaluations(result.evaluations_csv)

        assert list(rows[0]) == list(EVALUATION_COLUMNS)
        assert [row["error"] for row in rows if row["error"]] == []

    @pytest.mark.unit
    def test_every_evaluation_runs_the_coupled_model(self, calibrated_modflow_without_names):
        data, result = calibrated_modflow_without_names

        # The observations are the coupled run of the configuration, so only a
        # coupled evaluation of the configuration reproduces them.
        assert result.best_nse == pytest.approx(1.0, abs=1e-9)
        assert list(result.best_parameters) == list(CALIBRATION_PARAMETERS)
        document = json.loads(result.calibrated_config.read_text(encoding="utf-8"))
        assert document["MODFLOW"] == json.loads(
            json.dumps(ModelConfiguration(data.config_file).modflow.model_dump(mode="json"))
        )
        assert not list(result.run_dir.glob("*.tbl"))


@pytest.fixture(scope="class")
def modflow_dataset(tmp_path_factory):
    """A coupled dataset for the refusals, which never start a search."""
    return ModflowDataset(tmp_path_factory.mktemp("modflow-refusals"))


@needs_mf2005
class TestModflowRefusals:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("bound", "match"),
        [
            ({KH: (0.0, 0.5)}, "not a range inside"),
            ({"modflow.layers.1.specific_storage": (1e-6, 1e-4)}, "calibratable MODFLOW"),
            ({"modflow.layers.1.kh.9": (0.1, 0.2)}, "modflow.layers.1.kh.1"),
        ],
    )
    def test_a_modflow_bound_the_configuration_cannot_take_is_refused_before_the_search(
        self, modflow_dataset, no_pool, bound, match
    ):
        with pytest.raises(ValueError, match=match):
            calibrate(
                modflow_dataset.config_file,
                modflow_dataset.observed,
                modflow_dataset.run_dir,
                modflow_dataset.settings(bounds=bound),
            )

        assert not modflow_dataset.run_dir.exists()
        assert no_pool == []

    @pytest.mark.unit
    def test_the_search_starts_from_the_modflow_values_of_the_configuration(
        self, modflow_dataset, broken_search
    ):
        init = modflow_dataset.init({KH: (0.1, 0.2, 0.3, 0.4, 0.5)})
        with pytest.raises(RuntimeError, match="the search broke"):
            calibrate(
                modflow_dataset.config_file,
                modflow_dataset.observed,
                modflow_dataset.tmp_run_dir("start"),
                modflow_dataset.settings(bounds={KH: (0.05, 0.5)}, init=init),
            )

        assert broken_search["bounds"][-1] == (0.05, 0.5)
        assert len(broken_search["bounds"]) == 9
        assert broken_search["x0"][-1] == pytest.approx(MODFLOW_KH_TABLE[2])

    @pytest.mark.unit
    def test_the_workers_find_mf2005_on_the_path_they_inherit(
        self, modflow_dataset, broken_search, monkeypatch
    ):
        order = []
        monkeypatch.setattr(_deps, "ensure_mf2005_on_path", lambda: order.append("path"))
        built = runner._pool

        def pool(workers):
            order.append("pool")
            return built(workers)

        monkeypatch.setattr(runner, "_pool", pool)

        with pytest.raises(RuntimeError, match="the search broke"):
            calibrate(
                modflow_dataset.config_file,
                modflow_dataset.observed,
                modflow_dataset.tmp_run_dir("path"),
                modflow_dataset.settings(),
            )

        assert order == ["path", "pool"]

    @pytest.mark.unit
    def test_an_unreadable_conductivity_table_stops_the_calibration(
        self, tmp_path, no_pool, caplog
    ):
        data = ModflowDataset(tmp_path)
        table = Path(data.config["MODFLOW"]["layers"][0]["horizontal_conductivity"]["table"])
        table.write_text("1 0.5\n2 fast\n", encoding="utf8")

        with caplog.at_level(logging.CRITICAL):
            with pytest.raises(CalibrationError, match="kh1.tbl"):
                data.calibrate(allow_blocking_problems=True)

        assert no_pool == []

    @pytest.mark.unit
    def test_a_dead_worker_of_a_coupled_run_names_the_modflow_cause(
        self, modflow_dataset, monkeypatch
    ):
        monkeypatch.setattr(
            scipy_optimize,
            "differential_evolution",
            _record_then_raise(BrokenProcessPool("A process in the process pool was terminated")),
        )

        with pytest.raises(CalibrationError, match="memory") as failure:
            calibrate(
                modflow_dataset.config_file,
                modflow_dataset.observed,
                modflow_dataset.tmp_run_dir("dead"),
                modflow_dataset.settings(),
            )

        assert "dis.nstp" in str(failure.value)
        assert "converge" in str(failure.value)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("error", "raised"),
        [
            (BrokenProcessPool("A process in the process pool was terminated"), CalibrationError),
            (KeyboardInterrupt(), KeyboardInterrupt),
        ],
        ids=["dead-worker", "interrupted"],
    )
    def test_the_table_of_an_ended_search_keeps_the_modflow_columns(
        self, modflow_dataset, monkeypatch, error, raised
    ):
        monkeypatch.setattr(
            scipy_optimize,
            "differential_evolution",
            _record_then_raise(error, modflow={SPECIFIC_YIELD: 0.2}),
        )
        run_dir = modflow_dataset.tmp_run_dir(f"ended-{type(error).__name__}")

        with pytest.raises(raised):
            calibrate(
                modflow_dataset.config_file,
                modflow_dataset.observed,
                run_dir,
                modflow_dataset.settings(
                    bounds={SPECIFIC_YIELD: (0.05, 0.3)},
                    init=modflow_dataset.init({SPECIFIC_YIELD: (0.1, 0.25, 0.2, 0.3, 0.05)}),
                ),
            )

        # The table the message points to carries what the evaluations searched.
        with (run_dir / "evaluations.csv").open(encoding="utf-8", newline="") as table:
            header = next(csv.reader(table))
        position = EVALUATION_COLUMNS.index("x") + 1
        assert header == [
            *EVALUATION_COLUMNS[:position],
            SPECIFIC_YIELD,
            *EVALUATION_COLUMNS[position:],
        ]
        rows = read_evaluations(run_dir / "evaluations.csv")
        assert [row[SPECIFIC_YIELD] for row in rows] == [repr(0.2)]


class TestModflowNamesWithoutModflow:
    @pytest.mark.unit
    def test_a_modflow_name_is_refused_when_the_configuration_does_not_enable_it(
        self, dataset, no_pool
    ):
        with pytest.raises(ValueError, match="does not enable MODFLOW"):
            dataset.calibrate(bounds={SPECIFIC_YIELD: (0.05, 0.3)})

        assert not dataset.run_dir.exists()
        assert no_pool == []

    @pytest.mark.unit
    def test_a_run_without_modflow_leaves_the_path_alone(self, dataset, broken_search, monkeypatch):
        calls = []
        monkeypatch.setattr(_deps, "ensure_mf2005_on_path", lambda: calls.append("path"))

        with pytest.raises(RuntimeError, match="the search broke"):
            dataset.calibrate()

        assert calls == []

    @pytest.mark.unit
    def test_the_message_of_a_dead_worker_is_the_one_of_today(self, dataset, monkeypatch):
        monkeypatch.setattr(
            scipy_optimize,
            "differential_evolution",
            _record_then_raise(BrokenProcessPool("A process in the process pool was terminated")),
        )

        with pytest.raises(CalibrationError) as failure:
            dataset.calibrate()

        assert "dis.nstp" not in str(failure.value)


class TestRecordOrder:
    @pytest.mark.unit
    def test_the_modflow_values_order_candidates_that_share_the_nine_parameters(self):
        nine = dict.fromkeys(CALIBRATION_PARAMETERS, 0.5)
        records = [
            {"id": "a", "parameters": {**nine, SPECIFIC_YIELD: 0.3}},
            {"id": "b", "parameters": {**nine, SPECIFIC_YIELD: 0.1}},
        ]

        ordered = sorted(records, key=runner._record_order)

        assert [record["id"] for record in ordered] == ["b", "a"]
