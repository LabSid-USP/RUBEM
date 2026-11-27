import json
from pathlib import Path

import pytest

from rubem.cli import main
from tests.helpers.synthetic import write_synthetic_dataset


@pytest.fixture(name="config_path")
def config_path_fixture(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(write_synthetic_dataset(str(tmp_path))), encoding="utf8")
    return path


@pytest.fixture(name="observed_path")
def observed_path_fixture(tmp_path):
    path = tmp_path / "observed.csv"
    path.write_text("0;1\n1;2.0\n2;3.0\n", encoding="utf8")
    return path


class FakeCalibration:
    """Stand in for ``rubem.calibration.runner.calibrate``.

    It records the arguments the command line built and answers with a result
    whose files do not have to exist: the command only prints their paths.
    """

    def __init__(self, run_dir, best_nse=0.87):
        from rubem.calibration.runner import CalibrationResult

        self.calls = []
        self.result = CalibrationResult(
            best_parameters={
                "alpha": 4.5,
                "beta": 0.5,
                "w_1": 0.333,
                "w_2": 0.333,
                "w_3": 0.334,
                "rcd": 5.0,
                "f": 0.5,
                "alpha_gw": 0.5,
                "x": 0.5,
            },
            best_nse=best_nse,
            best_objective=169000.0,
            evaluations=128,
            generations=2,
            success=True,
            message="Optimization terminated successfully.",
            run_dir=Path(run_dir),
            evaluations_csv=Path(run_dir) / "evaluations.csv",
            result_json=Path(run_dir) / "result.json",
            calibrated_config=Path(run_dir) / "config-calibrated.json",
            best_series=Path(run_dir) / "best_arn.csv",
            stations_csv=Path(run_dir) / "stations.csv",
        )

    def __call__(self, config_path, observed_path, run_dir, settings):
        self.calls.append((config_path, observed_path, run_dir, settings))
        return self.result


@pytest.fixture(name="fake_calibration")
def fake_calibration_fixture(tmp_path, monkeypatch):
    fake = FakeCalibration(tmp_path / "calibration")
    monkeypatch.setattr("rubem.calibration.runner.calibrate", fake)
    return fake


class TestCliCalibrateArgumentsReachTheRunner:
    @pytest.mark.unit
    def test_the_paths_and_the_documented_defaults(
        self, config_path, observed_path, tmp_path, fake_calibration, restore_logging
    ):
        run_dir = tmp_path / "calibration"

        main(
            [
                "calibrate",
                "-c",
                str(config_path),
                "--observed",
                str(observed_path),
                "-o",
                str(run_dir),
            ]
        )

        (given_config, given_observed, given_run_dir, settings) = fake_calibration.calls[0]
        assert Path(given_config) == config_path
        assert Path(given_observed) == observed_path
        assert Path(given_run_dir) == run_dir
        assert settings.variable == "arn"
        assert settings.spinup_steps == 0
        assert settings.maxiter == 100
        assert settings.popsize == 15
        assert settings.seed is None
        assert settings.temp_dir is None
        assert settings.init == "sobol"
        assert settings.strategy == "best1exp"
        assert settings.polish is False
        assert settings.bounds is None
        assert settings.fixed is None
        assert settings.stations is None
        assert settings.allow_blocking_problems is False

    @pytest.mark.unit
    def test_every_option_reaches_the_settings(
        self, config_path, observed_path, tmp_path, fake_calibration, restore_logging
    ):
        temp_dir = tmp_path / "scratch"

        main(
            [
                "calibrate",
                "-c",
                str(config_path),
                "--observed",
                str(observed_path),
                "-o",
                str(tmp_path / "calibration"),
                "--variable",
                "rnf",
                "--spinup-steps",
                "12",
                "--maxiter",
                "3",
                "--popsize",
                "4",
                "--seed",
                "7",
                "--workers",
                "2",
                "--temp-dir",
                str(temp_dir),
            ]
        )

        settings = fake_calibration.calls[0][3]
        assert settings.variable == "rnf"
        assert settings.spinup_steps == 12
        assert settings.maxiter == 3
        assert settings.popsize == 4
        assert settings.seed == 7
        assert settings.workers == 2
        assert Path(settings.temp_dir) == temp_dir

    @pytest.mark.unit
    def test_the_runner_keeps_its_own_default_worker_count(
        self, config_path, observed_path, tmp_path, fake_calibration, monkeypatch, restore_logging
    ):
        """Without ``--workers`` the command must not override the runner's default.

        The settings class is replaced by one whose default differs from the
        ``None`` the option carries, so forwarding the option unconditionally
        would be visible here.
        """
        from dataclasses import dataclass

        from rubem.calibration.runner import CalibrationSettings

        @dataclass(frozen=True)
        class SettingsWithAWorkerDefault(CalibrationSettings):
            workers: int | None = 7

        monkeypatch.setattr(
            "rubem.calibration.runner.CalibrationSettings", SettingsWithAWorkerDefault
        )

        main(
            [
                "calibrate",
                "-c",
                str(config_path),
                "--observed",
                str(observed_path),
                "-o",
                str(tmp_path / "calibration"),
            ]
        )

        assert fake_calibration.calls[0][3].workers == 7


