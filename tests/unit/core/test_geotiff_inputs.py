"""GeoTIFF input rasters and series (#194)."""

import os
import shutil

import pytest

from rubem.configuration._problems import ConfigurationError
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.core import DynamicFrameworkWrapper
from tests.helpers.compare import compare_csv, compare_rasters
from tests.helpers.synthetic import geotiff_series_name, series_name, write_synthetic_dataset
from tests.unit.core.test_core import expected_outputs


def run(config):
    DynamicFrameworkWrapper.load(ModelConfiguration(config)).run()


def assert_same_outputs(first, second):
    for name in expected_outputs():
        if name.endswith(".csv"):
            result = compare_csv(first / "out" / name, second / "out" / name)
        else:
            result = compare_rasters(first / "out" / name, second / "out" / name)
        assert result.equal, f"{name}:\n{result.report()}"


class TestGeoTiffDataset:
    @pytest.mark.unit
    def test_a_geotiff_only_dataset_reproduces_the_map_run(self, tmp_path):
        """Every raster, the clone and the samples included, is a GeoTIFF."""
        map_dir, tif_dir = tmp_path / "map", tmp_path / "tif"
        run(write_synthetic_dataset(str(map_dir)))
        config = write_synthetic_dataset(str(tif_dir), raster_format="tif")
        assert config["RASTERS"]["clone"].endswith(".tif")

        run(config)

        assert_same_outputs(tif_dir, map_dir)

    @pytest.mark.unit
    def test_geotiff_series_with_map_rasters(self, tmp_path):
        map_dir, mixed_dir = tmp_path / "map", tmp_path / "mixed"
        run(write_synthetic_dataset(str(map_dir)))
        config = write_synthetic_dataset(str(mixed_dir))
        tif_config = write_synthetic_dataset(str(tmp_path / "source"), raster_format="tif")
        for key, prefix in (
            ("prec", "prec"),
            ("etp", "etp"),
            ("kp", "kp"),
            ("ndvi", "ndvi"),
            ("landuse", "cob"),
        ):
            for step in (1, 2):
                os.remove(os.path.join(config["DIRECTORIES"][key], series_name(prefix, step)))
                shutil.copyfile(
                    os.path.join(tif_config["DIRECTORIES"][key], geotiff_series_name(prefix, step)),
                    os.path.join(config["DIRECTORIES"][key], geotiff_series_name(prefix, step)),
                )

        run(config)

        assert_same_outputs(mixed_dir, map_dir)

    @pytest.mark.unit
    def test_the_tiff_suffix_is_accepted(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path), raster_format="tif")
        dem = config["RASTERS"]["dem"]
        renamed = dem[:-4] + ".tiff"
        os.rename(dem, renamed)
        config["RASTERS"]["dem"] = renamed

        loaded = ModelConfiguration(config)

        assert not any(problem.blocking for problem in loaded.problems)

    @pytest.mark.unit
    def test_a_series_mixing_formats_is_refused(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        tif_config = write_synthetic_dataset(str(tmp_path / "source"), raster_format="tif")
        shutil.copyfile(
            os.path.join(tif_config["DIRECTORIES"]["prec"], geotiff_series_name("prec", 1)),
            os.path.join(config["DIRECTORIES"]["prec"], geotiff_series_name("prec", 1)),
        )

        with pytest.raises(ValueError, match="mixes PCRaster maps and GeoTIFF files"):
            ModelConfiguration(config)

    @pytest.mark.unit
    def test_a_raster_with_another_geometry_blocks(self, tmp_path):
        from osgeo import gdal

        from tests.helpers.compare import ensure_gdal_drivers

        config = write_synthetic_dataset(str(tmp_path), raster_format="tif")
        ensure_gdal_drivers()
        gdal.UseExceptions()
        dataset = gdal.OpenEx(config["RASTERS"]["soil"], gdal.GA_Update)
        dataset.SetGeoTransform((1.0, 500.0, 0.0, 1500.0, 0.0, -500.0))
        dataset = None

        with pytest.raises(ConfigurationError, match="does not share the clone geometry"):
            ModelConfiguration(config)

    @pytest.mark.unit
    def test_a_raster_with_another_crs_blocks(self, tmp_path):
        from osgeo import gdal

        from tests.helpers.compare import ensure_gdal_drivers

        config = write_synthetic_dataset(str(tmp_path), raster_format="tif")
        ensure_gdal_drivers()
        gdal.UseExceptions()
        for path, crs in (
            (config["RASTERS"]["clone"], 'LOCAL_CS["Grid A",UNIT["metre",1]]'),
            (config["RASTERS"]["soil"], 'LOCAL_CS["Grid B",UNIT["foot",0.3048]]'),
        ):
            dataset = gdal.OpenEx(path, gdal.GA_Update)
            dataset.SetProjection(crs)
            dataset = None

        with pytest.raises(ConfigurationError, match="another coordinate reference system"):
            ModelConfiguration(config)

    @pytest.mark.unit
    def test_skipping_validation_still_checks_the_geometry_at_read_time(self, tmp_path):
        from osgeo import gdal

        from tests.helpers.compare import ensure_gdal_drivers

        config = write_synthetic_dataset(str(tmp_path), raster_format="tif")
        ensure_gdal_drivers()
        gdal.UseExceptions()
        dataset = gdal.OpenEx(config["RASTERS"]["ndvi_max"], gdal.GA_Update)
        dataset.SetGeoTransform((1.0, 500.0, 0.0, 1500.0, 0.0, -500.0))
        dataset = None
        loaded = ModelConfiguration(config, validate_input=False)

        with pytest.raises(ValueError, match="does not share the clone geometry"):
            DynamicFrameworkWrapper.load(loaded).run()

    @pytest.mark.unit
    def test_a_missing_geotiff_step_is_a_missing_step(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path), raster_format="tif")
        os.remove(os.path.join(config["DIRECTORIES"]["prec"], geotiff_series_name("prec", 2)))

        with pytest.raises(ConfigurationError, match="precipitation raster series is incomplete"):
            ModelConfiguration(config)
        assert not os.path.exists(
            os.path.join(config["DIRECTORIES"]["prec"], series_name("prec", 2))
        )
