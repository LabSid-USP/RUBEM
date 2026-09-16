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
from pathlib import Path

import numpy as np
import pytest

from rubem import _deps
from rubem.api import Model
from rubem.calibration import runner
from rubem.calibration.parameters import (
    CALIBRATION_PARAMETERS,
    FREE_PARAMETERS,
    bounds,
    parameters_to_vector,
)
from rubem.calibration.runner import (
    EVALUATION_COLUMNS,
    CalibrationError,
    CalibrationSettings,
    _population_size,
    _Progress,
    calibrate,
)
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.model_configuration_file import ModelConfigurationFile
from rubem.configuration.model_configuration_file_v1 import ModelConfigurationFileV1
from tests.helpers.config import REPO_ROOT
from tests.helpers.synthetic import write_synthetic_dataset

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
    def test_the_run_directory_holds_the_three_artifacts(self, calibrated):
        _, result = calibrated

        assert result.run_dir.is_dir()
        assert result.evaluations_csv.is_file()
        assert result.result_json.is_file()
        assert result.calibrated_config.is_file()
        assert result.message
        assert result.generations == 1


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
        self, tmp_path, caplog, capfd
    ):
        evaluations = tmp_path / "evaluations"
        evaluations.mkdir()
        (evaluations / "one.json").write_text("{}", encoding="utf8")
        progress = _Progress(evaluations)

        with caplog.at_level(logging.INFO, logger="rubem.calibration.runner"):
            stop = progress(scipy_optimize.OptimizeResult(fun=12.5, nit=3))

        assert stop is False, "the callback never halts the search"
        assert progress.generations == 3
        assert "Generation 3" in caplog.text
        assert "12.5" in caplog.text
        assert "1 evaluation" in caplog.text
        assert capfd.readouterr().out == "", "the library logs, it does not print"


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

        # Same seed, same initial population, same candidates, in the same order:
        # the table of a calibration is a function of its settings alone. Only
        # the identifiers and the process ids differ between the two runs.
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
        foreign = tmp_path / "foreign.csv"
        foreign.write_text("0;A;B\n1;1.0;2.0\n2;2.0;3.0\n3;3.0;4.0\n", encoding="utf8")

        with pytest.raises(CalibrationError, match="no station in common"):
            dataset.calibrate(observed=foreign, maxiter=1)

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
    @pytest.mark.parametrize("popsize", [1, 5, 15, 16])
    @pytest.mark.parametrize("init", ["sobol", "latinhypercube", "random"])
    def test_the_announced_population_is_the_one_scipy_builds(self, popsize, init):
        # The announced number is what the command line reports as the budget,
        # so it has to be SciPy's own arithmetic and not an approximation of it.
        optimum = scipy_optimize.differential_evolution(
            lambda vector: float(np.sum(vector)),
            bounds(),
            init=init,
            popsize=popsize,
            maxiter=0,
            polish=False,
            rng=0,
        )

        assert len(optimum.population) == _population_size(
            CalibrationSettings(popsize=popsize, init=init)
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
