import json
import logging
import sys

import humanize
import pytest

from rubem import __release__
from rubem.cli import main
from rubem.configuration.app_settings import AppSettings
from tests.helpers.synthetic import write_synthetic_dataset


class SettingsOverride:
    """Stand in for ``AppSettings`` with a few settings replaced.

    The command line asks the class for ``AppSettings.default()``, so the
    replacement is installed as the class and answers that call with this
    object. Every setting that is not overridden comes from the packaged
    ``appsettings.json``.
    """

    def __init__(self, **overrides):
        self.overrides = overrides
        self.packaged = AppSettings.default()

    def default(self):
        return self

    def get_setting(self, key):
        if key in self.overrides:
            return self.overrides[key]
        return self.packaged.get_setting(key)


@pytest.fixture(name="config_path")
def config_path_fixture(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(write_synthetic_dataset(str(tmp_path))), encoding="utf8")
    return path


@pytest.fixture(name="english_humanize")
def english_humanize_fixture():
    """Leave ``humanize`` in its default language whatever a test activated."""
    yield
    humanize.i18n.deactivate()


class TestCliRun:
    """Exercise the command line in process, where its output can be read."""

    @pytest.mark.unit
    def test_run_prints_the_documented_progress(
        self, tmp_path, config_path, capsys, restore_logging
    ):
        """The console output promised by doc/source/tutorials.rst."""
        main(["run", "-c", str(config_path)])

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
    def test_arguments_default_to_the_interpreter_ones(
        self, config_path, monkeypatch, capsys, restore_logging
    ):
        """The console script calls ``main()`` without arguments."""
        monkeypatch.setattr(sys, "argv", ["rubem", "run", "-s", "-c", str(config_path)])

        main()

        assert "Simulation finished successfully!" in capsys.readouterr().out

    @pytest.mark.unit
    def test_skipping_validation_says_so(self, config_path, capsys, restore_logging):
        main(["run", "-s", "-c", str(config_path)])

        output = capsys.readouterr().out
        assert "Loading configuration...\n" in output
        assert "Simulation finished successfully!" in output

    @pytest.mark.unit
    def test_a_failing_run_logs_one_traceback(
        self, config_path, monkeypatch, capsys, restore_logging
    ):
        """The library reports the failure; only the CLI prints its traceback."""
        from pcraster.framework import DynamicFramework

        def fail(self):
            raise RuntimeError("the framework failed")

        monkeypatch.setattr(DynamicFramework, "run", fail)

        with pytest.raises(SystemExit):
            main(["run", "-c", str(config_path)])

        logged = capsys.readouterr().err
        assert logged.count("Traceback (most recent call last)") == 1
        assert "Simulation failed: the framework failed" in logged

    @pytest.mark.unit
    def test_an_invalid_configuration_exits_with_one_without_a_traceback(
        self, tmp_path, capsys, restore_logging
    ):
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({}), encoding="utf8")

        with pytest.raises(SystemExit) as error:
            main(["run", "-c", str(config_path)])

        captured = capsys.readouterr().err
        assert error.value.code == 1
        assert "Invalid configuration:" in captured
        assert "SIM_TIME" in captured and "Field required" in captured
        assert "Traceback" not in captured

    @pytest.mark.unit
    def test_a_value_error_from_the_run_is_not_an_invalid_configuration(
        self, config_path, monkeypatch, capsys, restore_logging
    ):
        """A ``ValueError`` raised once the model is running is a crash, not a bad config."""
        from pcraster.framework import DynamicFramework

        def fail(self):
            raise ValueError("the framework failed")

        monkeypatch.setattr(DynamicFramework, "run", fail)

        with pytest.raises(SystemExit) as error:
            main(["run", "-c", str(config_path)])

        captured = capsys.readouterr()
        assert error.value.code == 1
        assert "RUBEM unexpectedly quit." in captured.err
        assert "Traceback (most recent call last)" in captured.err
        assert "Invalid configuration" not in captured.err

    @pytest.mark.unit
    def test_a_value_error_from_the_csv_export_is_not_an_invalid_configuration(
        self, config_path, monkeypatch, capsys, restore_logging
    ):
        """A ``ValueError`` from the post-run CSV export happens after a successful run."""

        def fail(*args, **kwargs):
            raise ValueError("cannot export the tables")

        monkeypatch.setattr("rubem.core.tss2csv", fail)

        with pytest.raises(SystemExit) as error:
            main(["run", "-c", str(config_path)])

        captured = capsys.readouterr()
        assert error.value.code == 1
        # The framework run itself succeeded; only the export afterwards failed.
        assert "Elapsed time:" in captured.out
        assert "RUBEM unexpectedly quit." in captured.err
        assert "Traceback (most recent call last)" in captured.err
        assert "Invalid configuration" not in captured.err

    @pytest.mark.unit
    def test_an_interrupted_run_exits_with_two(
        self, config_path, monkeypatch, capsys, restore_logging
    ):
        from pcraster.framework import DynamicFramework

        def interrupt(self):
            raise KeyboardInterrupt

        monkeypatch.setattr(DynamicFramework, "run", interrupt)

        with pytest.raises(SystemExit) as error:
            main(["run", "-c", str(config_path)])

        captured = capsys.readouterr()
        assert error.value.code == 2
        assert "RUBEM was interrupted by the user." in captured.err
        assert "Elapsed time:" in captured.out