class TestCliCalibrateOutput:
    @pytest.mark.unit
    def test_the_documented_progress_and_summary_are_printed(
        self, config_path, observed_path, tmp_path, fake_calibration, capsys, restore_logging
    ):
        main(
            [
                "calibrate",
                "-c",
                str(config_path),
                "--observed",
                str(observed_path),
                "-o",
                str(tmp_path / "calibration"),
            ]
        )

        output = capsys.readouterr().out
        result = fake_calibration.result
        for expected in (
            "Loading configuration and validating inputs...",
            "Calibration started...",
            "Calibration finished successfully!",
            "Best NSE: 0.87",
            "Best objective: 169000",
            "Evaluations: 128",
            "Generations: 2",
            str(result.evaluations_csv),
            str(result.result_json),
            str(result.calibrated_config),
            f"Observed summary: {result.run_dir / 'observed.csv'}",
            f"Stations table: {result.stations_csv}",
            f"Best candidate series: {result.best_series}",
        ):
            assert expected in output, f"missing line: {expected!r}\n{output}"

    @pytest.mark.unit
    def test_a_run_without_a_usable_nse_says_so(
        self, config_path, observed_path, tmp_path, monkeypatch, capsys, restore_logging
    ):
        fake = FakeCalibration(tmp_path / "calibration", best_nse=None)
        monkeypatch.setattr("rubem.calibration.runner.calibrate", fake)

        main(
            [
                "calibrate",
                "-c",
                str(config_path),
                "--observed",
                str(observed_path),
                "-o",
                str(tmp_path / "calibration"),
            ]
        )

        assert "Best NSE: n/a" in capsys.readouterr().out


