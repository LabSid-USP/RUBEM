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
    "soil_moisture_content_wilting_point",
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
    def test_ndvi_at_the_crop_coefficient_threshold_takes_the_minimum_branch(self, tmp_path):
        """A cell whose NDVI equals 1.1 * NDVI_min gets kc = kc_min (issue #320).

        The documented rule is kc = kc_min whenever NDVI <= 1.1 * NDVI_min, so
        the first-step evapotranspiration of a run whose NDVI sits exactly on
        the threshold must reproduce the run whose NDVI equals NDVI_min. Two
        strict comparisons around the threshold left that cell with kc = 0 and
        no vegetated-area evapotranspiration at all. A third run above the
        threshold, whose kc is interpolated, must differ, so that a constant
        output cannot pass.
        """
        import numpy as np
        import pcraster as pcr

        from tests.helpers.synthetic import COLS, MISSING, ROWS

        threshold_dir = tmp_path / "threshold"
        below_dir = tmp_path / "below"
        above_dir = tmp_path / "above"

        runs = [
            (directory, write_synthetic_dataset(str(directory)))
            for directory in (threshold_dir, below_dir, above_dir)
        ]
        # The threshold is the Float32 product PCRaster evaluates from the
        # ndvi_min raster the model reads: the Python literal 1.1 * 0.2 rounds
        # to a Float32 below it and would take the kc_min branch with any
        # comparison operator.
        ndvi_min = pcr.readmap(str(threshold_dir / "maps" / "ndvi" / "ndvi_min.map"))
        threshold = float(pcr.pcr2numpy(1.1 * ndvi_min, np.nan)[0, 0])
        below = float(pcr.pcr2numpy(ndvi_min, np.nan)[0, 0])
        # Write every step-1 NDVI raster while the synthetic clone is still set;
        # each model run replaces the PCRaster clone.
        for (directory, _), value in zip(runs, (threshold, below, 0.6), strict=True):
            ndvi = pcr.numpy2pcr(
                pcr.Scalar, np.full((ROWS, COLS), value, dtype=np.float32), MISSING
            )
            pcr.report(ndvi, str(directory / "maps" / "ndvi" / series_name("ndvi", 1)))
        for directory, config in runs:
            run_model(str(directory), config=config)

        name = series_name("eta", 1)
        same = compare_rasters(threshold_dir / "out" / name, below_dir / "out" / name)
        assert same.equal, (
            f"{name} at NDVI = 1.1 * NDVI_min differs from the NDVI = NDVI_min control:\n"
            f"{same.report()}"
        )
        assert not compare_rasters(threshold_dir / "out" / name, above_dir / "out" / name).equal, (
            "the threshold run reproduced the interpolated kc of the above-threshold control"
        )

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
        """The reported rasters are built before the release; a run that keeps
        every released field alive (the release methods patched to no-ops)
        must reproduce the normal run step for step."""
        from unittest.mock import patch

        from rubem._dynamic_model import RainfallRunoffBalanceEnhancedModel

        released = tmp_path / "released"
        reference = tmp_path / "reference"
        run_model(str(released))
        with (
            patch.object(
                RainfallRunoffBalanceEnhancedModel,
                "_RainfallRunoffBalanceEnhancedModel__release_initial_state",
                lambda self: None,
            ),
            patch.object(
                RainfallRunoffBalanceEnhancedModel,
                "_RainfallRunoffBalanceEnhancedModel__release_step_state",
                lambda self: None,
            ),
        ):
            run_model(str(reference))

        for name in expected_outputs():
            if not name.endswith((".tif", ".001", ".002")):
                continue
            result = compare_rasters(released / "out" / name, reference / "out" / name)
            assert result.equal, f"{name}:\n{result.report()}"


