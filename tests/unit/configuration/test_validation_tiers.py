"""End-to-end behaviour of the content validation through the loader."""

import os

import numpy as np
import pytest

from rubem.configuration._problems import ConfigurationError
from rubem.configuration.model_configuration import ModelConfiguration
from tests.helpers.synthetic import series_name, write_synthetic_dataset


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
