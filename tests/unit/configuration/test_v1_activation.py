"""Configuration format 1.0 through the loader, the model and the command line."""

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from rubem.cli import main
from rubem.configuration.migrate import migrate_legacy_file
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.model_configuration_file import ModelConfigurationFile
from rubem.configuration.model_configuration_file_v1 import ModelConfigurationFileV1
from rubem.configuration.output_format import OutputFileFormat, TimeSeriesFileFormat
from rubem.core import DynamicFrameworkWrapper
from tests.helpers.compare import compare_csv, compare_rasters
from tests.helpers.synthetic import series_name, write_synthetic_dataset
from tests.unit.core.test_core import expected_outputs


def v1_document(base_dir, **metadata):
    legacy = ModelConfigurationFile.model_validate(write_synthetic_dataset(str(base_dir)))
    return ModelConfigurationFileV1.from_legacy(legacy, metadata or None).to_dict()


def write(path, document):
    Path(path).write_text(json.dumps(document, indent=1), encoding="utf8")
    return str(path)


def run(configuration):
    DynamicFrameworkWrapper.load(configuration).run()


def outputs(directory, suffix):
    return sorted(name for name in os.listdir(directory) if name.endswith(suffix))


class TestLoaderDetection:
    @pytest.mark.unit
    def test_a_document_with_version_is_read_as_format_1_0(self, tmp_path):
        document = v1_document(tmp_path, title="detected")

        loaded = ModelConfiguration(document)

        assert loaded.file_v1 is not None and loaded.file is None
        assert loaded.file_v1.metadata.title == "detected"
        assert loaded.simulation_period.total_steps == 2
        assert loaded.output_variables.tss
        assert loaded.output_variables.file_formats == (
            OutputFileFormat.PCRASTER | OutputFileFormat.GEOTIFF
        )
        assert loaded.output_variables.time_series_formats == TimeSeriesFileFormat.CSV
        assert not any(problem.blocking for problem in loaded.problems)

    @pytest.mark.unit
    def test_a_json_file_anchors_relative_paths(self, tmp_path):
        document = v1_document(tmp_path, title="anchored", authors=["A"])
        for section in ("rasters", "lookup_tables"):
            document[section] = {
                k: (os.path.relpath(v, tmp_path) if v else v) for k, v in document[section].items()
            }
        document["model_simulation_output"]["dir_path"] = "out"
        for spec in document["raster_series"].values():
            spec["dir_path"] = os.path.relpath(spec["dir_path"], tmp_path)
        path = write(tmp_path / "v1.json", document)

        loaded = ModelConfiguration.load(path)

        assert Path(loaded.raster_files.dem) == tmp_path / "maps" / "dem" / "dem.map"
        assert Path(loaded.output_directory.path) == tmp_path / "out"
        # Loading (and validating) the configuration must not write metadata.json:
        # it is written only once the run has finished successfully.
        assert not (tmp_path / "out" / "metadata.json").exists()

    @pytest.mark.unit
    def test_duplicated_keys_block_a_1_0_file(self, tmp_path):
        document = v1_document(tmp_path)
        text = json.dumps(document)
        text = text[:-1] + ', "version": "1.0"}'
        path = tmp_path / "dup.json"
        path.write_text(text, encoding="utf8")

        with pytest.raises(ValueError, match="Duplicated key"):
            ModelConfiguration.load(path)

    @pytest.mark.unit
    def test_strict_validation_reports_unknown_keys(self, tmp_path):
        document = v1_document(tmp_path)
        document["GRID"] = {"grid": 500}

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            ModelConfiguration(document)

    @pytest.mark.unit
    def test_non_directory_series_are_validated_through_the_resolvers(self, tmp_path):
        document = v1_document(tmp_path)
        ndvi_dir = document["raster_series"]["ndvi"]["dir_path"]
        document["raster_series"]["ndvi"] = {
            "monthly": [
                {"month": m, "file_path": os.path.join(ndvi_dir, series_name("ndvi", 1))}
                for m in range(1, 13)
            ]
        }

        loaded = ModelConfiguration(document)

        assert loaded.raster_series is None
        assert "MonthlySeriesResolver" in str(loaded)
        assert not any(problem.blocking for problem in loaded.problems)
        # A gap after the first step is reported, not blocking: the run reuses
        # the previous raster. A missing first step blocks.
        document["raster_series"]["ndvi"]["monthly"][1]["file_path"] = str(tmp_path / "absent.map")
        loaded = ModelConfiguration(document)
        assert any(
            "ndvi raster series has gaps" in str(p) and not p.blocking for p in loaded.problems
        )

        from rubem.configuration._problems import ConfigurationError

        document["raster_series"]["ndvi"]["monthly"][0]["file_path"] = str(tmp_path / "absent.map")
        with pytest.raises(ConfigurationError, match="lacks the first step"):
            ModelConfiguration(document)