class TestCliArguments:
    @pytest.mark.unit
    @pytest.mark.parametrize("flag", ["--version", "-V"])
    def test_version_is_printed_and_exits_cleanly(self, capsys, restore_logging, flag):
        with pytest.raises(SystemExit) as error:
            main([flag])

        assert error.value.code == 0
        assert capsys.readouterr().out == f"RUBEM v{__release__}\n"


class TestConfigSchema:
    @pytest.mark.unit
    def test_prints_the_legacy_schema_as_json(self, capsys, restore_logging):
        import json

        main(["config", "schema", "--format", "legacy"])

        schema = json.loads(capsys.readouterr().out)
        assert schema["title"] == "ModelConfigurationFile"
        assert set(schema["required"]) >= {"SIM_TIME", "RASTERS", "TABLES"}

    @pytest.mark.unit
    def test_1_0_is_the_default_format(self, capsys, restore_logging):
        import json

        main(["config", "schema"])

        assert "simulation_period" in json.loads(capsys.readouterr().out)["properties"]

    @pytest.mark.unit
    def test_an_unknown_format_is_rejected(self, capsys, restore_logging):
        with pytest.raises(SystemExit) as error:
            main(["config", "schema", "--format", "yaml"])

        assert error.value.code == 2

    @pytest.mark.unit
    def test_the_configuration_file_is_required(self, capsys, restore_logging):
        with pytest.raises(SystemExit) as error:
            main(["run"])

        assert error.value.code == 2
        assert "Missing option '-c' / '--configfile'" in capsys.readouterr().err

    @pytest.mark.unit
    def test_no_arguments_prints_the_help(self, capsys, restore_logging):
        with pytest.raises(SystemExit) as error:
            main([])

        assert error.value.code == 2
        output = capsys.readouterr()
        assert "Usage: rubem [OPTIONS] COMMAND [ARGS]..." in output.out + output.err
        assert "run" in output.out + output.err and "config" in output.out + output.err

    @pytest.mark.unit
    def test_help_lists_the_commands_and_the_epilog(self, capsys, restore_logging):
        with pytest.raises(SystemExit) as error:
            main(["--help"])

        assert error.value.code == 0
        output = capsys.readouterr().out
        assert "Run a simulation from a configuration file." in output
        assert "ABSOLUTELY NO WARRANTY" in output

    @pytest.mark.unit
    def test_an_unknown_command_is_rejected(self, capsys, restore_logging):
        with pytest.raises(SystemExit) as error:
            main(["bogus"])

        assert error.value.code == 2
        assert "No such command 'bogus'" in capsys.readouterr().err

    @pytest.mark.unit
    def test_the_legacy_spelling_still_runs_with_a_deprecation_warning(
        self, config_path, capsys, restore_logging
    ):
        with pytest.warns(DeprecationWarning, match="rubem run -c"):
            main(["-s", "-c", str(config_path)])

        captured = capsys.readouterr()
        assert "Simulation finished successfully!" in captured.out
        assert "is deprecated; use 'rubem run -c <config>'" in captured.err

    @pytest.mark.unit
    def test_the_legacy_spelling_needs_the_configuration_option(self, capsys, restore_logging):
        """Bare unknown options are not mapped to ``run``: the error names the command line."""
        with pytest.raises(SystemExit) as error:
            main(["-s"])

        assert error.value.code == 2
        assert "No such option: -s" in capsys.readouterr().err

    @pytest.mark.unit
    def test_a_missing_configuration_file_is_rejected_before_anything_runs(
        self, tmp_path, capsys, restore_logging
    ):
        missing = tmp_path / "missing.json"

        with pytest.raises(SystemExit) as error:
            main(["run", "-c", str(missing)])

        captured = capsys.readouterr()
        assert error.value.code == 2
        assert f'Specified file path "{missing}" does not exist.' in captured.err
        assert "Loading configuration" not in captured.out


