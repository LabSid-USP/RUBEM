import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from rubem.configuration.model_configuration_file import ModelConfigurationFile
from rubem.configuration.model_configuration_file_v1 import (
    DirectoryRasterSeries,
    ModelConfigurationFileV1,
    MonthlyRasterSeries,
    RasterFormat,
    TimeSeriesFormat,
)
from tests.helpers.synthetic import write_synthetic_dataset


@pytest.fixture(name="legacy")
def legacy_fixture(tmp_path):
    return ModelConfigurationFile.model_validate(write_synthetic_dataset(str(tmp_path)))


@pytest.fixture(name="document")
def document_fixture(legacy):
    return ModelConfigurationFileV1.from_legacy(legacy, {"title": "synthetic"}).to_dict()


def monthly_spec(prefix="ndvi"):
    return {
        "monthly": [{"month": m, "file_path": f"/maps/{prefix}0000.{m:03d}"} for m in range(1, 13)]
    }


class TestStrictness:
    @pytest.mark.unit
    def test_the_converted_document_validates_and_round_trips(self, document):
        model = ModelConfigurationFileV1.model_validate(document)

        assert model.version == "1.0"
        assert model.metadata.title == "synthetic"
        assert ModelConfigurationFileV1.model_validate(model.to_dict()) == model

    @pytest.mark.unit
    @pytest.mark.parametrize("version", ["0.9", "1", 1.0, None])
    def test_the_version_must_be_1_0(self, document, version):
        document["version"] = version

        with pytest.raises(ValidationError, match="version"):
            ModelConfigurationFileV1.model_validate(document)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "section, key",
        [
            (None, "GRID"),
            ("raster_info", "resolution"),
            ("rasters", "sample_locations"),
            ("metadata", "doi"),
        ],
    )
    def test_unknown_keys_are_rejected(self, document, section, key):
        target = document if section is None else document[section]
        target[key] = 1

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            ModelConfigurationFileV1.model_validate(document)

    @pytest.mark.unit
    def test_duplicated_keys_are_an_error_when_reading_a_file(self, tmp_path):
        file = tmp_path / "config.json"
        file.write_text('{"version": "1.0", "version": "1.0"}', encoding="utf8")

        with pytest.raises(ValueError, match="duplicated key"):
            ModelConfigurationFileV1.from_json(file)

    @pytest.mark.unit
    def test_from_json_reads_a_valid_file(self, tmp_path, document):
        file = tmp_path / "config.json"
        file.write_text(json.dumps(document), encoding="utf8")

        assert ModelConfigurationFileV1.from_json(file).to_dict() == document

    @pytest.mark.unit
    def test_the_period_is_ordered_and_iso(self, document):
        document["simulation_period"] = {"start": "2000-02-01", "finish": "2000-01-01"}
        with pytest.raises(ValidationError, match="before finish"):
            ModelConfigurationFileV1.model_validate(document)

        document["simulation_period"] = {"start": "01/01/2000", "finish": "2000-02-01"}
        with pytest.raises(ValidationError):
            ModelConfigurationFileV1.model_validate(document)

        document["simulation_period"] = {
            "start": "2000-01-01",
            "finish": "2000-02-01",
            "alignment": "2000-03-01",
        }
        with pytest.raises(ValidationError, match="alignment"):
            ModelConfigurationFileV1.model_validate(document)


