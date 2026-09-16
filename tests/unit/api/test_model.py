"""The public Python API: loading a configuration, running it, and what it reports."""

import json
import math
import multiprocessing
import os
import pickle
import shutil
import subprocess
import sys
import textwrap
from concurrent.futures.process import BrokenProcessPool
from inspect import signature

import numpy as np
import pydantic
import pytest

from rubem import _deps, api
from rubem.api import ConfigurationError, Model, RunResult
from rubem.configuration._problems import Problem
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.model_configuration_file import ModelConfigurationFile
from rubem.configuration.model_configuration_file_v1 import ModelConfigurationFileV1
from tests.helpers.config import REPO_ROOT
from tests.helpers.synthetic import MISSING, series_name, write_synthetic_dataset
from tests.unit.api import _child
from tests.unit.core.test_aggregation import write_zones
from tests.unit.core.test_core import expected_outputs

VARIABLES = ("itp", "bfw", "srn", "eta", "lfw", "rec", "smc", "rnf", "arn")


def reported_paths(result):
    """Every path a result reports, rasters first, then time series tables."""
    paths = [path for members in result.rasters.values() for path in members]
    paths.extend(path for tables in result.time_series.values() for path in tables)
    return paths


def reported_names(result):
    return sorted(path.name for path in reported_paths(result))


def missing_files(result):
    return [str(path) for path in reported_paths(result) if not path.is_file()]


def break_kp(config):
    """Make the first pan coefficient raster non-positive, a blocking problem."""
    import pcraster as pcr

    pcr.setclone(config["RASTERS"]["clone"])
    path = os.path.join(config["DIRECTORIES"]["kp"], series_name("kp", 1))
    pcr.report(pcr.numpy2pcr(pcr.Scalar, np.zeros((3, 3), dtype=np.float32), -9999.0), path)


def v1_document(legacy_config, **metadata):
    """The format 1.0 equivalent of a legacy configuration document."""
    legacy = ModelConfigurationFile.model_validate(legacy_config)
    return ModelConfigurationFileV1.from_legacy(legacy, metadata or None).to_dict()


def relative_to(config, base_dir):
    """The same configuration with every path relative to ``base_dir``."""
    relative = json.loads(json.dumps(config))
    for section in ("DIRECTORIES", "RASTERS", "TABLES"):
        relative[section] = {
            key: (os.path.relpath(value, base_dir) if value else value)
            for key, value in config[section].items()
        }
    return relative


def v1_document_with_time_series_formats(legacy_config, formats):
    """A format 1.0 document whose time series ask for ``formats``."""
    document = v1_document(legacy_config)
    document["model_simulation_output"]["time_series_samples"]["formats"] = list(formats)
    return document