class TestSampleMapRelease:
    """``sample_map`` is only read again by the time series writer when the
    writer cannot use the sample file path directly."""

    @pytest.mark.unit
    def test_the_sample_map_is_released_for_a_point_map_sample_file(self, tmp_path):
        """Point aggregation with a ``.map`` sample file hands the writer the
        file path directly; the full-grid field is not needed again."""
        config = write_synthetic_dataset(str(tmp_path))
        wrapper = DynamicFrameworkWrapper.load(ModelConfiguration(config, validate_input=False))
        model = wrapper.dynamic_model_concept

        wrapper.run()

        assert model.sample_vals is not None
        assert model.sample_map is None

    @pytest.mark.unit
    def test_the_sample_map_survives_subcatchment_aggregation(self, tmp_path):
        """Subcatchment aggregation builds the id map from the LDD; the writer
        reads it from the field, which must stay alive for the run."""
        config = write_synthetic_dataset(str(tmp_path))
        configuration = ModelConfiguration(config, validate_input=False)
        configuration.output_variables = configuration.output_variables.model_copy(
            update={"aggregation": "subcatchment"}
        )
        wrapper = DynamicFrameworkWrapper.load(configuration)
        model = wrapper.dynamic_model_concept

        wrapper.run()

        assert model.sample_map is not None