class TestCliCalibrateFailures:
    @pytest.mark.unit
    def test_a_calibration_error_exits_with_one_without_a_traceback(
        self, config_path, observed_path, tmp_path, monkeypatch, capsys, restore_logging
    ):
        from rubem.calibration.runner import CalibrationError

        def fail(*args, **kwargs):
            raise CalibrationError("every evaluation failed: no such variable")

        monkeypatch.setattr("rubem.calibration.runner.calibrate", fail)

        with pytest.raises(SystemExit) as error:
            main(
                [
                    "calibrate",
                    "-c",
                    str(config_path),
                    "--observed",
                    str(observed_path),
                    "-o",
                    str(tmp_path / "calibration"),
                ]
            )

        captured = capsys.readouterr().err
        assert error.value.code == 1
        assert "every evaluation failed: no such variable" in captured
        assert "Traceback" not in captured

    @pytest.mark.unit
    def test_an_unexpected_failure_logs_one_traceback(
        self, config_path, observed_path, tmp_path, monkeypatch, capsys, restore_logging
    ):
        def fail(*args, **kwargs):
            raise RuntimeError("the pool died")

        monkeypatch.setattr("rubem.calibration.runner.calibrate", fail)

        with pytest.raises(SystemExit) as error:
            main(
                [
                    "calibrate",
                    "-c",
                    str(config_path),
                    "--observed",
                    str(observed_path),
                    "-o",
                    str(tmp_path / "calibration"),
                ]
            )

        captured = capsys.readouterr().err
        assert error.value.code == 1
        assert captured.count("Traceback (most recent call last)") == 1
        assert "RUBEM unexpectedly quit." in captured

    @pytest.mark.unit
    def test_a_missing_scipy_exits_with_the_installation_guidance(
        self, config_path, observed_path, tmp_path, monkeypatch, capsys, restore_logging
    ):
        monkeypatch.setattr("rubem._deps.missing_calibration_deps", lambda: ["scipy"])

        with pytest.raises(SystemExit) as error:
            main(
                [
                    "calibrate",
                    "-c",
                    str(config_path),
                    "--observed",
                    str(observed_path),
                    "-o",
                    str(tmp_path / "calibration"),
                ]
            )

        message = str(error.value)
        assert "scipy" in message
        assert 'pip install "rubem[calibration]"' in message

    @pytest.mark.unit
    def test_an_interrupted_calibration_exits_with_two(
        self, config_path, observed_path, tmp_path, monkeypatch, capsys, restore_logging
    ):
        def interrupt(*args, **kwargs):
            raise KeyboardInterrupt

        monkeypatch.setattr("rubem.calibration.runner.calibrate", interrupt)

        with pytest.raises(SystemExit) as error:
            main(
                [
                    "calibrate",
                    "-c",
                    str(config_path),
                    "--observed",
                    str(observed_path),
                    "-o",
                    str(tmp_path / "calibration"),
                ]
            )

        captured = capsys.readouterr().err
        assert error.value.code == 2
        assert "RUBEM was interrupted by the user." in captured
        assert "Traceback" not in captured

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("option", "value"),
        [
            ("--maxiter", "0"),
            ("--maxiter", "-1"),
            ("--popsize", "0"),
            ("--popsize", "-1"),
            ("--workers", "0"),
            ("--workers", "-1"),
            ("--spinup-steps", "-1"),
        ],
    )
    def test_a_search_size_outside_its_range_is_rejected(
        self, config_path, observed_path, tmp_path, fake_calibration, option, value, restore_logging
    ):
        """A generation count, a population and a worker count all start at one."""
        with pytest.raises(SystemExit) as error:
            main(
                [
                    "calibrate",
                    "-c",
                    str(config_path),
                    "--observed",
                    str(observed_path),
                    "-o",
                    str(tmp_path / "calibration"),
                    option,
                    value,
                ]
            )

        assert error.value.code == 2
        assert not fake_calibration.calls

    @pytest.mark.unit
    def test_a_negative_spin_up_is_rejected(
        self, config_path, observed_path, tmp_path, fake_calibration, capsys, restore_logging
    ):
        with pytest.raises(SystemExit) as error:
            main(
                [
                    "calibrate",
                    "-c",
                    str(config_path),
                    "--observed",
                    str(observed_path),
                    "-o",
                    str(tmp_path / "calibration"),
                    "--spinup-steps",
                    "-1",
                ]
            )

        assert error.value.code == 2
        assert not fake_calibration.calls

    @pytest.mark.unit
    def test_a_missing_observed_file_is_rejected_before_anything_runs(
        self, config_path, tmp_path, fake_calibration, capsys, restore_logging
    ):
        missing = tmp_path / "missing.csv"

        with pytest.raises(SystemExit) as error:
            main(
                [
                    "calibrate",
                    "-c",
                    str(config_path),
                    "--observed",
                    str(missing),
                    "-o",
                    str(tmp_path / "calibration"),
                ]
            )

        assert error.value.code == 2
        assert not fake_calibration.calls
        assert "Loading configuration" not in capsys.readouterr().out

    @pytest.mark.unit
    def test_an_incomplete_command_is_not_mapped_onto_the_legacy_spelling(
        self, config_path, capsys, restore_logging
    ):
        """``calibrate`` is a subcommand, not the deprecated bare ``-c`` form."""
        with pytest.raises(SystemExit) as error:
            main(["calibrate", "-c", str(config_path)])

        captured = capsys.readouterr()
        assert error.value.code == 2
        assert "Missing option '--observed'" in captured.err
        assert "is deprecated" not in captured.err