class TestInProcessRuns:
    @pytest.mark.unit
    def test_a_run_from_a_dictionary_reports_every_file_it_wrote(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))

        result = Model.from_config(config).run()

        assert isinstance(result, RunResult)
        assert result.output_directory == tmp_path / "out"
        assert (result.first_step, result.last_step) == (1, 2)
        assert result.metadata is None, "a legacy configuration has no metadata section"
        assert math.isfinite(result.elapsed_seconds) and result.elapsed_seconds >= 0
        assert reported_names(result) == sorted(expected_outputs())
        assert not missing_files(result)

    @pytest.mark.unit
    def test_raster_members_are_grouped_by_format_in_step_order(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))

        result = Model.from_config(config).run()

        assert sorted(result.rasters) == sorted(VARIABLES)
        assert [path.name for path in result.rasters["itp"]] == [
            series_name("itp", 1),
            series_name("itp", 2),
            "itp0000001.tif",
            "itp0000002.tif",
        ]
        assert [path.name for path in result.time_series["itp"]] == ["tss_itp.csv"]

    @pytest.mark.unit
    def test_a_run_from_a_file_anchors_and_runs(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config), encoding="utf8")

        result = Model.from_file(config_file).run()

        assert result.output_directory == tmp_path / "out"
        assert not missing_files(result)

    @pytest.mark.unit
    def test_a_loaded_configuration_is_used_as_it_is(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        loaded = ModelConfiguration(config, validate_input=False)

        model = Model.from_config(loaded)

        assert model.configuration is loaded
        assert not missing_files(model.run())

    @pytest.mark.unit
    def test_a_format_1_0_run_reports_its_metadata(self, tmp_path):
        document = v1_document(write_synthetic_dataset(str(tmp_path)), title="api")

        result = Model.from_config(document).run()

        assert result.metadata == tmp_path / "out" / "metadata.json"
        assert not missing_files(result)
        written = json.loads(result.metadata.read_text(encoding="utf8"))
        assert written["version"] == "1.0" and written["title"] == "api"

    @pytest.mark.unit
    def test_the_reported_files_are_exactly_the_files_in_the_directory(self, tmp_path):
        """The description of the run must match the listing it refuses to read."""
        result = Model.from_config(write_synthetic_dataset(str(tmp_path))).run()

        assert reported_names(result) == sorted(
            path.name for path in result.output_directory.iterdir()
        )

    @pytest.mark.unit
    def test_every_reported_path_is_absolute(self, tmp_path, monkeypatch):
        """A relative output directory must not split the result in two anchors."""
        config = write_synthetic_dataset(str(tmp_path))
        config["DIRECTORIES"]["output"] = "out"
        monkeypatch.chdir(tmp_path)

        result = Model.from_config(config).run()

        assert result.output_directory == tmp_path / "out"
        assert all(path.is_absolute() for path in reported_paths(result))
        assert {path.parent for path in reported_paths(result)} == {result.output_directory}
        assert not missing_files(result)

    @pytest.mark.unit
    def test_time_series_kept_as_pcraster_tss_are_the_reported_ones(self, tmp_path):
        document = v1_document_with_time_series_formats(
            write_synthetic_dataset(str(tmp_path)), ["PCRasterTSS"]
        )

        result = Model.from_config(document).run()

        assert [path.name for path in result.time_series["itp"]] == ["tss_itp.tss"]
        assert not missing_files(result)
        assert not list(result.output_directory.glob("*.csv"))

    @pytest.mark.unit
    def test_both_time_series_formats_are_reported_csv_first(self, tmp_path):
        document = v1_document_with_time_series_formats(
            write_synthetic_dataset(str(tmp_path)), ["CSV", "PCRasterTSS"]
        )

        result = Model.from_config(document).run()

        assert [path.name for path in result.time_series["itp"]] == ["tss_itp.csv", "tss_itp.tss"]
        assert not missing_files(result)

    @pytest.mark.unit
    def test_an_aggregated_run_reports_the_tables_under_their_aggregated_names(self, tmp_path):
        """``zones`` renames the tables and writes a mapping that belongs to no variable."""
        document = v1_document(write_synthetic_dataset(str(tmp_path)))
        document["rasters"]["zones"] = write_zones(
            document, [20, 20, 20, 7, 7, 7, MISSING, MISSING, MISSING]
        )
        document["model_simulation_output"]["time_series_samples"]["aggregation"] = "zones"
        del document["rasters"]["samples"]

        result = Model.from_config(document).run()

        assert [path.name for path in result.time_series["itp"]] == ["tss_itp_zones.csv"]
        assert not missing_files(result)
        assert (result.output_directory / "zones_mapping.csv").is_file()
        assert "zones_mapping.csv" not in reported_names(result)

    @pytest.mark.unit
    def test_a_run_writes_nothing_to_stdout(self, tmp_path, capsys):
        """The library only logs; a front end is what prints."""
        Model.from_config(write_synthetic_dataset(str(tmp_path))).run()

        assert capsys.readouterr().out == ""


class TestIsolatedRuns:
    @pytest.mark.unit
    def test_two_sequential_isolated_runs_write_two_directories(self, tmp_path):
        results = []
        for name in ("first", "second"):
            base = tmp_path / name
            base.mkdir()
            results.append(Model.from_config(write_synthetic_dataset(str(base))).run_isolated())

        first, second = results
        assert first.output_directory == tmp_path / "first" / "out"
        assert second.output_directory == tmp_path / "second" / "out"
        for result in results:
            assert reported_names(result) == sorted(expected_outputs())
            assert not missing_files(result)
            assert (result.first_step, result.last_step) == (1, 2)
            assert math.isfinite(result.elapsed_seconds) and result.elapsed_seconds >= 0

    @pytest.mark.unit
    def test_the_anchor_of_a_file_crosses_the_boundary(self, tmp_path, monkeypatch):
        """The child anchors on the directory of the file, not on its own cwd."""
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps(relative_to(write_synthetic_dataset(str(tmp_path)), tmp_path)),
            encoding="utf8",
        )
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        result = Model.from_file(config_file).run_isolated()

        assert result.output_directory == tmp_path / "out"
        assert not missing_files(result)

    @pytest.mark.unit
    def test_an_explicit_base_dir_crosses_the_boundary(self, tmp_path, monkeypatch):
        """A document has no anchor of its own; the one given must travel with it."""
        config = relative_to(write_synthetic_dataset(str(tmp_path)), tmp_path)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        result = Model.from_config(config, base_dir=tmp_path).run_isolated()

        assert result.output_directory == tmp_path / "out"
        assert not missing_files(result)

    @pytest.mark.unit
    def test_the_run_happens_in_a_spawned_child_that_does_not_outlive_the_call(
        self, tmp_path, monkeypatch
    ):
        """The child is a fresh interpreter, and the executor takes it with it."""
        config = write_synthetic_dataset(str(tmp_path))
        monkeypatch.setattr(api, "_run_document", _child.record_and_run)

        result = Model.from_config(config).run_isolated()

        assert not missing_files(result)
        marker = json.loads(
            (result.output_directory / _child.MARKER_FILENAME).read_text(encoding="utf8")
        )
        assert marker["pid"] != os.getpid(), "the run must not happen in the calling process"
        assert "pcraster" in sys.modules, "the parent of this test has the model loaded"
        assert marker["preloaded"] == [], "a spawned child starts without the parent's modules"
        # The executor's worker is a multiprocessing child of this process, so an
        # empty active_children() proves it was joined; a probe with os.kill would
        # not be portable (Windows has no signal 0) and could hit a reused pid.
        assert multiprocessing.active_children() == []

    @pytest.mark.unit
    def test_a_child_that_dies_is_reported_against_run_isolated(self, tmp_path, monkeypatch):
        """A child killed mid-run, without an exception to send back."""
        model = Model.from_config(write_synthetic_dataset(str(tmp_path)), validate_input=False)
        monkeypatch.setattr(api, "_run_document", _child.die)

        with pytest.raises(RuntimeError, match="Model.run_isolated") as error:
            model.run_isolated()

        assert isinstance(error.value.__cause__, BrokenProcessPool)
        assert multiprocessing.active_children() == []

    @pytest.mark.unit
    def test_another_exception_of_the_child_crosses_the_boundary_as_itself(self, tmp_path):
        """Not every failure is a configuration problem; the type must survive."""
        config = write_synthetic_dataset(str(tmp_path))
        model = Model.from_config(config, validate_input=False)
        output = tmp_path / "out"
        shutil.rmtree(output)
        output.write_text("not a directory", encoding="utf8")

        with pytest.raises(NotADirectoryError, match="out"):
            model.run_isolated()

    @pytest.mark.unit
    def test_a_configuration_problem_crosses_the_boundary_as_itself(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        model = Model.from_config(config)
        break_kp(config)

        with pytest.raises(ConfigurationError) as error:
            model.run_isolated()

        assert any("not positive" in str(problem) for problem in error.value.problems)
        assert any(problem.blocking for problem in error.value.problems)

    @pytest.mark.unit
    def test_skipping_the_validation_crosses_the_boundary_too(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        break_kp(config)
        with pytest.raises(ConfigurationError):
            Model.from_config(config)

        result = Model.from_config(config, validate_input=False).run_isolated()

        assert not missing_files(result)

    @pytest.mark.unit
    def test_a_dead_subprocess_is_reported_against_run_isolated(self, tmp_path, mocker):
        model = Model.from_config(write_synthetic_dataset(str(tmp_path)), validate_input=False)
        executor = mocker.MagicMock()
        executor.submit.return_value.result.side_effect = BrokenProcessPool("killed")
        mocker.patch.object(api, "ProcessPoolExecutor", return_value=executor)

        with pytest.raises(RuntimeError, match="Model.run_isolated"):
            model.run_isolated()

        executor.shutdown.assert_called_once_with(wait=True)


class TestDocumentedLoaderFailures:
    """The loaders fail before validation too, with the documented types."""

    @pytest.mark.unit
    def test_a_configuration_file_that_is_not_there_is_reported_as_such(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            Model.from_file(tmp_path / "absent.json")

    @pytest.mark.unit
    def test_a_configuration_file_that_is_not_json_is_reported_as_such(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("{not json", encoding="utf8")

        with pytest.raises(json.JSONDecodeError):
            Model.from_file(path)

    @pytest.mark.unit
    def test_a_document_that_does_not_match_the_schema_is_reported_as_such(self, tmp_path):
        with pytest.raises(pydantic.ValidationError):
            Model.from_config({"bogus": 1}, base_dir=str(tmp_path))


class TestConfigurationErrorPickling:
    @pytest.mark.unit
    def test_a_round_trip_preserves_the_problems_and_the_message(self):
        # The payload is the exception built right above, not foreign data:
        # the round trip is what an isolated run does across its own pipe.
        error = ConfigurationError(
            [
                Problem(description="kp", reason="is not positive", blocking=True),
                Problem(description="ndvi", reason="has gaps"),
            ]
        )

        error.add_note("while rebuilding the configuration")

        restored = pickle.loads(pickle.dumps(error))

        assert type(restored) is ConfigurationError
        assert restored.problems == error.problems
        assert str(restored) == str(error)
        assert restored.__notes__ == ["while rebuilding the configuration"]


class TestResultSerialization:
    @pytest.mark.unit
    def test_a_result_survives_the_json_round_trip_the_process_boundary_uses(self, tmp_path):
        result = Model.from_config(write_synthetic_dataset(str(tmp_path))).run()

        restored = api._result_from_json(json.loads(json.dumps(api._result_to_json(result))))

        assert restored == result


_WITHOUT_NATIVE_DEPENDENCIES = textwrap.dedent(
    """
    import sys


    class BlockNativeDependencies:
        def find_spec(self, name, path=None, target=None):
            if name.partition(".")[0] in ("pcraster", "osgeo"):
                raise ModuleNotFoundError(f"blocked: {name}", name=name)
            return None


    sys.meta_path.insert(0, BlockNativeDependencies())

    from rubem import api

    assert "pcraster" not in sys.modules, "importing rubem.api must not import pcraster"
    assert "osgeo" not in sys.modules, "importing rubem.api must not import osgeo"

    calls = {
        "run": lambda: api.Model.__new__(api.Model).run(),
        "run_isolated": lambda: api.Model.__new__(api.Model).run_isolated(),
        "from_config": lambda: api.Model.from_config({}),
        "from_file": lambda: api.Model.from_file("config.json"),
    }
    for name, call in calls.items():
        try:
            call()
        except ImportError as error:
            print(name, error)
        else:
            raise AssertionError(f"{name} without the native dependencies must raise ImportError")
    """
)

_ISOLATION_OF_THE_CALLER = textwrap.dedent(
    """
    import json
    import sys

    from rubem.api import Model

    model = Model.from_file(sys.argv[1], validate_input=False)
    result = model.run_isolated()
    assert result.rasters, "the isolated run must report what it wrote"
    print(json.dumps({name: name in sys.modules for name in ("pcraster", "osgeo")}))
    """
)


class TestWithoutTheNativeDependencies:
    @pytest.mark.unit
    def test_the_module_imports_and_a_run_explains_what_is_missing(self):
        completed = subprocess.run(
            [sys.executable, "-c", _WITHOUT_NATIVE_DEPENDENCIES],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr
        for name in ("run", "run_isolated", "from_config", "from_file"):
            assert f"{name} RUBEM cannot run" in completed.stdout
        assert "pcraster, osgeo" in completed.stdout
        assert "conda-forge" in completed.stdout
        assert "environment.yml" in completed.stdout

    @pytest.mark.unit
    def test_the_command_line_still_exits_where_the_api_raises(self, monkeypatch):
        """The two front ends share the text, not the exception."""
        assert _deps.missing_runtime_deps() == [], "this environment has the native dependencies"
        # The API imported the function by name, so both bindings are replaced.
        monkeypatch.setattr(_deps, "missing_runtime_deps", lambda: ["pcraster"])
        monkeypatch.setattr(api, "missing_runtime_deps", lambda: ["pcraster"])

        with pytest.raises(SystemExit) as exit_:
            _deps.require_runtime_deps()
        with pytest.raises(ImportError) as imported:
            Model.from_config({})

        assert str(exit_.value) == _deps.runtime_deps_message(["pcraster"])
        assert str(imported.value) == str(exit_.value)


class TestTheCallerStaysFreeOfTheNativeState:
    @pytest.mark.unit
    def test_an_isolated_run_never_loads_pcraster_in_the_caller(self, tmp_path):
        """Only the child touches PCRaster: that is what run_isolated buys."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(write_synthetic_dataset(str(tmp_path))), encoding="utf8")

        completed = subprocess.run(
            [sys.executable, "-c", _ISOLATION_OF_THE_CALLER, str(config_file)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr
        loaded = json.loads(completed.stdout)
        assert loaded["pcraster"] is False
        # Loading a configuration imports GDAL in the caller even with the
        # validation off; only the PCRaster state stays in the child.
        assert loaded["osgeo"] is True


class TestPublicSurface:
    @pytest.mark.unit
    def test_the_exported_names_are_the_documented_ones(self):
        assert sorted(api.__all__) == ["ConfigurationError", "Model", "RunResult"]

    @pytest.mark.unit
    def test_the_signatures_are_the_documented_ones(self):
        assert str(signature(Model.__init__)) == (
            "(self, configuration: 'ModelConfiguration', *, validate_input: bool = True) -> None"
        )
        assert str(signature(Model.from_file)) == (
            "(path: str | os.PathLike[str] | bytes, *, validate_input: bool = True,"
            " base_dir: str | os.PathLike[str] | bytes | None = None) -> 'Model'"
        )
        assert str(signature(Model.from_config)) == (
            "(config: 'dict | ModelConfiguration', *, validate_input: bool = True,"
            " base_dir: str | os.PathLike[str] | bytes | None = None) -> 'Model'"
        )
        assert str(signature(Model.run)) == "(self) -> rubem.api.RunResult"
        assert str(signature(Model.run_isolated)) == "(self) -> rubem.api.RunResult"
        assert isinstance(Model.configuration, property)

    @pytest.mark.unit
    def test_the_result_fields_are_the_documented_ones(self):
        assert list(RunResult.__dataclass_fields__) == [
            "output_directory",
            "rasters",
            "time_series",
            "metadata",
            "first_step",
            "last_step",
            "elapsed_seconds",
        ]
        assert RunResult.__dataclass_params__.frozen
