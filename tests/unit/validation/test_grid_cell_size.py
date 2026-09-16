"""The declared grid cell size against the geometry of the clone."""

import json
import logging
import os

import pytest

from rubem.configuration._problems import ConfigurationError
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.model_configuration_file import ModelConfigurationFile
from rubem.configuration.model_configuration_file_v1 import ModelConfigurationFileV1
from rubem.configuration.output_raster_base import read_raster_geometry
from rubem.validation.grid_cell_size import check_grid_cell_size
from tests.helpers.compare import ensure_gdal_drivers
from tests.helpers.config import BASE_DATA_DIR
from tests.helpers.synthetic import CELL_SIZE, write_synthetic_dataset

# The PROJ database is not required to read these definitions, so the fixtures
# do not depend on an EPSG lookup being available.
GEOGCS_WKT = (
    'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
    'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]'
)
PROJCS_WKT = (
    'PROJCS["Synthetic transverse Mercator",'
    'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
    'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],'
    'PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],'
    'PARAMETER["central_meridian",-45],PARAMETER["scale_factor",0.9996],'
    'PARAMETER["false_easting",500000],PARAMETER["false_northing",10000000],'
    'UNIT["metre",1]]'
)
FOOT_TO_METRE = 0.304800609601219
FOOT_PROJCS_WKT = PROJCS_WKT.replace(
    'UNIT["metre",1]', f'UNIT["US survey foot",{FOOT_TO_METRE}]'
).replace("Synthetic transverse Mercator", "Synthetic transverse Mercator (feet)")
LOCAL_CS_WKT = 'LOCAL_CS["Engineering grid",UNIT["metre",1]]'

FIXTURE_DEM_TIF = os.path.join(BASE_DATA_DIR, "maps", "dem", "dem.tif")


def set_projection(path, projection):
    """Write ``projection`` onto an existing GeoTIFF, leaving its band untouched.

    The WKT is written as given; matching it against the PROJ database is only
    needed to label the GeoTIFF keys, so the errors that an incomplete PROJ
    installation emits while doing so are silenced here.
    """
    ensure_gdal_drivers()
    from osgeo import gdal

    gdal.UseExceptions()
    with gdal.ExceptionMgr(useExceptions=False), gdal.quiet_errors():
        dataset = gdal.OpenEx(str(path), gdal.GA_Update)
        try:
            assert dataset.SetProjection(projection) == gdal.CE_None
            dataset.FlushCache()
        finally:
            dataset = None
        gdal.ErrorReset()


def blocking_reasons(error):
    return [str(problem) for problem in error.problems if problem.blocking]


class TestCheckGridCellSize:
    @pytest.mark.unit
    def test_a_projected_raster_in_metres_that_matches_has_no_problem(self):
        problem = check_grid_cell_size(500.0, 500.0, -500.0, PROJCS_WKT, "clone.tif")

        assert problem is None

    @pytest.mark.unit
    def test_a_projected_raster_in_metres_that_differs_blocks(self):
        problem = check_grid_cell_size(500.0, 460.0, -460.0, PROJCS_WKT, "clone.tif")

        assert problem is not None
        assert problem.blocking
        assert problem.description == "Grid cell size does not match the raster."
        assert "500.0" in problem.reason and "460.0" in problem.reason
        assert problem.file == "clone.tif"

    @pytest.mark.unit
    @pytest.mark.parametrize("pixel", [500.0000001, 500.0002])
    def test_a_difference_within_the_tolerance_is_accepted(self, pixel):
        assert check_grid_cell_size(500.0, pixel, -pixel, PROJCS_WKT, "clone.tif") is None

    @pytest.mark.unit
    @pytest.mark.parametrize("pixel", [500.001, 500.002])
    def test_a_difference_above_the_tolerance_blocks(self, pixel):
        assert check_grid_cell_size(500.0, pixel, -pixel, PROJCS_WKT, "clone.tif") is not None

    @pytest.mark.unit
    def test_a_single_axis_that_differs_blocks(self):
        problem = check_grid_cell_size(500.0, 500.0, -400.0, PROJCS_WKT, "clone.tif")

        assert problem is not None and problem.blocking

    @pytest.mark.unit
    def test_a_projected_raster_in_feet_is_converted_to_metres(self):
        pixel = 500.0 / FOOT_TO_METRE

        assert check_grid_cell_size(500.0, pixel, -pixel, FOOT_PROJCS_WKT, "clone.tif") is None

    @pytest.mark.unit
    def test_a_projected_raster_in_feet_reports_both_units(self):
        problem = check_grid_cell_size(500.0, 500.0, -500.0, FOOT_PROJCS_WKT, "clone.tif")

        assert problem is not None and problem.blocking
        assert "US survey foot" in problem.reason
        assert "152.4" in problem.reason

    @pytest.mark.unit
    def test_a_geographic_raster_is_not_compared(self, caplog):
        with caplog.at_level(logging.INFO, logger="rubem.validation.grid_cell_size"):
            problem = check_grid_cell_size(
                500.0, 0.00462962962962963, -0.00462962962962963, GEOGCS_WKT, "clone.tif"
            )

        assert problem is None
        assert "500.0" in caplog.text
        assert "0.00462962962962963" in caplog.text
        assert "degree" in caplog.text

    @pytest.mark.unit
    def test_the_fixture_dataset_in_degrees_is_not_compared(self, caplog):
        _, _, transformation, projection = read_raster_geometry(FIXTURE_DEM_TIF)

        with caplog.at_level(logging.INFO, logger="rubem.validation.grid_cell_size"):
            problem = check_grid_cell_size(
                500.0, transformation[1], transformation[5], projection, FIXTURE_DEM_TIF
            )

        assert problem is None
        assert "500.0" in caplog.text

    @pytest.mark.unit
    @pytest.mark.parametrize("projection", [None, ""])
    def test_a_raster_without_a_coordinate_reference_system_is_not_compared(
        self, projection, caplog
    ):
        with caplog.at_level(logging.INFO, logger="rubem.validation.grid_cell_size"):
            problem = check_grid_cell_size(500.0, 400.0, -400.0, projection, "clone.map")

        assert problem is None
        assert "no coordinate reference system is available" in caplog.text
        assert "500.0" in caplog.text
        assert "400.0 x 400.0" in caplog.text

    @pytest.mark.unit
    def test_an_engineering_system_is_not_compared(self, caplog):
        with caplog.at_level(logging.INFO, logger="rubem.validation.grid_cell_size"):
            problem = check_grid_cell_size(500.0, 400.0, -400.0, LOCAL_CS_WKT, "clone.tif")

        assert problem is None
        assert "not projected" in caplog.text


