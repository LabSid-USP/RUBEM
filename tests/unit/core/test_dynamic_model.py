import os
import shutil

import pytest

from rubem.configuration.model_configuration import ModelConfiguration
from rubem.core import DynamicFrameworkWrapper
from tests.helpers.compare import compare_rasters
from tests.helpers.synthetic import series_name, write_synthetic_dataset
from tests.unit.core.test_core import expected_outputs, run_model

STEP_FLUXES = (
    "current_interception",
    "current_total_real_evapotranspiration",
    "current_surface_runoff",
    "current_lateral_flow",
    "current_recharge",
    "current_cell_total_discharge",
    "accumulated_cell_total_discharge",
    "current_runoff",
)
INITIAL_ONLY = (
    "dem",
    "initial_soil_moist_content",
    "initial_baseflow",
    "initial_soil_sat_zone_storage",
    "initial_cell_total_flow",
)
CARRIED_STATE = (
    "ldd",
    "slope",
    "ndvi_min",
    "ndvi_max",
    "previous_ndvi",
    "previous_landuse",
    "previous_baseflow",
    "current_baseflow",
    "previous_soil_moist_content",
    "current_soil_moist_content",
    "previous_soil_sat_zone_storage",
    "current_soil_sat_zone_storage",
    "previous_cell_total_flow",
    "baseflow_threshold",
    "soil_hydraulic_conductivity_coef",
    "soil_bulk_density",
    "soil_rootzone_depth",
    "soil_moist_content_sat_point",
    "soil_moistute_content_wilting_point",
    "soil_moisture_content_field_capacity",
)


class TestDynamicModelBehavior:
    @pytest.mark.unit
    def test_ndvi_and_landuse_gaps_fall_back_to_the_previous_step(self, tmp_path):
        """Missing NDVI/LULC steps after the first reuse the previous raster.

        The gap run is compared with two controls: one whose second-step
        rasters duplicate the first step, which it must reproduce exactly, and
        the untouched dataset, whose distinct second-step NDVI it must not
        reproduce. Checking only that the outputs exist would pass for any
        fallback value.
        """
        gap_dir = tmp_path / "gap"
        duplicate_dir = tmp_path / "duplicate"
        distinct_dir = tmp_path / "distinct"

        gap_config = write_synthetic_dataset(str(gap_dir))
        os.remove(gap_dir / "maps" / "ndvi" / series_name("ndvi", 2))
        os.remove(gap_dir / "maps" / "lulc" / series_name("cob", 2))
        run_model(str(gap_dir), validate_input=False, config=gap_config)

        duplicate_config = write_synthetic_dataset(str(duplicate_dir))
        for directory, prefix in (("ndvi", "ndvi"), ("lulc", "cob")):
            maps = duplicate_dir / "maps" / directory
            shutil.copyfile(maps / series_name(prefix, 1), maps / series_name(prefix, 2))
        run_model(str(duplicate_dir), config=duplicate_config)

        run_model(str(distinct_dir))

        missing = [n for n in expected_outputs() if not (gap_dir / "out" / n).is_file()]
        assert not missing, f"missing outputs: {missing}"

        for variable in ("itp", "eta", "srn"):
            name = series_name(variable, 2)
            same = compare_rasters(gap_dir / "out" / name, duplicate_dir / "out" / name)
            assert same.equal, f"{name} differs from the duplicated-input control:\n{same.report()}"

        interception = series_name("itp", 2)
        assert not compare_rasters(
            gap_dir / "out" / interception, distinct_dir / "out" / interception
        ), "the fallback reproduced the second-step NDVI instead of the first"

    @pytest.mark.unit
    def test_disabling_tss_produces_no_time_series(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        config["GENERATE_FILE"]["tss"] = False

        run_model(str(tmp_path), config=config)

        output_dir = tmp_path / "out"
        assert not list(output_dir.glob("tss_*.csv"))
        assert not list(output_dir.glob("*.tss"))

    @pytest.mark.unit
    def test_disabling_a_variable_skips_its_rasters_and_time_series(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        config["GENERATE_FILE"]["itp"] = False

        run_model(str(tmp_path), config=config)

        output_dir = tmp_path / "out"
        assert not list(output_dir.glob("itp*"))
        assert not (output_dir / "tss_itp.csv").exists()
        assert (output_dir / "bfw00000.001").is_file()
        assert (output_dir / "tss_bfw.csv").is_file()

    @pytest.mark.unit
    def test_stale_tss_files_in_the_output_directory_are_left_alone(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        stale = tmp_path / "out" / "stale.tss"
        stale.write_text("1 42.0\n", encoding="utf8")

        run_model(str(tmp_path), config=config)

        assert stale.exists()
        assert not (tmp_path / "out" / "stale.csv").exists()

    @pytest.mark.unit
    def test_missing_first_ndvi_step_raises_a_clear_error(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        os.remove(tmp_path / "maps" / "ndvi" / "ndvi0000.001")

        with pytest.raises(RuntimeError, match="NDVI raster.*no previous raster"):
            run_model(str(tmp_path), validate_input=False, config=config)

    @pytest.mark.unit
    def test_missing_first_landuse_step_raises_a_clear_error(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        os.remove(tmp_path / "maps" / "lulc" / "cob00000.001")

        with pytest.raises(RuntimeError, match="land-use raster.*no previous raster"):
            run_model(str(tmp_path), validate_input=False, config=config)


class TestStateRelease:
    """Per-step fields are dropped once reported; the carried state survives."""

    @pytest.mark.unit
    def test_step_fluxes_and_initial_rasters_are_released_after_the_run(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        wrapper = DynamicFrameworkWrapper.load(ModelConfiguration(config, validate_input=False))
        model = wrapper.dynamic_model_concept

        wrapper.run()

        held = [name for name in STEP_FLUXES + INITIAL_ONLY if getattr(model, name) is not None]
        assert not held, f"still referenced after the run: {held}"
        dropped = [name for name in CARRIED_STATE if getattr(model, name) is None]
        assert not dropped, f"carried state released: {dropped}"

    @pytest.mark.unit
    def test_the_release_does_not_change_the_outputs(self, tmp_path):
        """The reported rasters are built before the release; the run equals the
        one of the wrapper helper step for step."""
        released = tmp_path / "released"
        reference = tmp_path / "reference"
        run_model(str(released))
        run_model(str(reference))

        for name in expected_outputs():
            if not name.endswith((".tif", ".001", ".002")):
                continue
            result = compare_rasters(released / "out" / name, reference / "out" / name)
            assert result.equal, f"{name}:\n{result.report()}"
