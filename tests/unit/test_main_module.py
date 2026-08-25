import os
import runpy
import subprocess
import sys

import pytest

import rubem
from tests.helpers.config import REPO_ROOT


class TestMainModule:
    @pytest.mark.unit
    def test_run_as_script_invokes_cli_main_once(self, monkeypatch):
        calls = []

        def recorder(*args, **kwargs):
            calls.append((args, kwargs))

        monkeypatch.setattr("rubem.cli.main", recorder)
        monkeypatch.setattr(sys, "argv", ["rubem", "--version"])

        runpy.run_module("rubem", run_name="__main__", alter_sys=True)

        assert calls == [((), {})]

    @pytest.mark.unit
    def test_module_invocation_version_flag(self, tmp_path):
        env = dict(os.environ)
        env["PYTHONPATH"] = REPO_ROOT

        result = subprocess.run(
            [sys.executable, "-m", "rubem", "--version"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0
        assert result.stdout.strip() == f"RUBEM v{rubem.__release__}"

    @pytest.mark.unit
    def test_module_invocation_without_arguments_prints_the_help(self, tmp_path):
        env = dict(os.environ)
        env["PYTHONPATH"] = REPO_ROOT

        result = subprocess.run(
            [sys.executable, "-m", "rubem"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 2
        assert "Usage: rubem [OPTIONS] COMMAND [ARGS]..." in result.stdout + result.stderr
