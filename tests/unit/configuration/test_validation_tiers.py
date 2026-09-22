"""End-to-end behaviour of the content validation through the loader."""

import json
import logging
import os
from pathlib import Path

import numpy as np
import pytest

from rubem.configuration._problems import ConfigurationError
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.model_configuration_file import ModelConfigurationFile
from rubem.configuration.model_configuration_file_v1 import ModelConfigurationFileV1
from tests.helpers.synthetic import series_name, write_lai_max_table, write_synthetic_dataset


def rewrite_map(path, values, scale):
    import pcraster as pcr

    pcr.report(pcr.numpy2pcr(scale, np.asarray(values, dtype=np.float32), -9999.0), path)


@pytest.fixture(name="config")
def config_fixture(tmp_path):
    config = write_synthetic_dataset(str(tmp_path))
    import pcraster as pcr

    pcr.setclone(config["RASTERS"]["clone"])
    return config


def blocking_reasons(error):
    return [str(p) for p in error.problems if p.blocking]


class TestLoaderBlocksOnContent:
    @pytest.mark.unit
    def test_the_synthetic_configuration_loads_without_blocking_problems(self, config):
        loaded = ModelConfiguration(config)

        assert not any(problem.blocking for problem in loaded.problems)

    @pytest.mark.unit
    def test_a_missing_precipitation_step_blocks(self, config):
        os.remove(os.path.join(config["DIRECTORIES"]["prec"], series_name("prec", 2)))

        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(config)

        assert any(
            "precipitation raster series is incomplete" in r for r in blocking_reasons(error.value)
        )

    @pytest.mark.unit
    def test_a_missing_first_ndvi_step_blocks_but_a_later_gap_warns(self, config):
        os.remove(os.path.join(config["DIRECTORIES"]["ndvi"], series_name("ndvi", 2)))

        loaded = ModelConfiguration(config)
        assert any(
            "ndvi raster series has gaps" in str(p) and not p.blocking for p in loaded.problems
        )

        os.rename(
            os.path.join(config["DIRECTORIES"]["ndvi"], series_name("ndvi", 1)),
            os.path.join(config["DIRECTORIES"]["ndvi"], series_name("ndvi", 2)),
        )
        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(config)
        assert any("lacks the first step" in r for r in blocking_reasons(error.value))

    @pytest.mark.unit
    def test_a_non_positive_kp_blocks(self, config):
        import pcraster as pcr

        rewrite_map(
            os.path.join(config["DIRECTORIES"]["kp"], series_name("kp", 1)),
            np.zeros((3, 3)),
            pcr.Scalar,
        )

        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(config)

        assert any("not positive" in r for r in blocking_reasons(error.value))

    @pytest.mark.unit
    def test_a_fractional_soil_class_blocks(self, tmp_path):
        """A GeoTIFF soil raster is read as int32 classes; 1.5 would round onto 2."""
        from rubem.preprocessing._io import read_raster, write_geotiff

        config = write_synthetic_dataset(str(tmp_path), raster_format="tif")
        soil = read_raster(config["RASTERS"]["soil"])
        write_geotiff(
            config["RASTERS"]["soil"],
            np.full(soil.array.shape, 1.5, dtype=np.float32),
            soil.geotransform,
            soil.projection,
            nodata=-9999.0,
        )

        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(config)

        assert any("Soil raster has non-integer values" in r for r in blocking_reasons(error.value))

    @pytest.mark.unit
    def test_a_fractional_ldd_code_blocks(self, tmp_path):
        from rubem.preprocessing._io import read_raster, write_geotiff

        config = write_synthetic_dataset(str(tmp_path), raster_format="tif")
        ldd = read_raster(config["RASTERS"]["ldd"])
        write_geotiff(
            config["RASTERS"]["ldd"],
            np.where(ldd.mask(), ldd.array + 0.5, -9999.0).astype(np.float32),
            ldd.geotransform,
            ldd.projection,
            nodata=-9999.0,
        )

        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(config)

        assert any("LDD raster has non-integer values" in r for r in blocking_reasons(error.value))

    @pytest.mark.unit
    def test_a_fractional_land_use_class_blocks(self, tmp_path):
        from rubem.preprocessing._io import read_raster, write_geotiff
        from tests.helpers.synthetic import geotiff_series_name

        config = write_synthetic_dataset(str(tmp_path), raster_format="tif")
        member = os.path.join(config["DIRECTORIES"]["landuse"], geotiff_series_name("cob", 1))
        landuse = read_raster(member)
        write_geotiff(
            member,
            np.full(landuse.array.shape, 2.5, dtype=np.float32),
            landuse.geotransform,
            landuse.projection,
            nodata=-9999.0,
        )

        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(config)

        assert any(
            "Land use raster has non-integer values" in r for r in blocking_reasons(error.value)
        )

    @pytest.mark.unit
    def test_ndvi_extremes_must_be_ordered(self, config):
        import pcraster as pcr

        rewrite_map(config["RASTERS"]["ndvi_max"], np.full((3, 3), 0.2), pcr.Scalar)

        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(config)

        assert any(
            "NDVI maximum is not above NDVI minimum" in r for r in blocking_reasons(error.value)
        )

    @pytest.mark.unit
    def test_sample_ids_must_be_contiguous(self, config):
        import pcraster as pcr

        samples = np.full((3, 3), -9999.0)
        samples[0, 0], samples[2, 2] = 1, 3
        rewrite_map(config["RASTERS"]["samples"], samples, pcr.Nominal)

        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(config)

        assert any("contiguous from 1" in r for r in blocking_reasons(error.value))

    @pytest.mark.unit
    def test_a_bad_lookup_table_blocks(self, config):
        with open(config["TABLES"]["t_sat"], "w", encoding="utf8") as f:
            f.write("1 0\n")

        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(config)

        assert any("non-positive" in r for r in blocking_reasons(error.value))

    @pytest.mark.unit
    def test_skipping_validation_skips_the_content_checks(self, config):
        with open(config["TABLES"]["t_sat"], "w", encoding="utf8") as f:
            f.write("1 0\n")
        os.remove(os.path.join(config["DIRECTORIES"]["prec"], series_name("prec", 2)))

        loaded = ModelConfiguration(config, validate_input=False)

        assert not any(problem.blocking for problem in loaded.problems)


