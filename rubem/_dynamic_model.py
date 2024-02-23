import os
import logging

import numpy as np
import pcraster as pcr
import pcraster.framework as pcrfw
from rubem.configuration.output_format import OutputFileFormat

from rubem.modules._evapotranspiration import *
from rubem.modules._interception import *
from rubem.modules._soil import *
from rubem.modules._surface_runoff import *
from rubem.date._date_calc import *
from rubem.file._file_generators import *
from rubem.configuration.model_configuration import ModelConfiguration


class RUBEM(pcrfw.DynamicModel):
    def __init__(self, config: ModelConfiguration):
        pcrfw.DynamicModel.__init__(self)
        self.logger = logging.getLogger(__name__)

        self.config = config

        self.logger.info("Reading clone file...")
        try:
            pcr.setclone(self.config.raster_files.clone)
        except RuntimeError:
            self.logger.error("Error reading clone file at '%s'", self.config.raster_files.clone)
            raise

        # TODO: Automatic calculation of cell area
        self.logger.info("Obtaining grid cell area...")
        self.A = self.config.grid.area

        self.logger.info("Obtaining initial baseflow...")
        self.EBini = pcrfw.scalar(self.config.initial_soil_conditions.initial_baseflow)

        self.logger.info("Obtaining baseflow limit...")
        self.EBlim = pcrfw.scalar(self.config.initial_soil_conditions.baseflow_limit)

        self.logger.info("Obtaining initial moisture content of the saturated zone...")
        self.Tusini = pcrfw.scalar(
            self.config.initial_soil_conditions.initial_saturated_zone_storage
        )

        self.logger.debug("Reading DEM reference file...")
        try:
            self.ref = getRefInfo(self.config.raster_files.demtif)
        except RuntimeError:
            self.logger.error(
                "Error reading Digital Elevation Model (DEM) file at '%s'",
                self.config.raster_files.demtif,
            )
            raise

        self.__getEnabledOutputVars()

    def __getEnabledOutputVars(self):
        # Store which variables have or have not been selected for export
        self.enabledOuputVars = {
            "itp": self.config.output_variables.itp,
            "bfw": self.config.output_variables.bfw,
            "srn": self.config.output_variables.srn,
            "eta": self.config.output_variables.eta,
            "lfw": self.config.output_variables.lfw,
            "rec": self.config.output_variables.rec,
            "smc": self.config.output_variables.smc,
            "rnf": self.config.output_variables.rnf,
        }

    def __stepUpdateOutputVars(self):
        self.outputVarsDict = {
            "itp": self.Itp,
            "bfw": self.EB,
            "srn": self.ES,
            "eta": self.ETr,
            "lfw": self.LF,
            "rec": self.REC,
            "smc": self.TUr,
            "rnf": self.runoff,
        }

    def __stepReport(self):
        self.__stepUpdateOutputVars()

        for outputVar, isOutputVarEnabled in self.enabledOuputVars.items():
            if not isOutputVarEnabled:
                continue

            # Export TIFF raster series
            if self.config.output_variables.file_format is OutputFileFormat.GEOTIFF:
                reportTIFFSeries(
                    self,
                    self.ref,
                    self.outputVarsDict.get(outputVar),
                    outputVar,
                    self.config.output_directory.path,
                    self.currentStep,
                    dyn=True,
                )

            # Export PCRaster map format raster series
            if self.config.output_variables.file_format is OutputFileFormat.PCRASTER:
                self.report(self.outputVarsDict.get(outputVar), outputVar)

            # Check if we have to export the time series of the selected
            # variable (fileName)
            if self.config.raster_files.sample_locations and self.config.output_variables.tss:
                # Export tss according to variable (fileName) selected
                # The same as self.TssFileXxx.sample(self.Xxx)
                self.sampleTimeSeriesDict.get(outputVar)(self.outputVarsDict.get(outputVar))

    def __setupTimeoutputTimeseries(self):
        # read sample map location as nominal
        try:
            sample_map = pcrfw.nominal(self.config.raster_files.sample_locations)
        except RuntimeError:
            self.logger.error(
                "Error reading sample map file at '%s'"
                % (self.config.raster_files.sample_locations)
            )
            raise

        # Initialize Tss report at sample locations or pits
        self.TssFileRun = pcrfw.TimeoutputTimeseries(
            "tss_rnf",
            self,
            self.config.raster_files.sample_locations,
            noHeader=True,
        )
        self.TssFileInt = pcrfw.TimeoutputTimeseries(
            "tss_itp",
            self,
            self.config.raster_files.sample_locations,
            noHeader=True,
        )
        self.TssFileBflow = pcrfw.TimeoutputTimeseries(
            "tss_bfw",
            self,
            self.config.raster_files.sample_locations,
            noHeader=True,
        )
        self.TssFileSfRun = pcrfw.TimeoutputTimeseries(
            "tss_srn",
            self,
            self.config.raster_files.sample_locations,
            noHeader=True,
        )
        self.TssFileEta = pcrfw.TimeoutputTimeseries(
            "tss_eta",
            self,
            self.config.raster_files.sample_locations,
            noHeader=True,
        )
        self.TssFileLf = pcrfw.TimeoutputTimeseries(
            "tss_lfw",
            self,
            self.config.raster_files.sample_locations,
            noHeader=True,
        )
        self.TssFileRec = pcrfw.TimeoutputTimeseries(
            "tss_rec",
            self,
            self.config.raster_files.sample_locations,
            noHeader=True,
        )
        self.TssFileSsat = pcrfw.TimeoutputTimeseries(
            "tss_smc",
            self,
            self.config.raster_files.sample_locations,
            noHeader=True,
        )

        self.sampleTimeSeriesDict = {
            "itp": self.TssFileInt.sample,
            "bfw": self.TssFileBflow.sample,
            "srn": self.TssFileSfRun.sample,
            "eta": self.TssFileEta.sample,
            "lfw": self.TssFileLf.sample,
            "rec": self.TssFileRec.sample,
            "smc": self.TssFileSsat.sample,
            "rnf": self.TssFileRun.sample,
        }
        # Information for output, get sample location numbers - integer,
        # from 1 to n
        self.mvalue = -999
        # Convert sample location to multidimensional array
        self.sample_array = pcrfw.pcr2numpy(sample_map, self.mvalue)
        # create 1d array with unique locations values
        # (1 to N number os locations)
        self.sample_vals = np.asarray(np.unique(self.sample_array))

    def initial(self):
        """Contains the initialization of variables used in the model.

        Contains operations to init the state of the model at time step 0.
        Operations included in this section are executed once.
        """

        self.logger.info("Setting up model initial parameters...")
        self.logger.debug("Reading DEM file...")
        # Read DEM file
        try:
            self.dem = pcrfw.readmap(self.config.raster_files.dem)
        except RuntimeError:
            self.logger.error("Error reading DEM file at '%s'" % (self.config.raster_files.dem))
            raise

        if self.config.raster_files.ldd:
            self.logger.info("Reading Local Drain Direction (LDD) file...")
            try:
                self.ldd = pcr.ldd(pcr.readmap(self.config.raster_files.ldd))
            except RuntimeError:
                self.logger.error("Error reading LDD file at '%s'" % (self.config.raster_files.ldd))
                raise
        else:
            self.logger.info(
                "Local Drain Direction (LDD) raster map not specified, generating one based on DEM..."
            )
            self.ldd = pcrfw.lddcreate(self.dem, 1e31, 1e31, 1e31, 1e31)

        self.logger.info("Creating slope map based on DEM...")
        self.S = pcrfw.slope(self.dem)

        if self.config.raster_files.sample_locations and self.config.output_variables.tss:
            self.logger.info("Setting up TSS output files...")
            self.__setupTimeoutputTimeseries()

        self.logger.info("Reading min. and max. NDVI rasters...")
        try:
            self.ndvi_min = pcrfw.scalar(pcrfw.readmap(self.config.raster_files.ndvi_min))
        except RuntimeError:
            self.logger.error(
                "Error reading NDVI min file at '%s'" % (self.config.raster_files.ndvi_min)
            )
            raise

        try:
            self.ndvi_max = pcrfw.scalar(pcrfw.readmap(self.config.raster_files.ndvi_max))
        except RuntimeError:
            self.logger.error(
                "Error reading NDVI max file at '%s'" % (self.config.raster_files.ndvi_max)
            )
            raise

        self.logger.info("Computing min. and max. surface runoff (SR)")
        self.sr_min = srCalc(self.ndvi_min)
        self.sr_max = srCalc(self.ndvi_max)

        self.logger.info("Reading soil attributes...")
        try:
            solo = pcrfw.readmap(self.config.raster_files.soil)
        except RuntimeError:
            self.logger.error("Error reading soil file at '%s'" % (self.config.raster_files.soil))
            raise

        self.logger.info("Reading hydraulic conductivity coefficient...")
        try:
            self.Kr = pcrfw.lookupscalar(self.config.lookuptable_files.k_sat, solo)
        except RuntimeError:
            self.logger.error(
                "Error reading K_sat file at '%s'" % (self.config.lookuptable_files.k_sat)
            )
            raise

        self.logger.info("Reading soil density...")
        try:
            self.dg = pcrfw.lookupscalar(self.config.lookuptable_files.bulk_density, solo)
        except RuntimeError:
            self.logger.error(
                "Error reading bulk_density file at '%s'"
                % (self.config.lookuptable_files.bulk_density)
            )
            raise

        self.logger.info("Reading soil root zone depth...")
        try:
            self.Zr = pcrfw.lookupscalar(self.config.lookuptable_files.rootzone_depth, solo)
        except RuntimeError:
            self.logger.error(
                "Error reading rootzone_depth file at '%s'"
                % (self.config.lookuptable_files.rootzone_depth)
            )
            raise

        self.logger.info("Reading soil moisture for saturation of the first layer...")
        try:
            self.TUsat = (
                pcrfw.lookupscalar(self.config.lookuptable_files.t_sat, solo)
                * self.dg
                * self.Zr
                * 10
            )
        except RuntimeError:
            self.logger.error(
                "Error reading T_sat file at '%s'" % (self.config.lookuptable_files.t_sat)
            )
            raise

        self.TUr_ini = (
            self.TUsat * self.config.initial_soil_conditions.initial_soil_moisture_content
        )

        self.logger.info("Reading soil ground wilting point...")
        try:
            self.TUw = (
                pcrfw.lookupscalar(self.config.lookuptable_files.t_wp, solo)
                * self.dg
                * self.Zr
                * 10
            )
        except RuntimeError:
            self.logger.error(
                "Error reading T_wp file at '%s'" % (self.config.lookuptable_files.t_wp)
            )
            raise

        self.logger.info("Reading soil field capacity...")
        try:
            self.TUcc = (
                pcrfw.lookupscalar(self.config.lookuptable_files.t_fcap, solo)
                * self.dg
                * self.Zr
                * 10
            )
        except RuntimeError:
            self.logger.error(
                "Error reading T_fcap file at '%s'" % (self.config.lookuptable_files.t_fcap)
            )
            raise

        self.EB_ini = self.EBini  # initial baseflow [mm]
        self.EB_lim = self.EBlim  # limit for baseflow condition [mm]
        self.TUs_ini = self.Tusini  # initial moisture content of the saturated layer [mm]

        self.logger.info("Establishing initial conditions...")
        self.TUrprev = self.TUr_ini
        self.TUsprev = self.TUs_ini
        self.EBprev = self.EB_ini
        self.TUr = self.TUr_ini
        self.TUs = self.TUs_ini
        self.EB = self.EB_ini
        self.Qini = pcrfw.scalar(0)
        self.Qprev = self.Qini

    def dynamic(self):
        """Contains the implementation of the dynamic section of the model.

        Contains the operations that are executed consecutively each time step.
        Results of prev time step can be used as input for the curr time step.
        The dynamic section is executed a specified number of timesteps.
        """
        t = self.currentStep
        self.logger.info(f"Cycle {t} of {self.config.simulation_period.last_step}")
        print(f"## Timestep {t} of {self.config.simulation_period.last_step}")

        self.logger.debug("Reading NDVI map from '%s'...", self.config.raster_series.ndvi)
        try:
            ndvi = self.readmap(self.config.raster_series.ndvi)
            self.ndvi_ant = ndvi
        except RuntimeError:
            self.logger.warning(
                "Error reading NDVI map from '%s'. Using previous timestep value...",
                self.config.raster_series.ndvi,
            )
            ndvi = self.ndvi_ant

        self.logger.debug("Reading landuse map from '%s'...", self.config.raster_series.landuse)
        try:
            self.landuse = self.readmap(self.config.raster_series.landuse)
            self.landuse_ant = self.landuse
        except RuntimeError:
            self.logger.warning(
                "Error reading landuse map from '%s'. Using previous timestep value...",
                self.config.raster_series.landuse,
            )
            self.landuse = self.landuse_ant

        self.logger.debug(
            "Reading precipitation map from '%s'...", self.config.raster_series.precipitation
        )
        try:
            precipitation = pcr.scalar(self.readmap(self.config.raster_series.precipitation))
        except RuntimeError:
            self.logger.error(
                "Error reading precipitation map from '%s'", self.config.raster_series.precipitation
            )
            raise

        self.logger.debug(
            "Reading potential evapotranspiration map from '%s'...", self.config.raster_series.etp
        )
        try:
            ETp = pcr.scalar(self.readmap(self.config.raster_series.etp))
        except RuntimeError:
            self.logger.error(
                "Error reading potential evapotranspiration map from '%s'",
                self.config.raster_series.etp,
            )
            raise

        self.logger.debug("Reading Kp map from '%s'...", self.config.raster_series.kp)
        try:
            Kp = pcr.scalar(self.readmap(self.config.raster_series.kp))
        except RuntimeError:
            self.logger.error("Error reading Kp map from '%s'", self.config.raster_series.kp)
            raise

        self.logger.debug(
            "Reading rainydays file from '%s'...", self.config.lookuptable_files.rainy_days
        )
        try:
            month = ((t - 1) % 12) + 1
            rainyDays = pcrfw.lookupscalar(self.config.lookuptable_files.rainy_days, month)
        except RuntimeError:
            self.logger.error(
                "Error reading rainydays file at '%s'", self.config.lookuptable_files.rainy_days
            )
            raise

        self.logger.debug("Reading landuse attributes: manning...")
        try:
            n_manning = pcrfw.lookupscalar(self.config.lookuptable_files.manning, self.landuse)
        except RuntimeError:
            self.logger.error(
                "Error reading manning file at '%s'", self.config.lookuptable_files.manning
            )
            raise

        self.logger.debug("Reading landuse attributes: a_v...")
        try:
            Av = pcrfw.lookupscalar(self.config.lookuptable_files.a_v, self.landuse)
        except RuntimeError:
            self.logger.error("Error reading a_v file at '%s'", self.config.lookuptable_files.a_v)
            raise

        self.logger.debug("Reading landuse attributes: a_o...")
        try:
            Ao = pcrfw.lookupscalar(self.config.lookuptable_files.a_o, self.landuse)
        except RuntimeError:
            self.logger.error("Error reading a_o file at '%s'", self.config.lookuptable_files.a_o)
            raise

        self.logger.debug("Reading landuse attributes: a_s...")
        try:
            As = pcrfw.lookupscalar(self.config.lookuptable_files.a_s, self.landuse)
        except RuntimeError:
            self.logger.error("Error reading a_s file at '%s'", self.config.lookuptable_files.a_s)
            raise

        self.logger.debug("Reading landuse attributes: a_i...")
        try:
            Ai = pcrfw.lookupscalar(self.config.lookuptable_files.a_i, self.landuse)
        except RuntimeError:
            self.logger.error("Error reading a_i file at '%s'", self.config.lookuptable_files.a_i)
            raise

        self.logger.debug("Reading landuse attributes: K_c_min...")
        try:
            self.kc_min = pcrfw.lookupscalar(self.config.lookuptable_files.kc_min, self.landuse)
        except RuntimeError:
            self.logger.error(
                "Error reading K_c_min file at '%s'", self.config.lookuptable_files.kc_min
            )
            raise

        self.logger.debug("Reading landuse attributes: K_c_max...")
        try:
            self.kc_max = pcrfw.lookupscalar(self.config.lookuptable_files.kc_max, self.landuse)
        except RuntimeError:
            self.logger.error(
                "Error reading K_c_max file at '%s'", self.config.lookuptable_files.kc_max
            )
            raise

        self.logger.debug("Interception")
        SR = srCalc(ndvi)
        FPAR = fparCalc(
            self.config.constants.fraction_photo_active_radiation_min,
            self.config.constants.fraction_photo_active_radiation_max,
            SR,
            self.sr_min,
            self.sr_max,
        )
        LAI = laiCalc(
            FPAR,
            self.config.constants.fraction_photo_active_radiation_max,
            self.config.constants.leaf_area_interception_max,
        )
        Id, Ir, Iv, self.Itp = interceptionCalc(
            self.config.calibration_parameters.alpha,
            LAI,
            precipitation,
            rainyDays,
            Av,
        )

        self.logger.debug("Evapotranspiration")

        Kc_1 = kcCalc(ndvi, self.ndvi_min, self.ndvi_max, self.kc_min, self.kc_max)
        # condicao do kc, se NDVI < 1.1NDVI_min, kc = kc_min
        kc_cond1 = pcrfw.scalar(ndvi < 1.1 * self.ndvi_min)
        kc_cond2 = pcrfw.scalar(ndvi > 1.1 * self.ndvi_min)
        Kc = pcr.scalar((kc_cond2 * Kc_1) + (kc_cond1 * self.kc_min))
        Ks = pcr.scalar(ksCalc(self.TUr, self.TUw, self.TUcc))

        # Vegetated area
        self.ET_av = etavCalc(ETp, Kc, Ks)

        # Impervious area
        # ET impervious area = Interception of impervious area
        cond = pcr.scalar((precipitation != 0))
        self.ET_ai = self.config.constants.impervious_area_interception * cond

        # Open water
        self.ET_ao = etaoCalc(ETp, Kp, precipitation, Ao)
        # self.report(ET_ao,self.config.output_directory.output+'ETao')

        # Bare soil
        self.ET_as = etasCalc(ETp, self.kc_min, Ks)
        self.ETr = (Av * self.ET_av) + (Ai * self.ET_ai) + (Ao * self.ET_ao) + (As * self.ET_as)

        self.logger.debug("Surface Runoff")

        Pdm = precipitation / rainyDays
        Ch = chCalc(
            self.TUr,
            self.dg,
            self.Zr,
            self.TUsat,
            self.config.calibration_parameters.beta,
        )
        Cper = cperCalc(
            self.TUw,
            self.dg,
            self.Zr,
            self.S,
            n_manning,
            self.config.calibration_parameters.w_1,
            self.config.calibration_parameters.w_2,
            self.config.calibration_parameters.w_3,
        )
        Aimp, Cimp = cimpCalc(Ao, Ai)
        Cwp = cwpCalc(Aimp, Cper, Cimp)
        Csr = csrCalc(Cwp, Pdm, self.config.calibration_parameters.rcd)

        self.ES = sRunoffCalc(
            Csr,
            Ch,
            precipitation,
            self.Itp,
            Ao,
            self.ET_ao,
            self.TUr,
            self.TUsat,
        )

        self.logger.debug("Lateral Flow")

        self.LF = lfCalc(
            self.config.calibration_parameters.f,
            self.Kr,
            self.TUr,
            self.TUsat,
        )

        self.logger.debug("Recharge Flow")

        self.REC = recCalc(
            self.config.calibration_parameters.f,
            self.Kr,
            self.TUr,
            self.TUsat,
        )

        self.logger.debug("Baseflow")

        self.EB = baseflowCalc(
            self.EBprev,
            self.config.calibration_parameters.alpha_gw,
            self.REC,
            self.TUs,
            self.EB_lim,
        )
        self.EBprev = self.EB

        self.logger.debug("Soil Balance")
        self.TUr = turCalc(
            self.TUrprev,
            precipitation,
            self.Itp,
            self.ES,
            self.LF,
            self.REC,
            self.ETr,
            Ao,
            self.TUsat,
        )
        self.TUs = tusCalc(self.TUsprev, self.REC, self.EB)
        self.TUrprev = self.TUr

        self.TUsprev = self.TUs

        self.logger.debug("Runoff")

        days = daysOfMonth(self.config.simulation_period.start_date, t)
        c = days * 24 * 3600

        self.Qtot = self.ES + self.LF + self.EB  # [mm]
        self.Qtotvol = self.Qtot * self.A * 0.001 / c  # [m3/s]

        self.Qt = pcrfw.accuflux(self.ldd, self.Qtotvol)

        self.runoff = (
            self.config.calibration_parameters.x * self.Qprev
            + (1 - self.config.calibration_parameters.x) * self.Qt
        )
        self.Qprev = self.runoff

        os.chdir(self.config.output_directory.path)
        self.logger.debug("Exporting variables to files")

        self.__stepReport()
