import json
import sys

import pytest

from rubem.cli import main
from tests.helpers.synthetic import write_synthetic_dataset


class TestCliRun:
    """Exercise the command line in process, where its output can be read."""

    @pytest.mark.unit
    def test_run_prints_the_documented_progress(
        self, tmp_path, monkeypatch, capsys, restore_logging
    ):
        """The console output promised by doc/source/tutorials.rst."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(write_synthetic_dataset(str(tmp_path))), encoding="utf8")
        monkeypatch.setattr(sys, "argv", ["rubem", "-c", str(config_path)])

        main()

        output = capsys.readouterr().out
        for expected in (
            "Loading configuration and validating inputs...",
            "Simulation started...",
            "## Timestep 1 of 2",
            "Simulation finished successfully!",
            "Elapsed time:",
        ):
            assert expected in output, f"missing progress line: {expected!r}\n{output}"
        assert (tmp_path / "out" / "tss_itp.csv").is_file()

    @pytest.mark.unit
    def test_skipping_validation_says_so(self, tmp_path, monkeypatch, capsys, restore_logging):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(write_synthetic_dataset(str(tmp_path))), encoding="utf8")
        monkeypatch.setattr(sys, "argv", ["rubem", "-s", "-c", str(config_path)])

        main()

        output = capsys.readouterr().out
        assert "Loading configuration...\n" in output
        assert "Simulation finished successfully!" in output

    @pytest.mark.unit
    def test_a_failing_run_exits_with_one(self, tmp_path, monkeypatch, capsys, restore_logging):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({}), encoding="utf8")
        monkeypatch.setattr(sys, "argv", ["rubem", "-c", str(config_path)])

        with pytest.raises(SystemExit) as error:
            main()

        assert error.value.code == 1
