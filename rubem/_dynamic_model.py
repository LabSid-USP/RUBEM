import logging
import os
import warnings
from calendar import monthrange
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pcraster as pcr
import pcraster.framework as pcrfw
from dateutil.relativedelta import relativedelta
from pcraster._pcraster import Field

from .configuration.model_configuration import ModelConfiguration
from .configuration.output_format import OutputFileFormat
from .configuration.raster_series_resolver import MissingStep
from .file._file_generators import report
from .file._readers import FieldScale, is_geotiff, read_field, set_clone
from .file._timeoutput import TimeoutputTimeseriesAdapter
from .hydrological_processes import Evapotranspiration, Interception, Soil, SurfaceRunoff

MISSING_VALUE_DEFAULT = -9999


class RainfallRunoffBalanceEnhancedModel(pcrfw.DynamicModel):
    """Rainfall-Runoff Balance Enhanced Model.

    This class contains the implementation of the Rainfall-Runoff Balance Enhanced Model (RUBEM).
    RUBEM is a hydrological model for transforming precipitation into surface and subsurface runoff.
    The model is based on equations that represent the physical processes of the hydrological cycle,
    with spatial distribution defined by pixel, in distinct vegetated and non-vegetated covers, and
    has the flexibility to study a wide range of applications, including impacts of changes in
    climate and land use, has flexible spatial resolution, the inputs are raster-type matrix
    files obtained from remote sensing data and operates with a reduced number of parameters.
    """

    def __init__(self, config: ModelConfiguration):
        pcrfw.DynamicModel.__init__(self)
        self.logger = logging.getLogger(__name__)
        # User-facing progress: silent unless a front end configures it, which
        # the CLI does in ``rubem.cli.setup_logging``.
        self.progress = logging.getLogger("rubem.progress")

        self.config = config

        self.logger.info("Reading clone file...")
        set_clone(self.config.raster_files.clone)

        self.sample_time_series_dict = {}
        self.sample_vals = None
        self.sample_map = None
        self.dem = None
        self.ldd = None
        self.slope = None
        self.ndvi_max = None
        self.ndvi_min = None
        self.previous_ndvi = None
        self.previous_landuse = None
        self.min_reflectances_simple_ratio = None
        self.max_reflectances_simple_ratio = None
        self.initial_baseflow = None
        self.baseflow_threshold = None
        self.previous_baseflow = None
        self.current_baseflow = None
        self.initial_soil_sat_zone_storage = None
        self.previous_soil_sat_zone_storage = None
        self.current_soil_sat_zone_storage = None
        self.previous_soil_moist_content = None
        self.current_soil_moist_content = None
        self.initial_cell_total_flow = None
        self.previous_cell_total_flow = None
        self.soil_hydraulic_conductivity_coef = None
        self.soil_bulk_density = None
        self.soil_rootzone_depth = None
        self.soil_moist_content_sat_point = None
        self.initial_soil_moist_content = None
        self.soil_moisture_content_wilting_point = None
        self.soil_moisture_content_field_capacity = None
        # Fluxes of the current step: computed, reported and then released.
        self.current_interception = None
        self.current_total_real_evapotranspiration = None
        self.current_surface_runoff = None
        self.current_lateral_flow = None
        self.current_recharge = None
        self.current_cell_total_discharge = None
        self.accumulated_cell_total_discharge = None
        self.current_runoff = None

    @property
    def soil_moistute_content_wilting_point(self):
        """Deprecated spelling of :attr:`soil_moisture_content_wilting_point`."""
        warnings.warn(
            "soil_moistute_content_wilting_point is deprecated; "
            "use soil_moisture_content_wilting_point.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.soil_moisture_content_wilting_point

    @soil_moistute_content_wilting_point.setter
    def soil_moistute_content_wilting_point(self, value):
        warnings.warn(
            "soil_moistute_content_wilting_point is deprecated; "
            "use soil_moisture_content_wilting_point.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.soil_moisture_content_wilting_point = value

    def initial(self):
        """Contains the initialization of variables used in the model.

        Contains operations to init the state of the model at time step 0.
        Operations included in this section are executed once.
        """

        self.logger.info("Setting up model initial parameters...")

        self.logger.debug("Reading DEM file...")
        self.dem = self.__read_raster(self.config.raster_files.dem, FieldScale.SCALAR)

        if self.config.raster_files.ldd:
            self.logger.info("Reading Local Drain Direction (LDD) file...")
            self.ldd = self.__read_raster(self.config.raster_files.ldd, FieldScale.LDD)
        else:
            self.logger.info(
                "Local Drain Direction (LDD) raster map not specified, generating one based on DEM..."
            )
            self.ldd = pcrfw.lddcreate(self.dem, 1e31, 1e31, 1e31, 1e31)

        self.logger.info("Creating slope map based on DEM...")
        self.slope = pcrfw.slope(self.dem)

        if self.config.raster_files.sample_locations and self.config.output_variables.tss:
            self.logger.info("Setting up TSS output files...")
            self.sample_vals = self.__initial_setup_sample_locations()
            self.__initial_setup_timeoutput_timeseries()

        self.logger.info("Reading min. and max. NDVI rasters...")
        self.ndvi_max = self.__read_raster(self.config.raster_files.ndvi_max, FieldScale.SCALAR)
        self.ndvi_min = self.__read_raster(self.config.raster_files.ndvi_min, FieldScale.SCALAR)

        self.logger.info("Computing min. and max. Reflectances Simple Ratio (SR)")
        self.min_reflectances_simple_ratio = Interception.get_reflectances_simple_ratio(
            self.ndvi_min
        )
        self.max_reflectances_simple_ratio = Interception.get_reflectances_simple_ratio(
            self.ndvi_max
        )

        self.logger.info("Reading soil attributes...")
        soil = self.__read_raster(self.config.raster_files.soil, FieldScale.NOMINAL)

        self.logger.info("Reading hydraulic conductivity coefficient...")
        self.soil_hydraulic_conductivity_coef = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.k_sat,
            lookup_value=soil,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.info("Reading soil density...")
        self.soil_bulk_density = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.bulk_density,
            lookup_value=soil,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.info("Reading soil root zone depth...")
        self.soil_rootzone_depth = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.rootzone_depth,
            lookup_value=soil,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.info("Reading soil moisture for saturation of the first layer...")
        tusat_partial = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.t_sat,
            lookup_value=soil,
            lookup_func=pcrfw.lookupscalar,
        )
        self.soil_moist_content_sat_point = (
            tusat_partial * self.soil_bulk_density * self.soil_rootzone_depth * 10
        )
        self.initial_soil_moist_content = (
            self.soil_moist_content_sat_point
            * self.config.initial_soil_conditions.initial_soil_moisture_content
        )

        self.logger.info("Reading soil ground wilting point...")
        tuw_partial = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.t_wp,
            lookup_value=soil,
            lookup_func=pcrfw.lookupscalar,
        )
        self.soil_moisture_content_wilting_point = (
            tuw_partial * self.soil_bulk_density * self.soil_rootzone_depth * 10
        )

        self.logger.info("Reading soil field capacity...")
        tuw_partial = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.t_fcap,
            lookup_value=soil,
            lookup_func=pcrfw.lookupscalar,
        )
        self.soil_moisture_content_field_capacity = (
            tuw_partial * self.soil_bulk_density * self.soil_rootzone_depth * 10
        )

        self.logger.info("Establishing initial conditions...")
        self.initial_baseflow = pcrfw.scalar(self.config.initial_soil_conditions.initial_baseflow)
        self.baseflow_threshold = pcrfw.scalar(self.config.initial_soil_conditions.baseflow_limit)
        self.initial_soil_sat_zone_storage = pcrfw.scalar(
            self.config.initial_soil_conditions.initial_saturated_zone_storage
        )
        self.previous_soil_moist_content = self.initial_soil_moist_content
        self.previous_soil_sat_zone_storage = self.initial_soil_sat_zone_storage
        self.previous_baseflow = self.initial_baseflow
        self.current_soil_moist_content = self.initial_soil_moist_content
        self.current_soil_sat_zone_storage = self.initial_soil_sat_zone_storage
        self.current_baseflow = self.initial_baseflow
        self.initial_cell_total_flow = pcrfw.scalar(0)
        self.previous_cell_total_flow = pcrfw.scalar(0)

        self.__release_initial_state()

    def __release_initial_state(self):
        """Drop the rasters the dynamic section never reads again.

        A PCRaster field is freed when its last Python reference goes. The DEM
        only feeds the LDD and the slope, and the initial conditions have been
        copied into the previous-step state, so keeping them on the model
        would hold full-grid rasters for the whole run.
        """
        self.dem = None
        self.initial_soil_moist_content = None
        self.initial_baseflow = None
        self.initial_soil_sat_zone_storage = None
        self.initial_cell_total_flow = None

    def dynamic(self):
        """Contains the implementation of the dynamic section of the model.

        Contains the operations that are executed consecutively each time step.
        Results of prev time step can be used as input for the curr time step.
        The dynamic section is executed a specified number of timesteps.
        """
        current_timestep = self.currentStep
        current_date = self.config.simulation_period.start_date + relativedelta(
            months=(current_timestep - self.config.simulation_period.first_step)
        )
        self.logger.info(
            "Cycle %s of %s (%s)",
            current_timestep,
            self.config.simulation_period.last_step,
            current_date.strftime("%b/%Y"),
        )
        self.progress.info(
            "## Timestep %d of %d", current_timestep, self.config.simulation_period.last_step
        )

        current_ndvi = self.__read_fallback_series("ndvi", "NDVI", current_timestep)
        current_landuse = self.__read_fallback_series("landuse", "land-use", current_timestep)
        current_precipitation = self.__read_series(
            "precipitation", current_timestep, conversion_func=pcr.scalar
        )
        current_potential_evapotranspiration = self.__read_series(
            "etp", current_timestep, conversion_func=pcr.scalar
        )
        current_class_a_pan_coef = self.__read_series(
            "kp", current_timestep, conversion_func=pcr.scalar
        )

        self.logger.debug(
            "Reading rainydays file from '%s'...", self.config.lookuptable_files.rainy_days
        )
        current_rainy_days = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.rainy_days,
            lookup_value=current_date.month,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Reading landuse attributes: manning...")
        current_n_manning = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.manning,
            lookup_value=current_landuse,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Reading landuse attributes: a_v...")
        vegetated_area_fraction = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.a_v,
            lookup_value=current_landuse,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Reading landuse attributes: a_o...")
        open_water_area_fraction = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.a_o,
            lookup_value=current_landuse,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Reading landuse attributes: a_s...")
        bare_soil_area_fraction = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.a_s,
            lookup_value=current_landuse,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Reading landuse attributes: a_i...")
        impervious_area_fraction = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.a_i,
            lookup_value=current_landuse,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Reading landuse attributes: K_c_min...")
        min_crop_coef = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.kc_min,
            lookup_value=current_landuse,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Reading landuse attributes: K_c_max...")
        max_crop_coef = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.kc_max,
            lookup_value=current_landuse,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Interception")
        current_reflectances_simple_ratio = Interception.get_reflectances_simple_ratio(current_ndvi)
        current_fpar = Interception.get_fpar(
            self.config.constants.fraction_photo_active_radiation_min,
            self.config.constants.fraction_photo_active_radiation_max,
            current_reflectances_simple_ratio,
            self.min_reflectances_simple_ratio,
            self.max_reflectances_simple_ratio,
        )
        current_leaf_area_index = Interception.get_leaf_area_index(
            current_fpar,
            self.config.constants.fraction_photo_active_radiation_max,
            self.config.constants.leaf_area_interception_max,
        )
        self.current_interception = Interception.get_interception(
            self.config.calibration_parameters.alpha,
            current_leaf_area_index,
            current_precipitation,
            current_rainy_days,
            vegetated_area_fraction,
        )

        self.logger.debug("Evapotranspiration")

        partial_crop_coef = Interception.get_crop_coef(
            current_ndvi, self.ndvi_min, self.ndvi_max, min_crop_coef, max_crop_coef
        )
        # If NDVI < 1.1 * NDVI_min, kc = kc_min
        crop_coef_lt_min_ndvi = pcrfw.scalar(current_ndvi < 1.1 * self.ndvi_min)
        crop_coef_gt_min_ndvi = pcrfw.scalar(current_ndvi > 1.1 * self.ndvi_min)
        current_crop_coef = pcr.scalar(
            (crop_coef_gt_min_ndvi * partial_crop_coef) + (crop_coef_lt_min_ndvi * min_crop_coef)
        )

        water_stress_coef = pcr.scalar(
            Evapotranspiration.get_water_stress_coef_et_vegetated_area(
                self.current_soil_moist_content,
                self.soil_moisture_content_wilting_point,
                self.soil_moisture_content_field_capacity,
            )
        )

        # Vegetated area
        real_et_vegetated_area = Evapotranspiration.get_et_vegetated_area(
            current_potential_evapotranspiration, current_crop_coef, water_stress_coef
        )

        # Impervious area
        # ET impervious area = Interception of impervious area
        real_et_impervious_area = self.config.constants.impervious_area_interception * pcr.scalar(
            current_precipitation != 0
        )

        # Open water
        real_et_open_water_area = Evapotranspiration.get_actual_et_open_water_area(
            current_potential_evapotranspiration,
            current_class_a_pan_coef,
            current_precipitation,
            open_water_area_fraction,
        )

        # Bare soil
        real_et_bare_soil_area = Evapotranspiration.get_water_stress_coef_et_bare_soil_area(
            current_potential_evapotranspiration, min_crop_coef, water_stress_coef
        )
        self.current_total_real_evapotranspiration = (
            (vegetated_area_fraction * real_et_vegetated_area)
            + (impervious_area_fraction * real_et_impervious_area)
            + (open_water_area_fraction * real_et_open_water_area)
            + (bare_soil_area_fraction * real_et_bare_soil_area)
        )

        self.logger.debug("Surface Runoff")

        average_daily_rain_on_rainy_days = current_precipitation / current_rainy_days
        soil_moisture_coef = SurfaceRunoff.get_coef_soil_moist_conditions(
            self.current_soil_moist_content,
            self.soil_bulk_density,
            self.soil_rootzone_depth,
            self.soil_moist_content_sat_point,
            self.config.calibration_parameters.beta,
        )
        pot_runoff_coef_permeable_areas = SurfaceRunoff.get_runoff_coef_permeable_areas(
            self.soil_moisture_content_wilting_point,
            self.soil_bulk_density,
            self.soil_rootzone_depth,
            self.slope,
            current_n_manning,
            self.config.calibration_parameters.w_1,
            self.config.calibration_parameters.w_2,
            self.config.calibration_parameters.w_3,
        )
        total_fraction_impermeable_area_per_cell = (
            SurfaceRunoff.get_impervious_surface_percent_per_grid_cell(
                open_water_area_fraction, impervious_area_fraction
            )
        )
        pot_runoff_coef_impermeable_areas = SurfaceRunoff.get_runoff_coef_impervious_area(
            total_fraction_impermeable_area_per_cell
        )
        pot_runoff_coef = SurfaceRunoff.get_weighted_pot_runoff_coef(
            total_fraction_impermeable_area_per_cell,
            pot_runoff_coef_permeable_areas,
            pot_runoff_coef_impermeable_areas,
        )
        actual_flow_coef = SurfaceRunoff.get_actual_runoff_coef(
            pot_runoff_coef,
            average_daily_rain_on_rainy_days,
            self.config.calibration_parameters.rcd,
        )
        self.current_surface_runoff = SurfaceRunoff.get_surface_runoff(
            actual_flow_coef,
            soil_moisture_coef,
            current_precipitation,
            self.current_interception,
            open_water_area_fraction,
            real_et_open_water_area,
            self.current_soil_moist_content,
            self.soil_moist_content_sat_point,
        )

        self.logger.debug("Lateral Flow")

        self.current_lateral_flow = Soil.get_lateral_flow(
            self.config.calibration_parameters.f,
            self.soil_hydraulic_conductivity_coef,
            self.current_soil_moist_content,
            self.soil_moist_content_sat_point,
        )

        self.logger.debug("Recharge Flow")

        self.current_recharge = Soil.get_recharge(
            self.config.calibration_parameters.f,
            self.soil_hydraulic_conductivity_coef,
            self.current_soil_moist_content,
            self.soil_moist_content_sat_point,
        )

        self.logger.debug("Baseflow")

        self.current_baseflow = Soil.get_baseflow(
            self.previous_baseflow,
            self.config.calibration_parameters.alpha_gw,
            self.current_recharge,
            self.current_soil_sat_zone_storage,
            self.baseflow_threshold,
        )
        self.previous_baseflow = self.current_baseflow

        self.logger.debug("Soil Balance")
        self.current_soil_moist_content = Soil.get_actual_soil_moist_cont(
            self.previous_soil_moist_content,
            current_precipitation,
            self.current_interception,
            self.current_surface_runoff,
            self.current_lateral_flow,
            self.current_recharge,
            self.current_total_real_evapotranspiration,
            open_water_area_fraction,
            self.soil_moist_content_sat_point,
        )
        self.current_soil_sat_zone_storage = Soil.get_actual_water_cont_sat_zone(
            self.previous_soil_sat_zone_storage, self.current_recharge, self.current_baseflow
        )
        self.previous_soil_moist_content = self.current_soil_moist_content
        self.previous_soil_sat_zone_storage = self.current_soil_sat_zone_storage

        self.logger.debug("Runoff")
        self.current_cell_total_discharge = (
            self.current_surface_runoff + self.current_lateral_flow + self.current_baseflow
        )  # [mm]

        conversion_den = monthrange(current_date.year, current_date.month)[1] * 24 * 3600
        current_cell_total_discharge_vol = (
            self.current_cell_total_discharge * self.config.grid.area * 0.001 / conversion_den
        )  # [m3/s]

        self.accumulated_cell_total_discharge = pcrfw.accuflux(
            self.ldd, current_cell_total_discharge_vol
        )

        self.current_runoff = (
            self.config.calibration_parameters.x * self.previous_cell_total_flow
            + (1 - self.config.calibration_parameters.x) * self.accumulated_cell_total_discharge
        )
        self.previous_cell_total_flow = self.current_runoff

        self.logger.debug("Exporting variables to files")
        self.__current_step_report()
        self.__release_step_state()

    def __release_step_state(self):
        """Drop the fluxes of the step that has just been reported.

        Only the storages and the routed flow carry over to the next step
        (``previous_*`` and the ``current_*`` storages assigned from them).
        Every other per-step field would otherwise stay referenced until the
        same attribute is assigned again, so the next step would hold two
        full-grid rasters per flux at its peak.
        """
        self.current_interception = None
        self.current_total_real_evapotranspiration = None
        self.current_surface_runoff = None
        self.current_lateral_flow = None
        self.current_recharge = None
        self.current_cell_total_discharge = None
        self.accumulated_cell_total_discharge = None
        self.current_runoff = None

    def __current_step_report(self):
        output_vars_dict = {
            self.config.output_variables.itp.id: self.current_interception,
            self.config.output_variables.bfw.id: self.current_baseflow,
            self.config.output_variables.srn.id: self.current_surface_runoff,
            self.config.output_variables.eta.id: self.current_total_real_evapotranspiration,
            self.config.output_variables.lfw.id: self.current_lateral_flow,
            self.config.output_variables.rec.id: self.current_recharge,
            self.config.output_variables.smc.id: self.current_soil_moist_content,
            self.config.output_variables.rnf.id: self.current_cell_total_discharge,
            self.config.output_variables.arn.id: self.current_runoff,
        }

        self.__report_raster_series(output_vars_dict)

        if self.config.raster_files.sample_locations:
            self.__report_time_series(output_vars_dict)

    def __report_raster_series(self, output_vars_dict):
        for var in self.config.output_variables.get_enabled_raster_series():
            if OutputFileFormat.PCRASTER in self.config.output_variables.file_formats:
                self.report(
                    variable=output_vars_dict.get(var.id),
                    name=str(Path(self.config.output_directory.path) / var.raster_filename_prefix),
                )

            if OutputFileFormat.GEOTIFF in self.config.output_variables.file_formats:
                report(
                    variable=output_vars_dict.get(var.id),
                    name=var.raster_filename_prefix,
                    timestep=self.currentStep,
                    outpath=self.config.output_directory.path,
                    file_format=OutputFileFormat.GEOTIFF,
                    base_raster_info=self.config.output_raster_base,
                    no_data_value=self.config.output_variables.no_data_value,
                )

    def __report_time_series(self, output_vars_dict):
        for var in self.config.output_variables.get_enabled_time_series():
            # The same as self.tss_file_xxx.sample(self.xxx)
            sample_func = self.sample_time_series_dict.get(var.id)
            if sample_func is None:
                raise RuntimeError(
                    f"No time-series writer was set up for the enabled variable '{var.get('id')}'."
                )
            sample_func(output_vars_dict.get(var.id))

    def __initial_setup_timeoutput_timeseries(self):
        """Initial setup of timeoutput timeseries.

        Initialize Tss report at sample locations or pits for each enabled output variable.
        """
        for var in self.config.output_variables.get_enabled_time_series():
            id_map = (
                self.sample_map
                if is_geotiff(self.config.raster_files.sample_locations)
                else self.config.raster_files.sample_locations
            )
            tss_file = TimeoutputTimeseriesAdapter(
                str(Path(self.config.output_directory.path) / var.table_filename_prefix),
                self,
                id_map,
                noHeader=True,
            )
            self.sample_time_series_dict[var.id] = tss_file.sample

    def __initial_setup_sample_locations(self) -> np.ndarray:
        """Initial setup of sample locations.

        Read the sample locations from the file and create a 1D array with unique locations values.
        """
        self.sample_map = pcrfw.nominal(
            self.__read_raster(self.config.raster_files.sample_locations, FieldScale.NOMINAL)
        )
        sample_array = pcrfw.pcr2numpy(map=self.sample_map, mv=MISSING_VALUE_DEFAULT)
        return np.asarray(np.unique(sample_array))

    def __read_series(
        self, series: str, step: int, conversion_func: Callable | None = None
    ) -> Field:
        """Read the raster a series provides for ``step``.

        :raises RuntimeError: If the series has no raster for the step, or the
            raster cannot be read.
        """
        resolver = self.config.series_resolvers[series]
        answer = resolver.path_for_step(step)
        if isinstance(answer, MissingStep):
            self.logger.error("%s", answer)
            raise RuntimeError(str(answer))
        self.logger.debug("Reading %s map from '%s'...", series, answer)
        scale = FieldScale.NOMINAL if series == "landuse" else FieldScale.SCALAR
        return self.__readmap_series_wrapper(
            files_partial_path=answer,
            dynamic_readmap_func=lambda path: read_field(path, scale),
            conversion_func=conversion_func,
        )

    def __read_fallback_series(self, series: str, label: str, step: int) -> Field:
        """Read a series that may reuse the previous raster on a missing step."""
        previous_name = f"previous_{series}"
        try:
            current = self.__read_series(series, step)
        except RuntimeError as error:
            previous = getattr(self, previous_name)
            if previous is None:
                raise RuntimeError(
                    f"Could not read the {label} raster for timestep {step} "
                    f"({self.config.series_resolvers[series]!r}), and there is no previous "
                    "raster to fall back to."
                ) from error
            self.logger.warning(
                "There was a problem reading the %s raster on timestep %d. "
                "Using the raster from the previous successful timestep...",
                label,
                step,
            )
            return previous
        setattr(self, previous_name, current)
        return current

    def __readmap_series_wrapper(
        self,
        files_partial_path: str | bytes | os.PathLike,
        dynamic_readmap_func: Callable,
        conversion_func: Callable | None = None,
        suppress_errors: bool = False,
    ) -> Field:
        """Read a map from a raster series for a given step from a specified location.

        :param dynamic_readmap_func: Function to read the map file.
        :type dynamic_readmap_func: Callable

        :param files_partial_path: The path where the data map is located and prefix combined.
        :type files_partial_path: Union[str, bytes, os.PathLike]

        :param conversion_func: Function to convert the read map to the desired data type. Default is ``None``.
        :type conversion_func: Optional[Callable]

        :param suppress_errors: If ``True``, suppresses errors and returns ``None``. Default is ``False``.
        :type suppress_errors: Optional[bool]

        :return: The data map read from the file.
        :rtype: Field

        :raises RuntimeError: The data map for the step was not found in the specified path.
        """

        try:
            if conversion_func:
                self.logger.debug("Reading and converting map from '%s'...", files_partial_path)
                return conversion_func(dynamic_readmap_func(files_partial_path))

            self.logger.debug("Reading map from '%s'...", files_partial_path)
            return dynamic_readmap_func(files_partial_path)
        except RuntimeError:
            if not suppress_errors:
                self.logger.error("Error reading map from '%s'", files_partial_path)
            raise

    def __read_raster(self, file_path, scale: FieldScale) -> Field:
        """Read an input raster (PCRaster map or GeoTIFF) as a field on the clone."""
        try:
            self.logger.debug("Reading %s raster from '%s'...", scale.value, file_path)
            return read_field(file_path, scale)
        except (RuntimeError, ValueError):
            self.logger.error("Error reading map from '%s'", file_path)
            raise

    def __lookup_wrapper(
        self,
        file_path: str | bytes | os.PathLike,
        lookup_value,
        lookup_func: Callable,
    ) -> Field:
        """Read a data from a lookup table for a given data type.

        :param file_path: The file path where the data is located.
        :type file_path: Union[str, bytes, os.PathLike]

        :param lookup_value: The value to lookup in the table.
        :type lookup_value: Variable

        :param lookup_func: Function to read the lookup file.
        :type lookup_func: Callable

        :return: The data read from the table.
        :rtype: Field

        :raises RuntimeError: The specified data was not loaded correctly.
        """

        try:
            self.logger.debug("Reading lookup table from '%s'...", file_path)
            return lookup_func(file_path, lookup_value)
        except RuntimeError:
            self.logger.error("Error reading lookup table from '%s'", file_path)
            raise