class TestRasterFileFormatAtRuntime:
    @pytest.mark.unit
    def test_disabling_the_pcraster_maps_writes_only_geotiffs(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        config["RASTER_FILE_FORMAT"] = {"map_raster_series": False, "tiff_raster_series": True}

        run_model(str(tmp_path), config=config)

        outputs = sorted(path.name for path in (tmp_path / "out").iterdir())
        assert not [name for name in outputs if name.endswith((".001", ".002"))], outputs
        assert [name for name in outputs if name.endswith(".tif")]
        assert [name for name in outputs if name.endswith(".csv")]

    @pytest.mark.unit
    def test_the_configured_no_data_value_reaches_the_geotiffs(self, tmp_path):
        """The GeoTIFF band declares the configured value and the cells the
        model leaves missing (the clone here has no missing cell, so a masked
        DEM cell is used to create one) carry it."""
        import numpy as np
        import pcraster as pcr

        from tests.helpers.compare import ensure_gdal_drivers
        from tests.helpers.synthetic import COLS, MISSING, ROWS

        config = write_synthetic_dataset(str(tmp_path))
        config["RASTER_FILE_FORMAT"] = {
            "map_raster_series": True,
            "tiff_raster_series": True,
            "no_data_value": -1,
        }
        ndvi_max_path = config["RASTERS"]["ndvi_max"]
        pcr.setclone(config["RASTERS"]["clone"])
        ndvi_max = pcr.pcr2numpy(pcr.readmap(ndvi_max_path), MISSING)
        ndvi_max[ROWS - 1, COLS - 1] = MISSING
        pcr.report(pcr.numpy2pcr(pcr.Scalar, ndvi_max, MISSING), ndvi_max_path)

        run_model(str(tmp_path), validate_input=False, config=config)

        ensure_gdal_drivers()
        from osgeo import gdal

        dataset = gdal.OpenEx(str(tmp_path / "out" / "itp0000001.tif"), gdal.GA_ReadOnly)
        try:
            band = dataset.GetRasterBand(1)
            assert band.GetNoDataValue() == -1
            array = band.ReadAsArray()
        finally:
            dataset = None
        assert array[ROWS - 1, COLS - 1] == -1
        assert np.count_nonzero(array == -1) == 1


class TestGeoreference:
    @pytest.mark.unit
    def test_the_georeference_crs_reaches_the_geotiff_outputs(self, tmp_path):
        from rubem.configuration.output_raster_base import read_raster_geometry
        from tests.helpers.compare import ensure_gdal_drivers

        config = write_synthetic_dataset(str(tmp_path))
        cols, rows, transformation, _ = read_raster_geometry(config["RASTERS"]["dem"])
        georeference = tmp_path / "maps" / "georeference.tif"
        ensure_gdal_drivers()
        from osgeo import gdal

        gdal.UseExceptions()
        dataset = gdal.GetDriverByName("GTiff").Create(
            str(georeference), cols, rows, 1, gdal.GDT_Float32
        )
        dataset.SetGeoTransform(transformation)
        dataset.SetProjection('LOCAL_CS["Engineering grid",UNIT["metre",1]]')
        dataset = None
        config["RASTERS"]["georeference"] = str(georeference)

        run_model(str(tmp_path), config=config)

        ensure_gdal_drivers()
        dataset = gdal.OpenEx(str(tmp_path / "out" / "itp0000001.tif"), gdal.GA_ReadOnly)
        try:
            assert "Engineering grid" in dataset.GetProjection()
            assert dataset.GetGeoTransform() == pytest.approx(transformation)
        finally:
            dataset = None

    @pytest.mark.unit
    def test_outputs_without_a_georeference_carry_no_crs(self, tmp_path):
        from tests.helpers.compare import ensure_gdal_drivers

        run_model(str(tmp_path))

        ensure_gdal_drivers()
        from osgeo import gdal

        dataset = gdal.OpenEx(str(tmp_path / "out" / "itp0000001.tif"), gdal.GA_ReadOnly)
        try:
            assert dataset.GetProjection() == ""
        finally:
            dataset = None


class TestDeprecatedAttributeNames:
    @pytest.mark.unit
    def test_the_old_wilting_point_spelling_warns_and_aliases_the_new_one(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        wrapper = DynamicFrameworkWrapper.load(ModelConfiguration(config, validate_input=False))
        model = wrapper.dynamic_model_concept

        with pytest.warns(DeprecationWarning, match="soil_moistute_content_wilting_point"):
            model.soil_moistute_content_wilting_point = "sentinel"
        assert model.soil_moisture_content_wilting_point == "sentinel"

        model.soil_moisture_content_wilting_point = "updated"
        with pytest.warns(DeprecationWarning, match="soil_moistute_content_wilting_point"):
            assert model.soil_moistute_content_wilting_point == "updated"


class TestSeriesResolvers:
    @pytest.mark.unit
    def test_the_run_reads_the_rasters_the_resolvers_answer(self, tmp_path):
        """A monthly NDVI set pointing every month at the step-1 raster must
        reproduce the run whose step-2 NDVI is a copy of step 1."""
        from datetime import date

        from rubem.configuration.raster_series_resolver import MonthlySeriesResolver

        resolved_dir = tmp_path / "resolved"
        duplicate_dir = tmp_path / "duplicate"
        distinct_dir = tmp_path / "distinct"

        resolved_config = write_synthetic_dataset(str(resolved_dir))
        configuration = ModelConfiguration(resolved_config, validate_input=False)
        first_ndvi = os.path.join(resolved_config["DIRECTORIES"]["ndvi"], series_name("ndvi", 1))
        configuration.series_resolvers["ndvi"] = MonthlySeriesResolver(
            "ndvi", {month: first_ndvi for month in range(1, 13)}, date(2000, 1, 1)
        )
        DynamicFrameworkWrapper.load(configuration).run()

        duplicate_config = write_synthetic_dataset(str(duplicate_dir))
        maps = duplicate_dir / "maps" / "ndvi"
        shutil.copyfile(maps / series_name("ndvi", 1), maps / series_name("ndvi", 2))
        run_model(str(duplicate_dir), config=duplicate_config)

        run_model(str(distinct_dir))

        for name in expected_outputs():
            if not name.endswith(".002"):
                continue
            same = compare_rasters(resolved_dir / "out" / name, duplicate_dir / "out" / name)
            assert same.equal, f"{name}:\n{same.report()}"
        differs = compare_rasters(
            resolved_dir / "out" / "itp00000.002", distinct_dir / "out" / "itp00000.002"
        )
        assert not differs.equal

    @pytest.mark.unit
    def test_a_missing_strict_step_fails_with_the_series_and_step(self, tmp_path):
        from rubem.configuration.raster_series_resolver import DirectorySeriesResolver

        config = write_synthetic_dataset(str(tmp_path))
        configuration = ModelConfiguration(config, validate_input=False)
        configuration.series_resolvers["kp"] = DirectorySeriesResolver(
            "kp", str(tmp_path / "nowhere"), "kp"
        )

        with pytest.raises(RuntimeError, match="kp series has no raster for step 1"):
            DynamicFrameworkWrapper.load(configuration).run()
