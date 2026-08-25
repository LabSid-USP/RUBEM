"""Spatial aggregation of the time series (#117)."""

import csv
import os

import numpy as np
import pytest
from pydantic import ValidationError

from rubem.configuration._problems import ConfigurationError
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.model_configuration_file import ModelConfigurationFile
from rubem.configuration.model_configuration_file_v1 import ModelConfigurationFileV1
from rubem.core import DynamicFrameworkWrapper
from tests.helpers.compare import ensure_gdal_drivers
from tests.helpers.synthetic import COLS, MISSING, ROWS, write_synthetic_dataset


def v1(base_dir, aggregation="point", zones=None):
    legacy = ModelConfigurationFile.model_validate(write_synthetic_dataset(str(base_dir)))
    document = ModelConfigurationFileV1.from_legacy(legacy).to_dict()
    document["model_simulation_output"]["time_series_samples"]["aggregation"] = aggregation
    if zones is not None:
        document["rasters"]["zones"] = zones
    return document


def write_zones(config, values):
    import pcraster as pcr

    path = os.path.join(os.path.dirname(config["rasters"]["soil"]), "zones.map")
    pcr.setclone(config["rasters"]["clone"])
    pcr.report(
        pcr.numpy2pcr(
            pcr.Nominal, np.asarray(values, dtype=np.int32).reshape(ROWS, COLS), int(MISSING)
        ),
        path,
    )
    return path


def read_csv(path, delimiter=";"):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle, delimiter=delimiter))


def run(document):
    configuration = ModelConfiguration(document)
    DynamicFrameworkWrapper.load(configuration).run()
    return configuration


class TestSubcatchment:
    @pytest.mark.unit
    def test_values_are_the_area_averages_over_the_subcatchments(self, tmp_path):
        import pcraster as pcr

        document = v1(tmp_path, "subcatchment")

        configuration = run(document)

        out = tmp_path / "out"
        rows = read_csv(out / "tss_itp_subcatchment.csv")
        assert rows[0][1:] == ["1", "2"]
        ensure_gdal_drivers()
        pcr.setclone(configuration.raster_files.clone)
        ldd = pcr.readmap(configuration.raster_files.ldd)
        samples = pcr.nominal(pcr.readmap(configuration.raster_files.sample_locations))
        catchments = pcr.subcatchment(ldd, samples)
        itp = pcr.readmap(str(out / "itp00000.001"))
        expected = pcr.pcr2numpy(pcr.areaaverage(itp, catchments), np.nan)
        ids = pcr.pcr2numpy(catchments, -9999)
        first_row = [float(v) for v in rows[1][1:]]
        for column, sample_id in enumerate((1, 2)):
            cell = np.argwhere(ids == sample_id)[0]
            assert first_row[column] == pytest.approx(float(expected[tuple(cell)]), rel=1e-5)
        assert not (out / "tss_itp.csv").exists()

    @pytest.mark.unit
    def test_point_tables_keep_their_names(self, tmp_path):
        run(v1(tmp_path, "point"))

        assert (tmp_path / "out" / "tss_itp.csv").is_file()


class TestZones:
    @pytest.mark.unit
    def test_zone_ids_are_remapped_and_recorded(self, tmp_path):
        import pcraster as pcr

        document = v1(tmp_path)
        zones = write_zones(document, [20, 20, 20, 7, 7, 7, MISSING, MISSING, MISSING])
        document["rasters"]["zones"] = zones
        document["model_simulation_output"]["time_series_samples"]["aggregation"] = "zones"
        del document["rasters"]["samples"]

        configuration = run(document)

        out = tmp_path / "out"
        assert read_csv(out / "zones_mapping.csv", ",") == [
            ["column", "zone"],
            ["1", "7"],
            ["2", "20"],
        ]
        rows = read_csv(out / "tss_itp_zones.csv")
        ensure_gdal_drivers()
        pcr.setclone(configuration.raster_files.clone)
        itp = pcr.pcr2numpy(pcr.readmap(str(out / "itp00000.001")), np.nan)
        assert float(rows[1][1]) == pytest.approx(float(np.nanmean(itp[1])), rel=1e-5)
        assert float(rows[1][2]) == pytest.approx(float(np.nanmean(itp[0])), rel=1e-5)

    @pytest.mark.unit
    def test_an_empty_zones_raster_blocks(self, tmp_path):
        document = v1(tmp_path)
        document["rasters"]["zones"] = write_zones(document, [MISSING] * (ROWS * COLS))
        document["model_simulation_output"]["time_series_samples"]["aggregation"] = "zones"

        with pytest.raises(ConfigurationError, match="Zones raster has no zone"):
            ModelConfiguration(document)

    @pytest.mark.unit
    def test_a_zone_id_above_the_int32_range_blocks(self, tmp_path):
        """A GeoTIFF zones raster holding an id above the int32 range must be
        rejected before the run, since ``read_field`` casts ids to int32 and
        an out-of-range id would saturate and merge distinct zones."""
        from rubem.preprocessing._io import write_geotiff

        document = v1(tmp_path)
        values = np.full((ROWS, COLS), 1, dtype=np.float64)
        values[0, 0] = 2147483648
        transform = (0.0, 500.0, 0.0, 1500.0, 0.0, -500.0)
        zones = write_geotiff(tmp_path / "zones.tif", values, transform)
        document["rasters"]["zones"] = str(zones)
        document["model_simulation_output"]["time_series_samples"]["aggregation"] = "zones"
        del document["rasters"]["samples"]

        with pytest.raises(ConfigurationError, match="32-bit integer"):
            ModelConfiguration(document)


class TestSpecification:
    @pytest.mark.unit
    def test_zones_need_a_zones_raster_and_points_need_samples(self, tmp_path):
        document = v1(tmp_path, "zones")
        with pytest.raises(ValidationError, match="needs rasters.zones"):
            ModelConfigurationFileV1.model_validate(document)

        document = v1(tmp_path, "subcatchment")
        del document["rasters"]["samples"]
        with pytest.raises(ValidationError, match="needs rasters.samples"):
            ModelConfigurationFileV1.model_validate(document)

    @pytest.mark.unit
    def test_the_legacy_format_cannot_express_aggregations(self, tmp_path):
        document = v1(tmp_path, "subcatchment")

        with pytest.raises(ValueError, match="only samples the time series at points"):
            ModelConfigurationFileV1.model_validate(document).to_legacy()

    @pytest.mark.unit
    def test_the_schema_documents_the_aggregation(self):
        schema = ModelConfigurationFileV1.model_json_schema(by_alias=True)

        assert "aggregation" in schema["$defs"]["TimeSeriesOutput"]["properties"]
        assert set(schema["$defs"]["Aggregation"]["enum"]) == {"point", "subcatchment", "zones"}