def both_formats(config):
    """The legacy configuration and its format 1.0 document."""
    legacy = ModelConfigurationFile.model_validate(config)
    return (config, ModelConfigurationFileV1.from_legacy(legacy).to_dict())


class TestLeafAreaIndexMaxTable:
    """The ``lai_max`` table and its switch must agree, and the table read is checked."""

    @pytest.mark.unit
    @pytest.mark.parametrize("validate_input", [True, False])
    def test_the_switch_without_a_table_blocks_before_the_run(self, config, validate_input):
        config["CONSTANTS"]["lai_max_from_table"] = True

        for source in both_formats(config):
            with pytest.raises(ConfigurationError) as error:
                ModelConfiguration(source, validate_input=validate_input)

            assert any("lookup table is not set" in r for r in blocking_reasons(error.value))

    @pytest.mark.unit
    def test_a_table_without_the_switch_is_reported_as_ignored(self, config):
        config["TABLES"]["lai_max"] = write_lai_max_table(config)

        for source in both_formats(config):
            loaded = ModelConfiguration(source)

            ignored = [p for p in loaded.problems if "lookup table is ignored" in p.description]
            assert len(ignored) == 1 and not ignored[0].blocking
            assert Path(ignored[0].file) == Path(config["TABLES"]["lai_max"])
            assert loaded.constants.leaf_area_interception_max_from_table is False

    @pytest.mark.unit
    def test_the_content_of_an_ignored_table_is_not_checked(self, config):
        """A declared table must exist, but with the switch off its content plays no part."""
        table = write_lai_max_table(config, {3: 0.0})
        config["TABLES"]["lai_max"] = table

        loaded = ModelConfiguration(config)

        assert not any(problem.blocking for problem in loaded.problems)
        assert any("lookup table is ignored" in p.description for p in loaded.problems)
        os.remove(table)
        with pytest.raises(FileNotFoundError):
            ModelConfiguration(config)

    @pytest.mark.unit
    def test_the_table_and_the_switch_reach_the_model_settings_in_both_formats(self, config):
        table = write_lai_max_table(config)
        config["TABLES"]["lai_max"] = table
        config["CONSTANTS"]["lai_max_from_table"] = True
        legacy = ModelConfigurationFile.model_validate(config)
        document = ModelConfigurationFileV1.from_legacy(legacy).to_dict()

        for source in (config, document):
            loaded = ModelConfiguration(source)

            assert loaded.constants.leaf_area_interception_max_from_table is True
            assert Path(loaded.lookuptable_files.lai_max) == Path(table)
            assert not any(problem.blocking for problem in loaded.problems)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "text, description",
        [
            ("3 0\n4 4.0\n", "non-positive"),
            ("3 12.5\n4 4.0\n", "above 12"),
            ("3 9.0\n", "does not share its keys"),
            ("3 nope\n", "cannot be read"),
        ],
    )
    def test_a_bad_table_blocks(self, config, text, description):
        table = write_lai_max_table(config)
        with open(table, "w", encoding="utf8") as f:
            f.write(text)
        config["TABLES"]["lai_max"] = table
        config["CONSTANTS"]["lai_max_from_table"] = True

        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(config)

        assert any(description in r for r in blocking_reasons(error.value))


