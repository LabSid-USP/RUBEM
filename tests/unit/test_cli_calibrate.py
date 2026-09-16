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