class TestCliCalibrateHelp:
    @pytest.mark.unit
    def test_the_command_is_listed_in_the_help(self, capsys, restore_logging):
        with pytest.raises(SystemExit) as error:
            main(["--help"])

        assert error.value.code == 0
        assert "calibrate" in capsys.readouterr().out

    @pytest.mark.unit
    def test_the_help_documents_every_option(self, capsys, restore_logging):
        with pytest.raises(SystemExit) as error:
            main(["calibrate", "--help"])

        assert error.value.code == 0
        output = capsys.readouterr().out
        assert "Calibrate the model parameters against an observed series." in output
        for option in (
            "--configfile",
            "--observed",
            "--run-dir",
            "--variable",
            "--spinup-steps",
            "--maxiter",
            "--popsize",
            "--seed",
            "--workers",
            "--temp-dir",
            "--bound",
            "--fix",
            "--stations",
            "--init",
            "--strategy",
            "--polish",
            "--no-polish",
        ):
            assert option in output, f"missing option: {option}\n{output}"

    @pytest.mark.unit
    def test_importing_the_command_line_does_not_need_scipy(self):
        """The CLI module stays importable without the optional extra."""
        import subprocess
        import sys

        completed = subprocess.run(
            [sys.executable, "-c", "import sys, rubem.cli; print('scipy' in sys.modules)"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            check=True,
        )
        assert completed.stdout.strip() == "False"


class TestCliCalibrateDecisionSpaceOptions:
    @pytest.mark.unit
    def test_the_bounds_the_fixed_parameters_and_the_stations_reach_the_settings(
        self, config_path, observed_path, tmp_path, fake_calibration, restore_logging
    ):
        main(
            [
                "calibrate",
                "-c",
                str(config_path),
                "--observed",
                str(observed_path),
                "-o",
                str(tmp_path / "calibration"),
                "--bound",
                "rcd=2:5",
                "--bound",
                "alpha=1:10",
                "--fix",
                "x=0",
                "--stations",
                "1, 2 ,3",
                "--init",
                "latinhypercube",
                "--strategy",
                "rand1bin",
                "--polish",
            ]
        )

        settings = fake_calibration.calls[0][3]
        assert settings.bounds == {"rcd": (2.0, 5.0), "alpha": (1.0, 10.0)}
        assert settings.fixed == {"x": 0.0}
        # The ids are read as strings and the spacing around the commas is not
        # part of them.
        assert settings.stations == ("1", "2", "3")
        assert settings.init == "latinhypercube"
        assert settings.strategy == "rand1bin"
        assert settings.polish is True

    @pytest.mark.unit
    def test_the_modflow_names_reach_the_settings_as_they_are_written(
        self, config_path, observed_path, tmp_path, fake_calibration, restore_logging
    ):
        main(
            [
                "calibrate",
                "-c",
                str(config_path),
                "--observed",
                str(observed_path),
                "-o",
                str(tmp_path / "calibration"),
                "--bound",
                "modflow.layers.1.specific_yield=0.05:0.3",
                "--bound",
                "modflow.layers.1.kh.2=0.05:0.5",
                "--fix",
                "modflow.river.1.conductance=0.387",
            ]
        )

        settings = fake_calibration.calls[0][3]
        # The command line only parses; the calibration resolves the names
        # against the MODFLOW section of the configuration.
        assert settings.bounds == {
            "modflow.layers.1.specific_yield": (0.05, 0.3),
            "modflow.layers.1.kh.2": (0.05, 0.5),
        }
        assert settings.fixed == {"modflow.river.1.conductance": 0.387}

    @pytest.mark.unit
    def test_the_help_of_the_bounds_names_the_modflow_parameters(self, capsys, restore_logging):
        with pytest.raises(SystemExit) as error:
            main(["calibrate", "--help"])

        assert error.value.code == 0
        output = " ".join(capsys.readouterr().out.split())
        assert "MODFLOW" in output
        assert "modflow.layers" in output

    @pytest.mark.unit
    def test_no_polish_is_the_default_and_can_be_written_out(
        self, config_path, observed_path, tmp_path, fake_calibration, restore_logging
    ):
        main(
            [
                "calibrate",
                "-c",
                str(config_path),
                "--observed",
                str(observed_path),
                "-o",
                str(tmp_path / "calibration"),
                "--no-polish",
            ]
        )

        assert fake_calibration.calls[0][3].polish is False

    @pytest.mark.unit
    def test_allow_blocking_problems_reaches_the_settings(
        self, config_path, observed_path, tmp_path, fake_calibration, restore_logging
    ):
        main(
            [
                "calibrate",
                "-c",
                str(config_path),
                "--observed",
                str(observed_path),
                "-o",
                str(tmp_path / "calibration"),
                "--allow-blocking-problems",
            ]
        )

        assert fake_calibration.calls[0][3].allow_blocking_problems is True

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("arguments", "message"),
        [
            (["--bound", "rcd=2"], "NAME=MIN:MAX"),
            (["--bound", "rcd:2:5"], "NAME=MIN:MAX"),
            (["--bound", "=2:5"], "NAME=MIN:MAX"),
            (["--bound", "rcd=a:5"], "is not a number"),
            (["--bound", "rcd=2:nan"], "is not a finite number"),
            (["--bound", "rcd=2:5", "--bound", "rcd=3:4"], "more than once"),
            (["--fix", "x"], "NAME=VALUE"),
            (["--fix", "=0"], "NAME=VALUE"),
            (["--fix", "x=zero"], "is not a number"),
            (["--fix", "x=0", "--fix", "x=1"], "more than once"),
            (["--stations", ",1"], "ID[,ID...]"),
            (["--stations", ""], "ID[,ID...]"),
            (["--init", "quasirandom"], "quasirandom"),
        ],
    )
    def test_a_malformed_option_is_rejected_with_the_form_it_expects(
        self,
        config_path,
        observed_path,
        tmp_path,
        fake_calibration,
        capsys,
        restore_logging,
        arguments,
        message,
    ):
        with pytest.raises(SystemExit) as error:
            main(
                [
                    "calibrate",
                    "-c",
                    str(config_path),
                    "--observed",
                    str(observed_path),
                    "-o",
                    str(tmp_path / "calibration"),
                    *arguments,
                ]
            )

        assert error.value.code == 2
        assert message in capsys.readouterr().err
        assert not fake_calibration.calls