class TestMetadataWriting:
    @pytest.mark.unit
    def test_metadata_is_written_after_a_successful_run(self, tmp_path):
        document = v1_document(tmp_path, title="written", authors=["A"])

        run(ModelConfiguration(document))

        metadata = json.loads((tmp_path / "out" / "metadata.json").read_text(encoding="utf8"))
        assert metadata == {
            "version": "1.0",
            "title": "written",
            "keywords": [],
            "authors": ["A"],
            "contact": [],
        }

    @pytest.mark.unit
    def test_a_failing_validation_does_not_touch_an_existing_metadata_json(self, tmp_path):
        from rubem.configuration._problems import ConfigurationError

        document = v1_document(tmp_path)
        # The first month's NDVI raster is missing: this fails deep inside
        # __build_from_v1 (validate_resolved_series) and is only turned into a
        # blocking ConfigurationError at the very end of __init__, after the
        # output directory has already been created -- exactly the point
        # where the old code wrote metadata.json unconditionally.
        document["raster_series"]["ndvi"] = {
            "monthly": [
                {"month": m, "file_path": str(tmp_path / "absent.map")} for m in range(1, 13)
            ]
        }
        out_dir = Path(document["model_simulation_output"]["dir_path"])
        out_dir.mkdir(parents=True, exist_ok=True)
        sentinel = out_dir / "metadata.json"
        sentinel.write_text('{"sentinel": true}', encoding="utf8")

        with pytest.raises(ConfigurationError, match="lacks the first step"):
            ModelConfiguration(document)

        assert sentinel.read_text(encoding="utf8") == '{"sentinel": true}'

    @pytest.mark.unit
    def test_a_failing_csv_export_does_not_write_metadata(self, tmp_path, mocker):
        document = v1_document(tmp_path, title="not written")
        mocker.patch("rubem.core.tss2csv", side_effect=RuntimeError("boom"))

        with pytest.raises(RuntimeError, match="boom"):
            run(ModelConfiguration(document))

        assert not (tmp_path / "out" / "metadata.json").exists()

    @pytest.mark.unit
    def test_metadata_is_written_after_the_csv_export(self, tmp_path, mocker):
        """The metadata write is the last step of a successful run."""
        from rubem import core

        document = v1_document(tmp_path, title="ordered")
        order = []
        real_tss2csv = core.tss2csv
        real_write_metadata = ModelConfiguration.write_metadata

        def record_export(*args, **kwargs):
            order.append("export")
            return real_tss2csv(*args, **kwargs)

        def record_metadata(self):
            order.append("metadata")
            return real_write_metadata(self)

        mocker.patch.object(core, "tss2csv", side_effect=record_export)
        mocker.patch.object(ModelConfiguration, "write_metadata", record_metadata)

        run(ModelConfiguration(document))

        assert order == ["export", "metadata"]

    @pytest.mark.unit
    def test_the_atomic_write_replaces_an_existing_file_only_on_success(self, tmp_path, mocker):
        first = v1_document(tmp_path, title="first")
        loaded = ModelConfiguration(first)
        loaded.write_metadata()
        metadata_path = Path(loaded.output_directory.path) / "metadata.json"
        original = metadata_path.read_text(encoding="utf8")
        assert "first" in original

        second = v1_document(tmp_path, title="second")
        loaded_again = ModelConfiguration(second)
        mocker.patch.object(Path, "replace", side_effect=OSError("disk full"))

        with pytest.raises(OSError, match="disk full"):
            loaded_again.write_metadata()

        assert metadata_path.read_text(encoding="utf8") == original
        assert not list(Path(loaded.output_directory.path).glob(".metadata.json.*.tmp"))


