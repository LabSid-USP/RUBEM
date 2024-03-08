from calendar import monthrange
import os
import logging
from typing import Callable, Optional, Union

from dateutil.relativedelta import relativedelta
import numpy as np
import pcraster as pcr
import pcraster.framework as pcrfw

from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.output_format import OutputFileFormat
from rubem.file._file_generators import report
from rubem.hydrological_processes import Evapotranspiration, Interception, Soil, SurfaceRunoff


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

        self.config = config

        self.logger.info("Reading clone file...")
        self.__readmap_wrapper(file_path=self.config.raster_files.clone, readmap_func=pcr.setclone)

        self.enabled_ouput_vars = {
            "itp": self.config.output_variables.itp,
            "bfw": self.config.output_variables.bfw,
            "srn": self.config.output_variables.srn,
            "eta": self.config.output_variables.eta,
            "lfw": self.config.output_variables.lfw,
            "rec": self.config.output_variables.rec,
            "smc": self.config.output_variables.smc,
            "rnf": self.config.output_variables.rnf,
            "arn": self.config.output_variables.arn,
        }

        self.sample_time_series_dict = {}

    def initial(self):
        """Contains the initialization of variables used in the model.

        Contains operations to init the state of the model at time step 0.
        Operations included in this section are executed once.
        """

        self.logger.info("Setting up model initial parameters...")

        self.logger.debug("Reading DEM file...")
        self.dem = self.__readmap_wrapper(self.config.raster_files.dem)

        if self.config.raster_files.ldd:
            self.logger.info("Reading Local Drain Direction (LDD) file...")
            self.ldd = self.__readmap_wrapper(
                file_path=self.config.raster_files.ldd,
                conversion_func=pcr.ldd,
            )
        else:
            self.logger.info(
                "Local Drain Direction (LDD) raster map not specified, generating one based on DEM..."
            )
            self.ldd = pcrfw.lddcreate(self.dem, 1e31, 1e31, 1e31, 1e31)

        self.logger.info("Creating slope map based on DEM...")
        self.slope = pcrfw.slope(self.dem)

        if self.config.raster_files.sample_locations and self.config.output_variables.tss:
            self.logger.info("Setting up TSS output files...")
            self.__initial_setup_timeoutput_timeseries()

        self.logger.info("Reading min. and max. NDVI rasters...")
        self.ndvi_max = self.__readmap_wrapper(self.config.raster_files.ndvi_max)
        self.ndvi_min = self.__readmap_wrapper(self.config.raster_files.ndvi_min)

        self.logger.info("Computing min. and max. Reflectances Simple Ratio (SR)")
        self.min_reflectances_simple_ratio = Interception.get_reflectances_simple_ration(
            self.ndvi_min
        )
        self.max_reflectances_simple_ratio = Interception.get_reflectances_simple_ration(
            self.ndvi_max
        )

        self.logger.info("Reading soil attributes...")
        soil = self.__readmap_wrapper(self.config.raster_files.soil)

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
        self.soil_moistute_content_wilting_point = (
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

    def dynamic(self):
        """Contains the implementation of the dynamic section of the model.

        Contains the operations that are executed consecutively each time step.
        Results of prev time step can be used as input for the curr time step.
        The dynamic section is executed a specified number of timesteps.
        """
        current_timestep = self.currentStep
        self.logger.info(f"Cycle {current_timestep} of {self.config.simulation_period.last_step}")
        print(f"## Timestep {current_timestep} of {self.config.simulation_period.last_step}")

        self.logger.debug("Reading NDVI map from '%s'...", self.config.raster_series.ndvi)
        try:
            current_ndvi = self.__readmap_series_wrapper(
                files_partial_path=self.config.raster_series.ndvi,
                dynamic_readmap_func=self.readmap,
                supress_errors=True,
            )
            self.previous_ndvi = current_ndvi
        except RuntimeError:
            self.logger.warning(
                "There was an problem reading NDVI map from '%s' on timestep %d. Using previous successful timestep raster...",
                self.config.raster_series.ndvi,
                current_timestep,
            )
            current_ndvi = self.previous_ndvi

        self.logger.debug("Reading landuse map from '%s'...", self.config.raster_series.landuse)
        try:
            self.current_landuse = self.__readmap_series_wrapper(
                files_partial_path=self.config.raster_series.landuse,
                dynamic_readmap_func=self.readmap,
                supress_errors=True,
            )
            self.previous_landuse = self.current_landuse
        except RuntimeError:
            self.logger.warning(
                "There was an problem reading LULC map from '%s' on timestep %d. Using previous successful timestep raster...",
                self.config.raster_series.landuse,
                current_timestep,
            )
            self.current_landuse = self.previous_landuse

        self.logger.debug(
            "Reading precipitation map from '%s'...", self.config.raster_series.precipitation
        )
        current_precipitation = self.__readmap_series_wrapper(
            files_partial_path=self.config.raster_series.precipitation,
            dynamic_readmap_func=self.readmap,
            conversion_func=pcr.scalar,
        )

        self.logger.debug(
            "Reading potential evapotranspiration map from '%s'...", self.config.raster_series.etp
        )
        current_potential_evapotranspiration = self.__readmap_series_wrapper(
            files_partial_path=self.config.raster_series.etp,
            dynamic_readmap_func=self.readmap,
            conversion_func=pcr.scalar,
        )

        self.logger.debug("Reading Kp map from '%s'...", self.config.raster_series.kp)
        current_class_a_pan_coef = self.__readmap_series_wrapper(
            files_partial_path=self.config.raster_series.kp,
            dynamic_readmap_func=self.readmap,
            conversion_func=pcr.scalar,
        )

        self.logger.debug(
            "Reading rainydays file from '%s'...", self.config.lookuptable_files.rainy_days
        )
        month = ((current_timestep - 1) % 12) + 1
        current_rainy_days = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.rainy_days,
            lookup_value=month,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Reading landuse attributes: manning...")
        current_n_manning = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.manning,
            lookup_value=self.current_landuse,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Reading landuse attributes: a_v...")
        vegeted_area_fraction = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.a_v,
            lookup_value=self.current_landuse,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Reading landuse attributes: a_o...")
        open_water_area_fraction = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.a_o,
            lookup_value=self.current_landuse,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Reading landuse attributes: a_s...")
        bare_soil_area_fraction = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.a_s,
            lookup_value=self.current_landuse,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Reading landuse attributes: a_i...")
        impervious_area_fraction = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.a_i,
            lookup_value=self.current_landuse,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Reading landuse attributes: K_c_min...")
        self.min_crop_coef = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.kc_min,
            lookup_value=self.current_landuse,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Reading landuse attributes: K_c_max...")
        self.max_crop_coef = self.__lookup_wrapper(
            file_path=self.config.lookuptable_files.kc_max,
            lookup_value=self.current_landuse,
            lookup_func=pcrfw.lookupscalar,
        )

        self.logger.debug("Interception")
        current_reflectances_simple_ratio = Interception.get_reflectances_simple_ration(
            current_ndvi
        )
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
            vegeted_area_fraction,
        )

        self.logger.debug("Evapotranspiration")

        partial_crop_coef = Interception.get_crop_coef(
            current_ndvi, self.ndvi_min, self.ndvi_max, self.min_crop_coef, self.max_crop_coef
        )
        # If NDVI < 1.1 * NDVI_min, kc = kc_min
        crop_coef_lt_min_ndvi = pcrfw.scalar(current_ndvi < 1.1 * self.ndvi_min)
        crop_coef_gt_min_ndvi = pcrfw.scalar(current_ndvi > 1.1 * self.ndvi_min)
        current_crop_coef = pcr.scalar(
            (crop_coef_gt_min_ndvi * partial_crop_coef)
            + (crop_coef_lt_min_ndvi * self.min_crop_coef)
        )

        # TODO: Rename variable
        Ks = pcr.scalar(
            Evapotranspiration.get_water_stress_coef_et_vegeted_area(
                self.current_soil_moist_content,
                self.soil_moistute_content_wilting_point,
                self.soil_moisture_content_field_capacity,
            )
        )

        # Vegetated area
        self.real_et_vegeted_area = Evapotranspiration.get_et_vegetated_area(
            current_potential_evapotranspiration, current_crop_coef, Ks
        )

        # Impervious area
        # ET impervious area = Interception of impervious area
        self.real_et_impervious_area = (
            self.config.constants.impervious_area_interception
            * pcr.scalar(current_precipitation != 0)
        )

        # Open water
        self.real_et_open_water_area = Evapotranspiration.get_actual_et_open_water_area(
            current_potential_evapotranspiration,
            current_class_a_pan_coef,
            current_precipitation,
            open_water_area_fraction,
        )

        # Bare soil
        self.real_et_bare_soil_area = Evapotranspiration.get_water_stress_coef_et_bare_soil_area(
            current_potential_evapotranspiration, self.min_crop_coef, Ks
        )
        self.total_real_et = (
            (vegeted_area_fraction * self.real_et_vegeted_area)
            + (impervious_area_fraction * self.real_et_impervious_area)
            + (open_water_area_fraction * self.real_et_open_water_area)
            + (bare_soil_area_fraction * self.real_et_bare_soil_area)
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
            self.soil_moistute_content_wilting_point,
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
            self.real_et_open_water_area,
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
        self.current_soil_moist_content = Soil.get_actual_soil_moist_cont_non_sat_zone(
            self.previous_soil_moist_content,
            current_precipitation,
            self.current_interception,
            self.current_surface_runoff,
            self.current_lateral_flow,
            self.current_recharge,
            self.total_real_et,
            open_water_area_fraction,
            self.soil_moist_content_sat_point,
        )
        self.current_soil_sat_zone_storage = Soil.get_actual_water_cont_sat_zone(
            self.previous_soil_sat_zone_storage, self.current_recharge, self.current_baseflow
        )
        self.previous_soil_moist_content = self.current_soil_moist_content
        self.previous_soil_sat_zone_storage = self.current_soil_sat_zone_storage

        self.logger.debug("Runoff")

        base_date = self.config.simulation_period.start_date + relativedelta(
            months=current_timestep - 1
        )
        conversion_den = monthrange(base_date.year, base_date.month)[1] * 24 * 3600

        self.current_cell_total_discharge = (
            self.current_surface_runoff + self.current_lateral_flow + self.current_baseflow
        )  # [mm]
        self.current_cell_total_discharge_vol = (
            self.current_cell_total_discharge * self.config.grid.area * 0.001 / conversion_den
        )  # [m3/s]

        self.accumulated_cell_total_discharge = pcrfw.accuflux(
            self.ldd, self.current_cell_total_discharge_vol
        )

        self.current_runoff = (
            self.config.calibration_parameters.x * self.previous_cell_total_flow
            + (1 - self.config.calibration_parameters.x) * self.accumulated_cell_total_discharge
        )
        self.previous_cell_total_flow = self.current_runoff

        os.chdir(self.config.output_directory.path)
        self.logger.debug("Exporting variables to files")

        self.__current_step_report()

    def __current_step_report(self):
        output_vars_dict = {
            "itp": self.current_interception,
            "bfw": self.current_baseflow,
            "srn": self.current_surface_runoff,
            "eta": self.total_real_et,
            "lfw": self.current_lateral_flow,
            "rec": self.current_recharge,
            "smc": self.current_soil_moist_content,
            "rnf": self.current_cell_total_discharge,
            "arn": self.current_runoff,
        }

        for output_var, is_output_var_enabled in self.enabled_ouput_vars.items():
            if not is_output_var_enabled:
                continue

            # Export TIFF raster series
            if self.config.output_variables.file_format is OutputFileFormat.GEOTIFF:
                report(
                    variable=output_vars_dict.get(output_var),
                    name=output_var,
                    timestep=self.currentStep,
                    outpath=self.config.output_directory.path,
                    file_format=OutputFileFormat.GEOTIFF,
                    base_raster_info=self.config.output_raster_base,
                )

            # Export PCRaster map format raster series
            if self.config.output_variables.file_format is OutputFileFormat.PCRASTER:
                self.report(variable=output_vars_dict.get(output_var), name=output_var)

            # Check if we have to export the time series of the selected
            # variable (fileName)
            if self.config.raster_files.sample_locations and self.config.output_variables.tss:
                # Export tss according to variable (fileName) selected
                # The same as self.tss_file_xxx.sample(self.xxx)
                self.sample_time_series_dict.get(output_var)(output_vars_dict.get(output_var))

    def __initial_setup_timeoutput_timeseries(self):

        if not self.config.raster_files.sample_locations:
            return

        sample_map = self.__readmap_wrapper(
            file_path=self.config.raster_files.sample_locations,
            readmap_func=pcrfw.nominal,
        )
        # Information for output, get sample location numbers - integer,
        # Convert sample location to multidimensional array
        sample_array = pcrfw.pcr2numpy(sample_map, -999)
        # create 1d array with unique locations values
        # (1 to N number os locations)
        self.sample_vals = np.asarray(np.unique(sample_array))

        # Initialize Tss report at sample locations or pits
        variables = ["itp", "bfw", "srn", "eta", "lfw", "rec", "smc", "rnf", "arn"]
        for var in variables:
            tss_file = pcrfw.TimeoutputTimeseries(
                f"tss_{var}",
                self,
                self.config.raster_files.sample_locations,
                noHeader=True,
            )
            self.sample_time_series_dict[var] = tss_file.sample

    def __readmap_series_wrapper(
        self,
        files_partial_path: Union[str, bytes, os.PathLike],
        dynamic_readmap_func: Callable,
        conversion_func: Optional[Callable] = None,
        supress_errors: bool = False,
    ) -> pcr._pcraster.Field:
        """Read a map from a raster series for a given step from a specified location.

        :param dynamic_readmap_func: Function to read the map file.
        :type dynamic_readmap_func: Callable

        :param files_partial_path: The path where the data map is located and prefix combined.
        :type files_partial_path: Union[str, bytes, os.PathLike]

        :param conversion_func: Function to convert the read map to the desired data type. Default is ``None``.
        :type conversion_func: Optional[Callable]

        :param supress_errors: If ``True``, suppresses errors and returns ``None``. Default is ``False``.
        :type supress_errors: Optional[bool]

        :return: The data map read from the file.
        :rtype: pcr._pcraster.Field

        :raises RuntimeError: The data map for the step was not found in the specified path.
        """

        try:
            if conversion_func:
                self.logger.debug("Reading and converting map from '%s'...", files_partial_path)
                return conversion_func(dynamic_readmap_func(files_partial_path))

            self.logger.debug("Reading map from '%s'...", files_partial_path)
            return dynamic_readmap_func(files_partial_path)
        except RuntimeError:
            if not supress_errors:
                self.logger.error("Error reading map from '%s'", files_partial_path)
            raise

    def __readmap_wrapper(
        self,
        file_path: Union[str, bytes, os.PathLike],
        readmap_func: Callable = pcrfw.readmap,
        conversion_func: Optional[Callable] = None,
    ) -> pcr._pcraster.Field:
        """Read a data map for a given data type from a specified location.

        :param file_path: The path where the data map is located.
        :type file_path: Union[str, bytes, os.PathLike]

        :param readmap_func: Function to read the map file. Default is ``pcrfw.readmap``.
        :type readmap_func: Callable

        :param conversion_func: Function to convert the read map to the desired data type. Default is ``None``.
        :type conversion_func: Optional[Callable]

        :return: The data map read from the file.
        :rtype: pcr._pcraster.Field

        :raises RuntimeError: The specified data map was not loaded correctly.
        """

        try:
            if conversion_func:
                self.logger.debug("Reading and converting map from '%s'...", file_path)
                return conversion_func(readmap_func(file_path))

            self.logger.debug("Reading map from '%s'...", file_path)
            return readmap_func(file_path)
        except RuntimeError:
            self.logger.error("Error reading map from '%s'", file_path)
            raise

    def __lookup_wrapper(
        self,
        file_path: Union[str, bytes, os.PathLike],
        lookup_value,
        lookup_func: Callable,
    ) -> pcr._pcraster.Field:
        """Read a data from a lookup table for a given data type.

        :param file_path: The file path where the data is located.
        :type file_path: Union[str, bytes, os.PathLike]

        :param lookup_value: The value to lookup in the table.
        :type lookup_value: Variable

        :param lookup_func: Function to read the lookup file.
        :type lookup_func: Callable

        :return: The data read from the table.
        :rtype: pcr._pcraster.Field

        :raises RuntimeError: The specified data was not loaded correctly.
        """

        try:
            self.logger.debug("Reading lookup table from '%s'...", file_path)
            return lookup_func(file_path, lookup_value)
        except RuntimeError:
            self.logger.error("Error reading lookup table from '%s'", file_path)
            raise