class TestCliCalibrateProgress:
    @pytest.mark.unit
    def test_the_progress_logger_is_routed_to_standard_output(self, capsys, restore_logging):
        """The lines a calibration reports reach the terminal verbatim."""
        import logging

        from rubem.cli import setup_logging

        setup_logging()
        logging.getLogger("rubem.progress").info("Generation 7: best objective 1.")

        captured = capsys.readouterr()
        assert captured.out == "Generation 7: best objective 1.\n"
        assert captured.err == "", "the progress is not a diagnostic"

    @pytest.mark.unit
    @pytest.mark.slow
    def test_a_real_calibration_prints_the_budget_and_one_line_per_generation(
        self, tmp_path, capsys, restore_logging
    ):
        """The whole command, on the synthetic dataset, with a search of two generations.

        The observations are the series the configuration itself wrote, so the
        search has an optimum to find and every evaluation succeeds. The
        population is the smallest a Sobol' initialization builds for eight free
        parameters, which keeps the run to a few dozen model runs.
        """
        pytest.importorskip("scipy.optimize")

        from rubem.api import Model

        config = write_synthetic_dataset(str(tmp_path), timesteps=3)
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config), encoding="utf8")
        observed = tmp_path / "observed.csv"
        observed.write_bytes(Model.from_config(config).run().time_series["arn"][0].read_bytes())
        run_dir = tmp_path / "calibration"

        main(
            [
                "calibrate",
                "-c",
                str(config_file),
                "--observed",
                str(observed),
                "-o",
                str(run_dir),
                "--maxiter",
                "1",
                "--popsize",
                "1",
                "--workers",
                "2",
                "--seed",
                "1",
                "--temp-dir",
                str(tmp_path / "temp"),
            ]
        )

        output = capsys.readouterr().out
        assert "Calibrating 8 free parameter(s)" in output, output
        assert "compares 3 time step(s)" in output, output
        assert "Generation 1:" in output, output
        assert "best NSE" in output, output
        assert "Calibration finished after" in output, output
        assert "Calibration finished successfully!" in output
        assert (run_dir / "observed.csv").is_file()
        assert (run_dir / "stations.csv").is_file()
        assert (run_dir / "best_arn.csv").is_file()