class TestRasterSeriesSpecifications:
    @pytest.mark.unit
    def test_dated_entries_resolve_period_references(self, document):
        document["raster_series"]["landuse"] = [
            {
                "file_path": "/maps/cob.map",
                "from": {"$ref": "#/simulation_period/start"},
                "to": "2000-01-01",
            },
            {
                "file_path": "/maps/cobpr.map",
                "from": "2000-02-01",
                "to": {"$ref": "#/simulation_period/finish"},
            },
        ]

        model = ModelConfigurationFileV1.model_validate(document)

        first, second = model.raster_series.landuse
        assert model.resolve_date(first.from_) == date(2000, 1, 1)
        assert model.resolve_date(first.to) == date(2000, 1, 1)
        assert model.resolve_date(second.to) == model.simulation_period.finish
        assert model.to_dict()["raster_series"]["landuse"][0]["from"] == {
            "$ref": "#/simulation_period/start"
        }

    @pytest.mark.unit
    def test_an_unknown_reference_is_rejected(self, document):
        document["raster_series"]["landuse"] = [
            {"file_path": "/maps/cob.map", "from": {"$ref": "#/nope"}, "to": "2000-02-01"}
        ]

        with pytest.raises(ValidationError):
            ModelConfigurationFileV1.model_validate(document)

    @pytest.mark.unit
    def test_an_empty_dated_series_is_rejected(self, document):
        document["raster_series"]["landuse"] = []

        with pytest.raises(ValidationError, match="at least one entry"):
            ModelConfigurationFileV1.model_validate(document)

    @pytest.mark.unit
    def test_monthly_series_need_the_twelve_months_once(self, document):
        document["raster_series"]["ndvi"] = monthly_spec()
        model = ModelConfigurationFileV1.model_validate(document)
        assert isinstance(model.raster_series.ndvi, MonthlyRasterSeries)

        document["raster_series"]["ndvi"] = {"monthly": monthly_spec()["monthly"][:11]}
        with pytest.raises(ValidationError, match="each month 1-12 exactly once"):
            ModelConfigurationFileV1.model_validate(document)

        bad = monthly_spec()
        bad["monthly"][0]["month"] = 13
        document["raster_series"]["ndvi"] = bad
        with pytest.raises(ValidationError):
            ModelConfigurationFileV1.model_validate(document)

    @pytest.mark.unit
    def test_yearly_replacement_needs_both_keys(self, document):
        spec = monthly_spec()
        spec["yearly_from"] = 2010
        document["raster_series"]["ndvi"] = spec
        with pytest.raises(ValidationError, match="given together"):
            ModelConfigurationFileV1.model_validate(document)

        spec["yearly_file_path"] = "/maps/ndvipr.map"
        model = ModelConfigurationFileV1.model_validate(document)
        assert model.raster_series.ndvi.yearly_from == 2010

    @pytest.mark.unit
    def test_directory_series_keep_their_prefix(self, document):
        model = ModelConfigurationFileV1.model_validate(document)

        assert isinstance(model.raster_series.etp, DirectoryRasterSeries)
        assert model.raster_series.etp.files_prefix == "etp"


class TestSimulationOutput:
    @pytest.mark.unit
    def test_formats_are_sets(self, document):
        document["model_simulation_output"]["raster_series"]["formats"] = ["GeoTIFF", "GeoTIFF"]

        with pytest.raises(ValidationError, match="more than once"):
            ModelConfigurationFileV1.model_validate(document)

    @pytest.mark.unit
    def test_enabled_variables_need_a_format(self, document):
        document["model_simulation_output"]["raster_series"]["formats"] = []
        with pytest.raises(ValidationError, match="lists no format"):
            ModelConfigurationFileV1.model_validate(document)

        document["model_simulation_output"]["raster_series"] = {"formats": []}
        document["model_simulation_output"]["time_series_samples"]["formats"] = []
        with pytest.raises(ValidationError, match="time_series_samples enables variables"):
            ModelConfigurationFileV1.model_validate(document)

    @pytest.mark.unit
    def test_time_series_without_rasters_is_allowed(self, document):
        document["model_simulation_output"]["raster_series"] = {}

        model = ModelConfigurationFileV1.model_validate(document)

        assert model.model_simulation_output.raster_series.enabled() == ()
        assert model.model_simulation_output.time_series_samples.enabled() == (
            "itp",
            "bfw",
            "srn",
            "eta",
            "lfw",
            "rec",
            "smc",
            "rnf",
            "arn",
        )
        assert model.model_simulation_output.time_series_samples.formats == [TimeSeriesFormat.CSV]

    @pytest.mark.unit
    def test_unknown_formats_are_rejected(self, document):
        document["model_simulation_output"]["raster_series"]["formats"] = ["NetCDF"]

        with pytest.raises(ValidationError):
            ModelConfigurationFileV1.model_validate(document)