@pytest.fixture(name="projected_config")
def projected_config_fixture(tmp_path):
    """A synthetic GeoTIFF dataset whose clone carries a projected CRS in metres."""
    config = write_synthetic_dataset(str(tmp_path), raster_format="tif")
    set_projection(config["RASTERS"]["clone"], PROJCS_WKT)
    return config


class TestLoaderChecksTheGridCellSize:
    @pytest.mark.unit
    def test_a_matching_grid_loads_without_blocking_problems(self, projected_config):
        loaded = ModelConfiguration(projected_config)

        assert loaded.grid.size == CELL_SIZE
        assert not any(problem.blocking for problem in loaded.problems)

    @pytest.mark.unit
    def test_a_mismatching_grid_blocks(self, projected_config):
        projected_config["GRID"]["grid"] = 400.0

        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(projected_config)

        reasons = blocking_reasons(error.value)
        assert any("Grid cell size does not match the raster." in reason for reason in reasons)
        assert any("400.0" in reason and "500.0" in reason for reason in reasons)

    @pytest.mark.unit
    def test_a_mismatching_grid_loads_without_input_validation(self, projected_config):
        projected_config["GRID"]["grid"] = 400.0

        loaded = ModelConfiguration(projected_config, validate_input=False)

        assert not any(problem.blocking for problem in loaded.problems)

    @pytest.mark.unit
    def test_a_dataset_without_a_coordinate_reference_system_is_not_compared(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path), raster_format="tif")
        config["GRID"]["grid"] = 400.0

        loaded = ModelConfiguration(config)

        assert not any(problem.blocking for problem in loaded.problems)

    @pytest.mark.unit
    def test_the_system_of_the_dem_is_used_when_the_clone_carries_none(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path), raster_format="tif")
        set_projection(config["RASTERS"]["dem"], PROJCS_WKT)
        config["GRID"]["grid"] = 400.0

        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(config)

        assert any(
            "Grid cell size does not match the raster." in reason
            for reason in blocking_reasons(error.value)
        )

    @pytest.mark.unit
    def test_a_mismatching_grid_size_blocks_in_format_1_0(self, projected_config, tmp_path):
        legacy = ModelConfigurationFile.model_validate(projected_config)
        document = ModelConfigurationFileV1.from_legacy(legacy).to_dict()
        document["raster_info"]["grid_size"] = 400.0
        path = tmp_path / "config-v1.json"
        path.write_text(json.dumps(document, indent=1), encoding="utf8")

        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(path)

        assert any(
            "Grid cell size does not match the raster." in reason
            for reason in blocking_reasons(error.value)
        )