class TestAllowBlockingProblems:
    """``allow_blocking_problems`` keeps the checks and their report, but not the exception."""

    @pytest.mark.unit
    def test_blocking_problems_are_kept_and_logged_as_errors(self, config, caplog):
        with open(config["TABLES"]["t_sat"], "w", encoding="utf8") as f:
            f.write("1 0\n")
        os.remove(os.path.join(config["DIRECTORIES"]["prec"], series_name("prec", 2)))
        os.remove(os.path.join(config["DIRECTORIES"]["ndvi"], series_name("ndvi", 2)))

        with caplog.at_level(logging.WARNING, logger="rubem.configuration.model_configuration"):
            loaded = ModelConfiguration(config, allow_blocking_problems=True)

        blocking = [str(p) for p in loaded.problems if p.blocking]
        assert any("non-positive" in reason for reason in blocking)
        assert any("precipitation raster series is incomplete" in reason for reason in blocking)
        assert any(
            "ndvi raster series has gaps" in str(p) and not p.blocking for p in loaded.problems
        )

        errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("Tsat" in message and "non-positive" in message for message in errors)
        assert any("precipitation raster series is incomplete" in message for message in errors)
        assert errors[-1] == f"Simulation continues despite {len(blocking)} blocking problem(s)."
        assert any("ndvi raster series has gaps" in message for message in warnings)
        assert not any("ndvi raster series has gaps" in message for message in errors)

    @pytest.mark.unit
    def test_the_default_still_raises(self, config):
        with open(config["TABLES"]["t_sat"], "w", encoding="utf8") as f:
            f.write("1 0\n")

        with pytest.raises(ConfigurationError):
            ModelConfiguration(config, allow_blocking_problems=False)

    @pytest.mark.unit
    def test_nothing_is_reported_without_blocking_problems(self, config, caplog):
        with caplog.at_level(logging.WARNING, logger="rubem.configuration.model_configuration"):
            loaded = ModelConfiguration(config, allow_blocking_problems=True)

        assert not any(problem.blocking for problem in loaded.problems)
        assert not any(r.levelno == logging.ERROR for r in caplog.records)

    @pytest.mark.unit
    def test_load_passes_the_keyword_through(self, tmp_path, config):
        with open(config["TABLES"]["t_sat"], "w", encoding="utf8") as f:
            f.write("1 0\n")
        path = tmp_path / "config.json"
        path.write_text(json.dumps(config), encoding="utf8")

        with pytest.raises(ConfigurationError):
            ModelConfiguration.load(path)
        loaded = ModelConfiguration.load(path, allow_blocking_problems=True)

        assert any(problem.blocking for problem in loaded.problems)