class TestOutputDiagnostics:
    """``any_enabled()`` only looks at raster series; a v1 configuration can

    select time series without their raster series, so the "no output"
    diagnostic must also look at time series, and must never be reported
    twice for the same root cause.
    """

    @pytest.mark.unit
    def test_a_time_series_only_configuration_is_not_reported_as_no_output(self, tmp_path):
        document = v1_document(tmp_path)
        document["model_simulation_output"]["raster_series"] = {}

        loaded = ModelConfiguration(document)

        assert loaded.output_variables.any_output_enabled()
        assert not any(
            p.description == "Simulation will not produce any output." for p in loaded.problems
        )

    @pytest.mark.unit
    def test_no_output_at_all_is_reported_exactly_once(self, tmp_path):
        document = v1_document(tmp_path)
        document["model_simulation_output"]["raster_series"] = {}
        document["model_simulation_output"]["time_series_samples"] = {}

        loaded = ModelConfiguration(document)

        no_output = [
            p for p in loaded.problems if p.description == "Simulation will not produce any output."
        ]
        assert len(no_output) == 1
        assert no_output[0].reason == "No Output Variables were selected."

    @pytest.mark.unit
    def test_sample_locations_and_tss_enabled_with_no_variables_reports_no_output_once(
        self, tmp_path
    ):
        legacy_config = write_synthetic_dataset(str(tmp_path))
        legacy_config["GENERATE_FILE"] = {
            **{key: False for key in legacy_config["GENERATE_FILE"]},
            "tss": True,
        }

        loaded = ModelConfiguration(legacy_config, validate_input=False)

        no_output = [
            p for p in loaded.problems if p.description == "Simulation will not produce any output."
        ]
        assert len(no_output) == 1
        assert no_output[0].reason == (
            "Sample Locations raster and Time Series generation were enabled but no "
            "Output Variables were selected."
        )


class TestResultsSpecification:
    """The format table of the results specification, row by row."""

    def _run_with(self, tmp_path, raster_formats, table_formats, time_series=True):
        document = v1_document(tmp_path)
        out = document["model_simulation_output"]
        out["raster_series"]["formats"] = raster_formats
        if not raster_formats:
            out["raster_series"] = {}
        out["time_series_samples"]["formats"] = table_formats
        if not time_series:
            out["time_series_samples"] = {}
        run(ModelConfiguration(document))
        return tmp_path / "out"

    @pytest.mark.unit
    def test_csv_only_converts_and_removes_the_tss_files(self, tmp_path):
        out = self._run_with(tmp_path, ["PCRasterMap"], ["CSV"])

        assert outputs(out, ".csv") and not outputs(out, ".tss")

    @pytest.mark.unit
    def test_tss_only_keeps_the_tss_files(self, tmp_path):
        out = self._run_with(tmp_path, ["PCRasterMap"], ["PCRasterTSS"])

        assert outputs(out, ".tss") and not outputs(out, ".csv")

    @pytest.mark.unit
    def test_both_formats_convert_and_keep(self, tmp_path):
        out = self._run_with(tmp_path, ["PCRasterMap"], ["CSV", "PCRasterTSS"])

        assert outputs(out, ".csv") and outputs(out, ".tss")

    @pytest.mark.unit
    def test_time_series_without_raster_series(self, tmp_path):
        out = self._run_with(tmp_path, [], ["CSV"])

        assert outputs(out, ".csv")
        assert not outputs(out, ".001") and not outputs(out, ".tif")

    @pytest.mark.unit
    def test_geotiff_only_raster_series_without_time_series(self, tmp_path):
        out = self._run_with(tmp_path, ["GeoTIFF"], [], time_series=False)

        assert outputs(out, ".tif")
        assert not outputs(out, ".001") and not outputs(out, ".csv") and not outputs(out, ".tss")