class TestCliSettings:
    @pytest.mark.unit
    def test_a_custom_logging_configuration_is_applied(
        self, config_path, monkeypatch, capsys, restore_logging
    ):
        """A ``logging`` block in the settings replaces the default console setup."""
        monkeypatch.setattr(
            "rubem.cli.AppSettings",
            SettingsOverride(
                logging={
                    "version": 1,
                    "formatters": {"custom": {"format": "custom-format %(message)s"}},
                    "handlers": {
                        "console": {
                            "class": "logging.StreamHandler",
                            "formatter": "custom",
                            "level": "INFO",
                        }
                    },
                    "root": {"handlers": ["console"], "level": "INFO"},
                }
            ),
        )

        main(["run", "-s", "-c", str(config_path)])

        assert logging.getLogger().level == logging.INFO
        assert "custom-format RUBEM successfully finished!" in capsys.readouterr().err

    @pytest.mark.unit
    def test_the_configured_language_localizes_the_elapsed_time(
        self, config_path, monkeypatch, capsys, restore_logging, english_humanize
    ):
        monkeypatch.setattr("rubem.cli.AppSettings", SettingsOverride(i18n={"language": "pt_BR"}))

        main(["run", "-s", "-c", str(config_path)])

        output = capsys.readouterr().out
        assert "Elapsed time:" in output
        assert "segundo" in output
        assert "second" not in output

    @pytest.mark.unit
    def test_an_unavailable_language_is_reported_and_english_is_kept(
        self, config_path, monkeypatch, capsys, restore_logging, english_humanize
    ):
        monkeypatch.setattr("rubem.cli.AppSettings", SettingsOverride(i18n={"language": "xx_XX"}))

        main(["run", "-s", "-c", str(config_path)])

        captured = capsys.readouterr()
        assert "Failed to set language" in captured.err
        assert "second" in captured.out

    @pytest.mark.unit
    def test_english_needs_no_activation(self, config_path, monkeypatch, capsys, restore_logging):
        def refuse(language):
            raise AssertionError(f"activate called for {language}")

        monkeypatch.setattr(humanize.i18n, "activate", refuse)
        monkeypatch.setattr("rubem.cli.AppSettings", SettingsOverride(i18n={"language": "en_US"}))

        main(["run", "-s", "-c", str(config_path)])

        assert "Simulation finished successfully!" in capsys.readouterr().out
