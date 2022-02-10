# coding=utf-8
# RUBEM is a distributed hydrological model to calculate monthly
# flows with changes in land use over time.
# Copyright (C) 2020-2021 LabSid PHA EPUSP

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
import logging
from configparser import ConfigParser

import numpy as np
import pcraster as pcr
import pcraster.framework as pcrfw

# Importing rainfall runoff model functions
try:
    from modules._evapotranspiration import *
    from modules._interception import *
    from modules._soil import *
    from modules._surface_runoff import *

    # Import util functions
    from date._date_calc import *
    from file._file_generators import *
except ImportError:
    from .modules._evapotranspiration import *
    from .modules._interception import *
    from .modules._soil import *
    from .modules._surface_runoff import *

    # Import util functions
    from .date._date_calc import *
    from .file._file_generators import *


logger = logging.getLogger(__name__)


class RUBEM(pcrfw.DynamicModel):
    """Rainfall rUnoff Balance Enhanced Model.

    Uses the PCRaster Dynamic Modelling Framework.
    """

    def __init__(self, config: ConfigParser):
        """Contains the initialization of the model class."""
        pcrfw.DynamicModel.__init__(self)

        self.config = config

        # Set clone
        pcr.setclone(self.config.get("RASTERS", "clone"))

        # TODO: Automatic calculation of cell area
        # Cell area
        self.A = self.config.getfloat("GRID", "grid") ** 2

        # Initial baseflow
        self.EBini = pcrfw.scalar(
            config.getfloat("INITIAL_SOIL_CONDITIONS", "bfw_ini")
        )
        # limit for baseflow
        self.EBlim = pcrfw.scalar(
            config.getfloat("INITIAL_SOIL_CONDITIONS", "bfw_lim")
        )
        # Initial moisture content of the saturated zone
        self.Tusini = pcrfw.scalar(
            config.getfloat("INITIAL_SOIL_CONDITIONS", "S_sat_ini")
        )

        # Get Tif file Reference
        self.ref = getRefInfo(self.config.get("RASTERS", "demtif"))

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
        sample_map = pcrfw.nominal(
            self.config.get("RASTERS", "samples")
        )  # read sample map location as nominal
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
        # Read DEM file
        self.dem = pcrfw.readmap(self.config.get("RASTERS", "dem"))

        # Generate the local drain direction map on basis of the elevation map
        self.ldd = pcrfw.lddcreate(self.dem, 1e31, 1e31, 1e31, 1e31)

        # Create slope map based on DEM
        self.S = pcrfw.slope(self.dem)

        # Create tss files
        if self.config.getboolean("GENERATE_FILE", "tss"):
            self.__setupTimeoutputTimeseries()

        # Read min and max ndvi
        self.ndvi_min = pcrfw.scalar(
            pcrfw.readmap(self.config.get("RASTERS", "ndvi_min"))
        )
        self.ndvi_max = pcrfw.scalar(
            pcrfw.readmap(self.config.get("RASTERS", "ndvi_max"))
        )

        # Compute min and max sr
        self.sr_min = srCalc(self.ndvi_min)
        self.sr_max = srCalc(self.ndvi_max)

        # Read soil attributes
        solo = pcrfw.readmap(self.config.get("RASTERS", "soil"))
        self.Kr = pcrfw.lookupscalar(
            self.config.get("TABLES", "K_sat"), solo
        )  # hydraulic conductivity coefficient
        self.dg = pcrfw.lookupscalar(
            self.config.get("TABLES", "bulk_density"), solo
        )  # soil density
        self.Zr = pcrfw.lookupscalar(
            self.config.get("TABLES", "rootzone_depth"), solo
        )  # root zone depth [cm]
        self.TUsat = (
            pcrfw.lookupscalar(self.config.get("TABLES", "T_sat"), solo)
            * self.dg
            * self.Zr
            * 10
        )  # moisture for saturation of the first layer [mm]
        self.TUr_ini = (self.TUsat) * (
            self.config.getfloat("INITIAL_SOIL_CONDITIONS", "T_ini")
        )  # initial moisture content of the root zone [mm]
        self.TUw = (
            pcrfw.lookupscalar(self.config.get("TABLES", "T_wp"), solo)
            * self.dg
            * self.Zr
            * 10
        )  # ground wilting point [mm]
        self.TUcc = (
            pcrfw.lookupscalar(self.config.get("TABLES", "T_fcap"), solo)
            * self.dg
            * self.Zr
            * 10
        )  # field capacity [mm]
        self.EB_ini = self.EBini  # initial baseflow [mm]
        self.EB_lim = self.EBlim  # limit for baseflow condition [mm]
        self.TUs_ini = (
            self.Tusini
        )  # initial moisture content of the saturated layer [mm]

        # steps
        _, self.lastStep, _ = totalSteps(
            self.config.get("SIM_TIME", "start"),
            self.config.get("SIM_TIME", "end"),
        )

        # Conditions for t = first loop
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
        logger.debug(f"Time: {t}")

        # Read NDVI
        try:
            NDVI = self.readmap(
                self.config.get("DIRECTORIES", "ndvi")
                + self.config.get("FILENAME_PREFIXES", "ndvi_prefix")
            )
            self.ndvi_ant = NDVI

        except RuntimeError:
            NDVI = self.ndvi_ant

        # Read Landuse Maps
        try:
            self.landuse = self.readmap(
                self.config.get("DIRECTORIES", "landuse")
                + self.config.get("FILENAME_PREFIXES", "landuse_prefix")
            )
            self.landuse_ant = self.landuse
        except RuntimeError:
            self.landuse = self.landuse_ant

        # Read precipitation maps
        precipitation = pcr.scalar(
            self.readmap(
                self.config.get("DIRECTORIES", "prec")
                + self.config.get("FILENAME_PREFIXES", "prec_prefix")
            )
        )

        # Read potential evapotranspiration
        ETp = pcr.scalar(
            self.readmap(
                self.config.get("DIRECTORIES", "etp")
                + self.config.get("FILENAME_PREFIXES", "etp_prefix")
            )
        )

        # Read Kp
        Kp = pcr.scalar(
            self.readmap(
                self.config.get("DIRECTORIES", "Kp")
                + self.config.get("FILENAME_PREFIXES", "kp_prefix")
            )
        )

        # Number of rainy days
        month = ((t - 1) % 12) + 1
        rainyDays = pcrfw.lookupscalar(
            self.config.get("TABLES", "rainydays"), month
        )

        # Read Landuse attributes
        n_manning = pcrfw.lookupscalar(
            self.config.get("TABLES", "manning"), self.landuse
        )
        Av = pcrfw.lookupscalar(self.config.get("TABLES", "a_v"), self.landuse)
        Ao = pcrfw.lookupscalar(self.config.get("TABLES", "a_o"), self.landuse)
        As = pcrfw.lookupscalar(self.config.get("TABLES", "a_s"), self.landuse)
        Ai = pcrfw.lookupscalar(self.config.get("TABLES", "a_i"), self.landuse)
        self.kc_min = pcrfw.lookupscalar(
            self.config.get("TABLES", "K_c_min"), self.landuse
        )
        self.kc_max = pcrfw.lookupscalar(
            self.config.get("TABLES", "K_c_max"), self.landuse
        )

        logger.debug("Interception")
        SR = srCalc(NDVI)
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
            NDVI, self.ndvi_min, self.ndvi_max, self.kc_min, self.kc_max
        )
        # condicao do kc, se NDVI < 1.1NDVI_min, kc = kc_min
        kc_cond1 = pcrfw.scalar(NDVI < 1.1 * self.ndvi_min)
        kc_cond2 = pcrfw.scalar(NDVI > 1.1 * self.ndvi_min)
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
            self.config.getfloat("INITIAL_SOIL_CONDITIONS", "T_ini")
            * self.Qprev
            + (1 - self.config.getfloat("INITIAL_SOIL_CONDITIONS", "T_ini"))
            * self.Qt
        )
        self.Qprev = self.runoff

        os.chdir(self.config.get("DIRECTORIES", "output"))
        logger.debug("Exporting variables to files")

        self.__stepReport()

        logger.info(f"Cycle {t} of {self.lastStep}")
