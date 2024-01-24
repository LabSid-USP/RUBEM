# coding=utf-8
# RUBEM is a distributed hydrological model to calculate monthly
# flows with changes in land use over time.
# Copyright (C) 2020-2023 LabSid PHA EPUSP

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Contact: hydrological@labsid.eng.br

"""RUBEM as a PCRaster Dynamic Model"""

import os
import glob
import logging
from configparser import ConfigParser

import numpy as np
import pcraster as pcr
import pcraster.framework as pcrfw

from rubem.modules._evapotranspiration import *
from rubem.modules._interception import *
from rubem.modules._soil import *
from rubem.modules._surface_runoff import *
from rubem.date._date_calc import *
from rubem.file._file_generators import *

logger = logging.getLogger(__name__)


class RUBEM(pcrfw.DynamicModel):
    """Rainfall rUnoff Balance Enhanced Model.

    Uses the PCRaster Dynamic Modelling Framework.
    """

    def __init__(self, config: ConfigParser):
        """Contains the initialization of the model class."""
        pcrfw.DynamicModel.__init__(self)

        self.config = config

        logger.info("Reading clone file...")
        try:
            pcr.setclone(self.config.get("RASTERS", "clone"))
        except RuntimeError:
            logger.error("Error reading clone file at '%s'"%(self.config.get("RASTERS", "clone")))
            raise

        # TODO: Automatic calculation of cell area
        logger.info("Obtaining grid cell area...")
        self.A = self.config.getfloat("GRID", "grid") ** 2

        logger.info("Obtaining initial baseflow...")
        self.EBini = pcrfw.scalar(
            config.getfloat("INITIAL_SOIL_CONDITIONS", "bfw_ini"))
        
        logger.info("Obtaining baseflow limit...")
        self.EBlim = pcrfw.scalar(
            config.getfloat("INITIAL_SOIL_CONDITIONS", "bfw_lim"))
        
        logger.info("Obtaining initial moisture content of the saturated zone...")
        self.Tusini = pcrfw.scalar(
            config.getfloat("INITIAL_SOIL_CONDITIONS", "S_sat_ini"))

        logger.debug("Reading DEM reference file...")
        try:
            self.ref = getRefInfo(self.config.get("RASTERS", "demtif"))
        except RuntimeError:
            logger.error("Error reading Digital Elevation Model (DEM) file at '%s'"%(self.dem_file))
            raise

        self.ndvi_path = self.config.get("DIRECTORIES", "ndvi") + self.config.get("FILENAME_PREFIXES", "ndvi_prefix")
        self.landuse_path = self.config.get("DIRECTORIES", "landuse") + self.config.get("FILENAME_PREFIXES", "landuse_prefix")
        self.precipitation_path = self.config.get("DIRECTORIES", "prec") + self.config.get("FILENAME_PREFIXES", "prec_prefix")
        self.etp_path = self.config.get("DIRECTORIES", "etp") + self.config.get("FILENAME_PREFIXES", "etp_prefix")
        self.kp_path = self.config.get("DIRECTORIES", "Kp") + self.config.get("FILENAME_PREFIXES", "kp_prefix")
        
        self.__getEnabledOutputVars()

    def __getEnabledOutputVars(self):
        # Store which variables have or have not been selected for export
        availabeOutputVars = [
            "itp",
            "bfw",
            "srn",
            "eta",
            "lfw",
            "rec",
            "smc",
            "rnf",
        ]
        self.enabledOuputVars = []
        for var in availabeOutputVars:
            if self.config.getboolean("GENERATE_FILE", var):
                self.enabledOuputVars.append(var)

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

        for enabledOutpurVar in self.enabledOuputVars:
            # Export TIFF raster series
            if self.config.getboolean(
                "RASTER_FILE_FORMAT", "tiff_raster_series"
            ):
                reportTIFFSeries(
                    self,
                    self.ref,
                    self.outputVarsDict.get(enabledOutpurVar),
                    enabledOutpurVar,
                    self.config.get("DIRECTORIES", "output"),
                    self.currentStep,
                    dyn=True,
                )

            # Export PCRaster map format raster series
            if self.config.getboolean(
                "RASTER_FILE_FORMAT", "map_raster_series"
            ):
                self.report(
                    self.outputVarsDict.get(enabledOutpurVar), enabledOutpurVar
                )

            # Check if we have to export the time series of the selected
            # variable (fileName)
            if self.config.getboolean("GENERATE_FILE", "tss"):
                # Export tss according to variable (fileName) selected
                # The same as self.TssFileXxx.sample(self.Xxx)
                self.sampleTimeSeriesDict.get(enabledOutpurVar)(
                    self.outputVarsDict.get(enabledOutpurVar)
                )

    def __setupTimeoutputTimeseries(self):
        
        # read sample map location as nominal
        try:
            sample_map = pcrfw.nominal(self.config.get("RASTERS", "samples")) 
        except RuntimeError:
            logger.error("Error reading sample map file at '%s'"%(self.config.get("RASTERS", "samples")))
            raise
        
        # Initialize Tss report at sample locations or pits
        self.TssFileRun = pcrfw.TimeoutputTimeseries(
            "tss_rnf",
            self,
            self.config.get("RASTERS", "samples"),
            noHeader=True,
        )
        self.TssFileInt = pcrfw.TimeoutputTimeseries(
            "tss_itp",
            self,
            self.config.get("RASTERS", "samples"),
            noHeader=True,
        )
        self.TssFileBflow = pcrfw.TimeoutputTimeseries(
            "tss_bfw",
            self,
            self.config.get("RASTERS", "samples"),
            noHeader=True,
        )
        self.TssFileSfRun = pcrfw.TimeoutputTimeseries(
            "tss_srn",
            self,
            self.config.get("RASTERS", "samples"),
            noHeader=True,
        )
        self.TssFileEta = pcrfw.TimeoutputTimeseries(
            "tss_eta",
            self,
            self.config.get("RASTERS", "samples"),
            noHeader=True,
        )
        self.TssFileLf = pcrfw.TimeoutputTimeseries(
            "tss_lfw",
            self,
            self.config.get("RASTERS", "samples"),
            noHeader=True,
        )
        self.TssFileRec = pcrfw.TimeoutputTimeseries(
            "tss_rec",
            self,
            self.config.get("RASTERS", "samples"),
            noHeader=True,
        )
        self.TssFileSsat = pcrfw.TimeoutputTimeseries(
            "tss_smc",
            self,
            self.config.get("RASTERS", "samples"),
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
        
        logger.info("Setting up model initial parameters...")
        logger.debug("Reading DEM file...")
        # Read DEM file
        try:
            self.dem = pcrfw.readmap(self.config.get("RASTERS", "dem"))
        except RuntimeError:
            logger.error("Error reading DEM file at '%s'"%(self.config.get("RASTERS", "dem")))
            raise

        logger.info("Generating local drain direction (LDD) map based on DEM...")
        self.ldd = pcrfw.lddcreate(self.dem, 1e31, 1e31, 1e31, 1e31)

        logger.info("Creating slope map based on DEM...")
        self.S = pcrfw.slope(self.dem)

        logger.info("Setting up TSS output files...")
        if self.config.getboolean("GENERATE_FILE", "tss"):
            self.__setupTimeoutputTimeseries()

        logger.info("Reading min. and max. NDVI rasters...")
        try:
            self.ndvi_min = pcrfw.scalar(
                pcrfw.readmap(self.config.get("RASTERS", "ndvi_min")))
        except RuntimeError:
            logger.error("Error reading NDVI min file at '%s'"%(self.config.get("RASTERS", "ndvi_min")))
            raise
            
        try:            
            self.ndvi_max = pcrfw.scalar(
                pcrfw.readmap(self.config.get("RASTERS", "ndvi_max")))
        except RuntimeError:
            logger.error("Error reading NDVI max file at '%s'"%(self.config.get("RASTERS", "ndvi_max")))
            raise

        logger.info("Computing min. and max. surface runoff (SR)")
        self.sr_min = srCalc(self.ndvi_min)
        self.sr_max = srCalc(self.ndvi_max)

        logger.info("Reading soil attributes...")
        try:            
            solo = pcrfw.readmap(self.config.get("RASTERS", "soil"))
        except RuntimeError:
            logger.error("Error reading soil file at '%s'"%(self.config.get("RASTERS", "soil")))
            raise
        
        logger.info("Reading hydraulic conductivity coefficient...")
        try:            
            self.Kr = pcrfw.lookupscalar(self.config.get("TABLES", "K_sat"), solo)
        except RuntimeError:
            logger.error("Error reading K_sat file at '%s'"%(self.config.get("TABLES", "K_sat")))
            raise
        
        logger.info("Reading soil density...")
        try:            
            self.dg = pcrfw.lookupscalar(self.config.get("TABLES", "bulk_density"), solo)  
        except RuntimeError:
            logger.error("Error reading bulk_density file at '%s'"%(self.config.get("TABLES", "bulk_density")))
            raise
        
        logger.info("Reading soil root zone depth...")
        try:            
            self.Zr = pcrfw.lookupscalar(self.config.get("TABLES", "rootzone_depth"), solo)  
        except RuntimeError:
            logger.error("Error reading rootzone_depth file at '%s'"%(self.config.get("TABLES", "rootzone_depth")))
            raise
        
        logger.info("Reading soil moisture for saturation of the first layer...")
        try:            
            self.TUsat = (pcrfw.lookupscalar(self.config.get("TABLES", "T_sat"), solo) * self.dg * self.Zr * 10)  
        except RuntimeError:
            logger.error("Error reading T_sat file at '%s'"%(self.config.get("TABLES", "T_sat")))
            raise
        
        logger.info("Obtaining soil initial moisture content of the root zone...")
        try:            
            self.TUr_ini = (self.TUsat) * (self.config.getfloat("INITIAL_SOIL_CONDITIONS", "T_ini"))  
        except RuntimeError:
            logger.error("Error reading T_ini file at '%s'"%(self.config.get("INITIAL_SOIL_CONDITIONS", "T_ini")))
            raise
        
        logger.info("Reading soil ground wilting point...")
        try:            
            self.TUw = (pcrfw.lookupscalar(self.config.get("TABLES", "T_wp"), solo) * self.dg * self.Zr * 10)  
        except RuntimeError:
            logger.error("Error reading T_wp file at '%s'"%(self.config.get("TABLES", "T_wp")))
            raise
        
        logger.info("Reading soil field capacity...")
        try:            
            self.TUcc = (pcrfw.lookupscalar(self.config.get("TABLES", "T_fcap"), solo) * self.dg * self.Zr * 10)  
        except RuntimeError:
            logger.error("Error reading T_fcap file at '%s'"%(self.config.get("TABLES", "T_fcap")))
            raise
        
        self.EB_ini = self.EBini  # initial baseflow [mm]
        self.EB_lim = self.EBlim  # limit for baseflow condition [mm]
        self.TUs_ini = self.Tusini  # initial moisture content of the saturated layer [mm]

        # steps
        _, self.lastStep, _ = totalSteps(self.config.get("SIM_TIME", "start"), self.config.get("SIM_TIME", "end"))

        logger.info("Establishing initial conditions...")
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
        logger.info(f"Cycle {t} of {self.lastStep}")
        print(f"## Timestep {t} of {self.lastStep}")

        logger.debug("Reading NDVI map from '%s'...", self.ndvi_path)
        try:
            ndvi = self.readmap(self.ndvi_path)
            self.ndvi_ant = ndvi
        except RuntimeError:
            logger.warning("Error reading NDVI map from '%s'. Using previous timestep value...", self.ndvi_path)
            ndvi = self.ndvi_ant

        logger.debug("Reading landuse map from '%s'...", self.landuse_path)
        try:
            self.landuse = self.readmap(self.landuse_path)
            self.landuse_ant = self.landuse
        except RuntimeError:
            logger.warning("Error reading landuse map from '%s'. Using previous timestep value...", self.landuse_path)
            self.landuse = self.landuse_ant

        logger.debug("Reading precipitation map from '%s'...", self.precipitation_path)
        try:
            precipitation = pcr.scalar(self.readmap(self.precipitation_path))
        except RuntimeError:
            logger.error("Error reading precipitation map from '%s'", self.precipitation_path)
            raise

        logger.debug("Reading potential evapotranspiration map from '%s'...", self.etp_path)
        try:
            ETp = pcr.scalar(self.readmap(self.etp_path))
        except RuntimeError:
            logger.error("Error reading potential evapotranspiration map from '%s'", self.etp_path)
            raise

        logger.debug("Reading Kp map from '%s'...", self.kp_path)
        try:    
            Kp = pcr.scalar(self.readmap(self.kp_path))
        except RuntimeError:
            logger.error("Error reading Kp map from '%s'", self.kp_path)
            raise

        logger.debug("Reading rainydays file from '%s'...", self.config.get("TABLES", "rainydays"))
        try:
            month = ((t - 1) % 12) + 1
            rainyDays = pcrfw.lookupscalar(self.config.get("TABLES", "rainydays"), month)
        except RuntimeError:
            logger.error("Error reading rainydays file at '%s'", self.config.get("TABLES", "rainydays"))
            raise

        logger.debug("Reading landuse attributes: manning...")
        try:
            n_manning = pcrfw.lookupscalar(self.config.get("TABLES", "manning"), self.landuse)
        except RuntimeError:
            logger.error("Error reading manning file at '%s'", self.config.get("TABLES", "manning"))
            raise
        
        logger.debug("Reading landuse attributes: a_v...")        
        try:
            Av = pcrfw.lookupscalar(self.config.get("TABLES", "a_v"), self.landuse)
        except RuntimeError:
            logger.error("Error reading a_v file at '%s'", self.config.get("TABLES", "a_v"))
            raise

        logger.debug("Reading landuse attributes: a_o...")        
        try:
            Ao = pcrfw.lookupscalar(self.config.get("TABLES", "a_o"), self.landuse)
        except RuntimeError:
            logger.error("Error reading a_o file at '%s'", self.config.get("TABLES", "a_o"))
            raise

        logger.debug("Reading landuse attributes: a_s...")        
        try:
            As = pcrfw.lookupscalar(self.config.get("TABLES", "a_s"), self.landuse)
        except RuntimeError:
            logger.error("Error reading a_s file at '%s'", self.config.get("TABLES", "a_s"))
            raise

        logger.debug("Reading landuse attributes: a_i...")            
        try:
            Ai = pcrfw.lookupscalar(self.config.get("TABLES", "a_i"), self.landuse)
        except RuntimeError:
            logger.error("Error reading a_i file at '%s'", self.config.get("TABLES", "a_i"))
            raise

        logger.debug("Reading landuse attributes: K_c_min...")            
        try:
            self.kc_min = pcrfw.lookupscalar(self.config.get("TABLES", "K_c_min"), self.landuse)
        except RuntimeError:
            logger.error("Error reading K_c_min file at '%s'", self.config.get("TABLES", "K_c_min"))
            raise

        logger.debug("Reading landuse attributes: K_c_max...")            
        try:
            self.kc_max = pcrfw.lookupscalar(self.config.get("TABLES", "K_c_max"), self.landuse)
        except RuntimeError:
            logger.error("Error reading K_c_max file at '%s'", self.config.get("TABLES", "K_c_max"))
            raise

        logger.debug("Interception")
        SR = srCalc(ndvi)
        FPAR = fparCalc(
            self.config.getfloat("CONSTANTS", "fpar_min"),
            self.config.getfloat("CONSTANTS", "fpar_max"),
            SR,
            self.sr_min,
            self.sr_max,
        )
        LAI = laiCalc(
            FPAR,
            self.config.getfloat("CONSTANTS", "fpar_max"),
            self.config.getfloat("CONSTANTS", "lai_max"),
        )
        Id, Ir, Iv, self.Itp = interceptionCalc(
            self.config.getfloat("CALIBRATION", "alpha"),
            LAI,
            precipitation,
            rainyDays,
            Av,
        )

        logger.debug("Evapotranspiration")

        Kc_1 = kcCalc(
            ndvi, self.ndvi_min, self.ndvi_max, self.kc_min, self.kc_max
        )
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
        self.ET_ai = self.config.getfloat("CONSTANTS", "i_imp") * cond

        # Open water
        self.ET_ao = etaoCalc(ETp, Kp, precipitation, Ao)
        # self.report(ET_ao,self.config.get("DIRECTORIES", "output")+'ETao')

        # Bare soil
        self.ET_as = etasCalc(ETp, self.kc_min, Ks)
        self.ETr = (
            (Av * self.ET_av)
            + (Ai * self.ET_ai)
            + (Ao * self.ET_ao)
            + (As * self.ET_as)
        )

        logger.debug("Surface Runoff")

        Pdm = precipitation / rainyDays
        Ch = chCalc(
            self.TUr,
            self.dg,
            self.Zr,
            self.TUsat,
            self.config.getfloat("CALIBRATION", "b"),
        )
        Cper = cperCalc(
            self.TUw,
            self.dg,
            self.Zr,
            self.S,
            n_manning,
            self.config.getfloat("CALIBRATION", "w_1"),
            self.config.getfloat("CALIBRATION", "w_2"),
            self.config.getfloat("CALIBRATION", "w_3"),
        )
        Aimp, Cimp = cimpCalc(Ao, Ai)
        Cwp = cwpCalc(Aimp, Cper, Cimp)
        Csr = csrCalc(Cwp, Pdm, self.config.getfloat("CALIBRATION", "rcd"))

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

        logger.debug("Lateral Flow")

        self.LF = lfCalc(
            self.config.getfloat("CALIBRATION", "f"),
            self.Kr,
            self.TUr,
            self.TUsat,
        )

        logger.debug("Recharge Flow")

        self.REC = recCalc(
            self.config.getfloat("CALIBRATION", "f"),
            self.Kr,
            self.TUr,
            self.TUsat,
        )

        logger.debug("Baseflow")

        self.EB = baseflowCalc(
            self.EBprev,
            self.config.getfloat("CALIBRATION", "alpha_gw"),
            self.REC,
            self.TUs,
            self.EB_lim,
        )
        self.EBprev = self.EB

        logger.debug("Soil Balance")
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

        logger.debug("Runoff")

        days = daysOfMonth(self.config.get("SIM_TIME", "start"), t)
        c = days * 24 * 3600

        self.Qtot = self.ES + self.LF + self.EB  # [mm]
        self.Qtotvol = self.Qtot * self.A * 0.001 / c  # [m3/s]

        self.Qt = pcrfw.accuflux(self.ldd, self.Qtotvol)

        self.runoff = (
            self.config.getfloat("CALIBRATION", "x")
            * self.Qprev
            + (1 - self.config.getfloat("CALIBRATION", "x"))
            * self.Qt
        )
        self.Qprev = self.runoff

        os.chdir(self.config.get("DIRECTORIES", "output"))
        logger.debug("Exporting variables to files")

        self.__stepReport()
