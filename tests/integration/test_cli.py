import json
import os
import subprocess
import sys
import tempfile

import pytest

from tests.helpers.compare import compare_csv, compare_rasters
from tests.helpers.config import (
    CSV_GOLDENS,
    GOLDEN_DIR,
    RASTER_GOLDENS,
    REPO_ROOT,
    TIFF_GOLDENS,
    base_model_config,
)

RUBEM_ENTRY = os.path.join(REPO_ROOT, "rubem")


def run_cli(*args):
    return subprocess.check_output([sys.executable, RUBEM_ENTRY, *args], cwd=REPO_ROOT)


def run_cli_capture(*args):
    """Run the CLI on the packaged settings without raising, capturing both streams."""
    env = dict(os.environ)
    env.pop("PYTHON_ENVIRONMENT", None)
    return subprocess.run(
        [sys.executable, RUBEM_ENTRY, *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class TestCliApp:
    @pytest.mark.integration
    def test_cli_app_help_ext(self):
        result = run_cli("--help")
        assert b"usage: rubem [-h] -c CONFIGFILE [-V] [-s]" in result

    @pytest.mark.integration
    def test_cli_app_help_short(self):
        result = run_cli("-h")
        assert b"usage: rubem [-h] -c CONFIGFILE [-V] [-s]" in result

    @pytest.mark.integration
    def test_cli_app_version_ext(self):
        result = run_cli("--version")
        assert b"RUBEM v" in result

    @pytest.mark.integration
    def test_cli_app_version_short(self):
        result = run_cli("-V")
        assert b"RUBEM v" in result

    @pytest.mark.integration
    def test_cli_app_no_args(self):
        with pytest.raises(subprocess.CalledProcessError):
            run_cli()

    @pytest.mark.integration
    def test_cli_app_invalid_args(self):
        with pytest.raises(subprocess.CalledProcessError):
            run_cli("-c", "invalid_path")

    @pytest.mark.integration
    def test_cli_app_not_a_file_config(self):
        with pytest.raises(subprocess.CalledProcessError):
            run_cli("-c", os.path.dirname(__file__))

    @pytest.mark.integration
    def test_cli_app_invalid_extension_config_json_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "bagheera.jaguar")
            with open(file=config_path, mode="w", encoding="utf8") as f:
                f.write(json.dumps(base_model_config(temp_dir)))

            with pytest.raises(subprocess.CalledProcessError):
                run_cli("-c", config_path)

    @pytest.mark.integration
    def test_cli_app_invalid_config_json_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            with open(file=config_path, mode="w", encoding="utf8") as f:
                f.write("invalid_json")

            with pytest.raises(subprocess.CalledProcessError):
                run_cli("-c", config_path)

    @pytest.mark.integration
    def test_cli_app_empty_config_json_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            with open(file=config_path, mode="w", encoding="utf8") as f:
                f.write(json.dumps({}))

            with pytest.raises(subprocess.CalledProcessError):
                run_cli("-c", config_path)

    @pytest.mark.integration
    def test_cli_app_reports_unexpected_failure(self):
        """A failed run must say so on the console, traceback included.

        The packaged ``appsettings.json`` carries no ``logging`` block, so the CLI
        falls back to its built-in configuration. That configuration must keep the
        loggers created at import time -- ``rubem.cli``'s own among them -- enabled,
        otherwise these diagnostics are dropped and the run fails in silence.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            with open(file=config_path, mode="w", encoding="utf8") as f:
                f.write("invalid_json")

            result = run_cli_capture("-c", config_path)

            assert result.returncode == 1
            assert "RUBEM unexpectedly quit." in result.stderr
            assert "Traceback (most recent call last):" in result.stderr

    def _run_and_compare(self, temp_dir, *cli_flags):
        config_path = os.path.join(temp_dir, "config.json")
        with open(file=config_path, mode="w", encoding="utf8") as f:
            f.write(json.dumps(base_model_config(temp_dir)))

        run_cli(*cli_flags, "-c", config_path)

        for raster_file in RASTER_GOLDENS + TIFF_GOLDENS:
            candidate = os.path.join(temp_dir, raster_file)
            assert os.path.exists(candidate), f"missing output {raster_file}"
            result = compare_rasters(candidate, os.path.join(GOLDEN_DIR, raster_file))
            assert result.equal, f"{raster_file}:\n{result.report()}"

        for table_file in CSV_GOLDENS:
            candidate = os.path.join(temp_dir, table_file)
            assert os.path.exists(candidate), f"missing output {table_file}"
            result = compare_csv(candidate, os.path.join(GOLDEN_DIR, table_file))
            assert result.equal, f"{table_file}:\n{result.report()}"

    @pytest.mark.slow
    @pytest.mark.integration
    def test_cli_app_valid_config_json_file(self):
        """Run the model on the synthetic dataset and compare with the goldens.

        .. note::

            To obtain reproducible results, the LDD raster must be set.
            See the `LDD` section in the `config.json` file.
            Refer to LabSid-USP/RUBEM#120 for more information.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            self._run_and_compare(temp_dir)

    @pytest.mark.slow
    @pytest.mark.integration
    def test_cli_app_reports_progress_on_stdout(self):
        """The console output documented in doc/source/tutorials.rst."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            with open(file=config_path, mode="w", encoding="utf8") as f:
                f.write(json.dumps(base_model_config(temp_dir)))

            output = run_cli("-c", config_path).decode("utf8")

        for expected in (
            "Loading configuration and validating inputs...",
            "Simulation started...",
            "## Timestep 1 of 2",
            "Simulation finished successfully!",
            "Elapsed time:",
        ):
            assert expected in output, f"missing progress line: {expected!r}\n{output}"

    @pytest.mark.slow
    @pytest.mark.integration
    def test_cli_app_skip_input_data_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self._run_and_compare(temp_dir, "-s")

    @pytest.mark.slow
    @pytest.mark.integration
    def test_cli_app_runs_from_any_working_directory(self):
        """The run must not depend on, or change, the caller's cwd."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = os.path.join(temp_dir, "out")
            os.makedirs(output_dir)
            scratch_cwd = os.path.join(temp_dir, "elsewhere")
            os.makedirs(scratch_cwd)
            config_path = os.path.join(temp_dir, "config.json")
            with open(file=config_path, mode="w", encoding="utf8") as f:
                f.write(json.dumps(base_model_config(output_dir)))

            subprocess.check_output(
                [sys.executable, RUBEM_ENTRY, "-c", config_path], cwd=scratch_cwd
            )

            assert not os.listdir(scratch_cwd)
            for raster_file in RASTER_GOLDENS + TIFF_GOLDENS:
                result = compare_rasters(
                    os.path.join(output_dir, raster_file),
                    os.path.join(GOLDEN_DIR, raster_file),
                )
                assert result.equal, f"{raster_file}:\n{result.report()}"
            for table_file in CSV_GOLDENS:
                result = compare_csv(
                    os.path.join(output_dir, table_file),
                    os.path.join(GOLDEN_DIR, table_file),
                )
                assert result.equal, f"{table_file}:\n{result.report()}"