class TestConversions:
    @pytest.mark.unit
    def test_legacy_round_trips_through_1_0(self, legacy):
        v1 = ModelConfigurationFileV1.from_legacy(legacy)

        assert v1.to_legacy() == legacy
        assert v1.model_simulation_output.raster_series.formats == [
            RasterFormat.PCRASTER_MAP,
            RasterFormat.GEOTIFF,
        ]

    @pytest.mark.unit
    def test_legacy_without_time_series_converts(self, legacy):
        legacy = ModelConfigurationFile.model_validate(
            {
                **legacy.to_dict(),
                "GENERATE_FILE": {**legacy.to_dict()["GENERATE_FILE"], "tss": False},
            }
        )

        v1 = ModelConfigurationFileV1.from_legacy(legacy)

        assert v1.model_simulation_output.time_series_samples.enabled() == ()
        assert v1.model_simulation_output.time_series_samples.formats == []
        assert v1.to_legacy() == legacy

    @pytest.mark.unit
    def test_to_legacy_refuses_what_the_legacy_format_cannot_express(self, document):
        document["raster_series"]["ndvi"] = monthly_spec()
        with pytest.raises(ValueError, match="not a directory series"):
            ModelConfigurationFileV1.model_validate(document).to_legacy()

        document["raster_series"]["ndvi"] = {"dir_path": "/maps/ndvi", "files_prefix": "ndvi"}
        document["model_simulation_output"]["raster_series"] = {"itp": True, "formats": ["GeoTIFF"]}
        with pytest.raises(ValueError, match="without its raster series"):
            ModelConfigurationFileV1.model_validate(document).to_legacy()

        document["model_simulation_output"]["time_series_samples"] = {
            "itp": True,
            "formats": ["PCRasterTSS"],
        }
        with pytest.raises(ValueError, match="only writes CSV"):
            ModelConfigurationFileV1.model_validate(document).to_legacy()

    @pytest.mark.unit
    def test_relative_paths_are_anchored_for_every_series_kind(self, document, tmp_path):
        document["rasters"]["dem"] = "maps/dem.map"
        document["lookup_tables"]["manning"] = "txt/manning.txt"
        document["model_simulation_output"]["dir_path"] = "out"
        document["raster_series"]["etp"] = {"dir_path": "maps/etp", "files_prefix": "etp"}
        document["raster_series"]["ndvi"] = {
            **monthly_spec(),
            "yearly_from": 2005,
            "yearly_file_path": "maps/ndvipr.map",
        }
        document["raster_series"]["ndvi"]["monthly"][0]["file_path"] = "maps/ndvi0000.001"
        document["raster_series"]["landuse"] = [
            {
                "file_path": "maps/cob.map",
                "from": "2000-01-01",
                "to": {"$ref": "#/simulation_period/finish"},
            }
        ]

        anchored = ModelConfigurationFileV1.model_validate(document).resolve_paths(tmp_path)

        assert Path(anchored.rasters.dem) == tmp_path / "maps" / "dem.map"
        assert Path(anchored.lookup_tables.manning) == tmp_path / "txt" / "manning.txt"
        assert Path(anchored.model_simulation_output.dir_path) == tmp_path / "out"
        assert Path(anchored.raster_series.etp.dir_path) == tmp_path / "maps" / "etp"
        assert (
            Path(anchored.raster_series.ndvi.monthly[0].file_path)
            == tmp_path / "maps" / "ndvi0000.001"
        )
        assert (
            Path(anchored.raster_series.ndvi.yearly_file_path) == tmp_path / "maps" / "ndvipr.map"
        )
        assert Path(anchored.raster_series.landuse[0].file_path) == tmp_path / "maps" / "cob.map"
        assert anchored.raster_series.landuse[0].to.ref == "#/simulation_period/finish"
        assert anchored.resolve_paths(None) is anchored

    @pytest.mark.unit
    def test_metadata_dates_are_iso(self, document):
        document["metadata"] = {
            "title": "t",
            "creation_date": "2024-06-01",
            "last_update": "2024-06-02",
        }

        model = ModelConfigurationFileV1.model_validate(document)

        assert model.metadata.creation_date == date(2024, 6, 1)
        document["metadata"]["creation_date"] = "01/06/2024"
        with pytest.raises(ValidationError):
            ModelConfigurationFileV1.model_validate(document)