class TestEndToEnd:
    @pytest.mark.unit
    def test_a_migrated_configuration_reproduces_the_legacy_run(self, tmp_path, restore_logging):
        legacy_dir = tmp_path / "legacy"
        legacy_config = write_synthetic_dataset(str(legacy_dir))
        legacy_path = write(legacy_dir / "config.json", legacy_config)
        run(ModelConfiguration.load(legacy_path))

        migrated_path = migrate_legacy_file(legacy_path, tmp_path / "migrated" / "config-v1.json")
        migrated = json.loads(Path(migrated_path).read_text(encoding="utf8"))
        assert migrated["version"] == "1.0"
        assert not os.path.isabs(migrated["rasters"]["dem"])
        assert (Path(migrated_path).parent / migrated["rasters"]["dem"]).resolve() == Path(
            legacy_config["RASTERS"]["dem"]
        ).resolve()

        v1_out = tmp_path / "v1-out"
        migrated["model_simulation_output"]["dir_path"] = str(v1_out)
        write(migrated_path, migrated)
        main(["run", "-c", str(migrated_path)])

        for name in expected_outputs():
            if name.endswith(".csv"):
                result = compare_csv(v1_out / name, legacy_dir / "out" / name)
            else:
                result = compare_rasters(v1_out / name, legacy_dir / "out" / name)
            assert result.equal, f"{name}:\n{result.report()}"
        assert (v1_out / "metadata.json").is_file()


class TestMigrateCommand:
    @pytest.mark.unit
    def test_writes_next_to_the_source_and_refuses_to_overwrite(
        self, tmp_path, capsys, restore_logging
    ):
        legacy_path = write(tmp_path / "config.json", write_synthetic_dataset(str(tmp_path)))

        main(["config", "migrate", "-c", legacy_path])

        target = tmp_path / "config-v1.json"
        assert target.is_file()
        assert f"Wrote {target}" in capsys.readouterr().out
        with pytest.raises(SystemExit) as error:
            main(["config", "migrate", "-c", legacy_path])
        assert error.value.code == 1
        assert "already exists" in capsys.readouterr().err
        main(["config", "migrate", "-c", legacy_path, "--force"])

    @pytest.mark.unit
    def test_output_elsewhere_rebases_the_paths(self, tmp_path):
        legacy_path = write(tmp_path / "config.json", write_synthetic_dataset(str(tmp_path)))
        elsewhere = tmp_path / "somewhere" / "else"

        written = migrate_legacy_file(legacy_path, elsewhere / "v1.json")

        document = json.loads(written.read_text(encoding="utf8"))
        assert document["rasters"]["dem"].startswith("..")
        loaded = ModelConfiguration.load(written, validate_input=False)
        assert (
            Path(loaded.raster_files.dem).resolve()
            == (tmp_path / "maps" / "dem" / "dem.map").resolve()
        )

    @pytest.mark.unit
    def test_no_temporary_file_is_left_behind(self, tmp_path):
        legacy_path = write(tmp_path / "config.json", write_synthetic_dataset(str(tmp_path)))

        migrate_legacy_file(legacy_path)

        assert not [name for name in os.listdir(tmp_path) if name.endswith(".tmp")]

    @pytest.mark.unit
    def test_an_invalid_source_is_reported(self, tmp_path, capsys, restore_logging):
        broken = tmp_path / "broken.json"
        broken.write_text("{}", encoding="utf8")

        with pytest.raises(SystemExit) as error:
            main(["config", "migrate", "-c", str(broken)])

        assert error.value.code == 1
        assert "Invalid configuration" in capsys.readouterr().err


class TestSchemaCommand:
    @pytest.mark.unit
    def test_1_0_is_the_default_schema(self, capsys, restore_logging):
        main(["config", "schema"])

        schema = json.loads(capsys.readouterr().out)
        assert schema["title"] == "ModelConfigurationFileV1"
        assert "raster_series" in schema["properties"]

    @pytest.mark.unit
    def test_the_legacy_schema_is_still_available(self, capsys, restore_logging):
        main(["config", "schema", "--format", "legacy"])

        assert json.loads(capsys.readouterr().out)["title"] == "ModelConfigurationFile"
