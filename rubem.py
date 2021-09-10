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
# Contact: rubem.hydrological@labsid.eng.br

"""Rainfall rUnoff Balance Enhanced Model."""

__author__ = "LabSid PHA EPUSP"
__email__ = "rubem.hydrological@labsid.eng.br"
__copyright__ = "Copyright 2020-2021, LabSid PHA EPUSP"
__license__ = "GPL"
__date__ = "2021-05-19"
__version__ = "0.1.0"

import argparse
import configparser
import os
import time

import numpy as np
import pcraster as pcr
import pcraster.framework as pcrfw

# Importing rainfall runoff model functions
from modules.evapotranspiration import *
from modules.interception import *
from modules.soil import *
from modules.surface_runoff import *

# Import util functions
from utilities.date_calc import *
from utilities.file_convertions import tss2csv
from utilities.file_generators import *


class RUBEM(pcrfw.DynamicModel):
    """Rainfall rUnoff Balance Enhanced Model.

    Uses the PCRaster Dynamic Modelling Framework.
    """

    def __init__(self):
        """Contains the initialization of the model class."""
        pcrfw.DynamicModel.__init__(self)
        print("RUBEM::Reading input files...", end=" ", flush=True)

        # TODO: Check if loaded config info is valid
        # Read file locations
        self.inpath = config.get("DIRECTORIES", "input")
        self.outpath = config.get("DIRECTORIES", "output")
        self.etp_path = config.get("DIRECTORIES", "etp")
        self.prec_path = config.get("DIRECTORIES", "prec")
        self.kp_path = config.get("DIRECTORIES", "Kp")
        self.ndvi_path = config.get("DIRECTORIES", "ndvi")
        self.land_path = config.get("DIRECTORIES", "landuse")

        # Read temporal filenames prefix
        self.etpPrefix = config.get("FILENAME_PREFIXES", "etp_prefix")
        self.precPrefix = config.get("FILENAME_PREFIXES", "prec_prefix")
        self.ndviPrefix = config.get("FILENAME_PREFIXES", "ndvi_prefix")
        self.kpPrefix = config.get("FILENAME_PREFIXES", "kp_prefix")
        self.coverPrefix = config.get("FILENAME_PREFIXES", "landuse_prefix")

        self.dem_file = config.get("RASTERS", "dem")
        self.demTif = config.get("RASTERS", "demtif")
        self.clone_file = config.get("RASTERS", "clone")
        # self.ldd_file = config.get('RASTERS', 'lddTif')
        self.soil_path = config.get("RASTERS", "soil")
        self.sampleLocs = config.get("RASTERS", "samples")
        self.ndviMaxFile = config.get("RASTERS", "ndvi_max")
        self.ndviMinFile = config.get("RASTERS", "ndvi_min")

        # Set clone
        pcr.setclone(self.clone_file)

        # Read text lookuptables from config file
        self.rainyDaysTable = config.get("TABLES", "rainydays")
        self.aiTable = config.get("TABLES", "a_i")
        self.aoTable = config.get("TABLES", "a_o")
        self.asTable = config.get("TABLES", "a_s")
        self.avTable = config.get("TABLES", "a_v")
        self.manningTable = config.get("TABLES", "manning")
        self.dgTable = config.get("TABLES", "bulk_density")
        self.KrTable = config.get("TABLES", "K_sat")
        self.TccTable = config.get("TABLES", "T_fcap")
        self.TsatTable = config.get("TABLES", "T_sat")
        self.TwTable = config.get("TABLES", "T_wp")
        self.ZrTable = config.get("TABLES", "rootzone_depth")
        self.KcminTable = config.get("TABLES", "K_c_min")
        self.KcmaxTable = config.get("TABLES", "K_c_max")

        # TODO: Automatic calculation of cell area
        # Cell area
        self.A = config.getfloat("GRID", "grid") ** 2

        # Read calibration parameters from config file
        self.alfa = config.getfloat("CALIBRATION", "alpha")
        self.b = config.getfloat("CALIBRATION", "b")
        self.w1 = config.getfloat("CALIBRATION", "w_1")
        self.w2 = config.getfloat("CALIBRATION", "w_2")
        self.w3 = config.getfloat("CALIBRATION", "w_3")
        self.RCD = config.getfloat("CALIBRATION", "rcd")
        self.f = config.getfloat("CALIBRATION", "f")
        self.alfa_gw = config.getfloat("CALIBRATION", "alpha_gw")
        self.x = config.getfloat("CALIBRATION", "x")

        # Read soil conditions from config file
        # Initial moisture content of the root zone (fraction of saturation content)
        self.ftur_ini = config.getfloat("INITIAL_SOIL_CONDITIONS", "T_ini")
        # Initial baseflow
        self.EBini = pcrfw.scalar(config.getfloat("INITIAL_SOIL_CONDITIONS", "bfw_ini"))
        # limit for baseflow
        self.EBlim = pcrfw.scalar(config.getfloat("INITIAL_SOIL_CONDITIONS", "bfw_lim"))
        # Initial moisture content of the saturated zone
        self.Tusini = pcrfw.scalar(
            config.getfloat("INITIAL_SOIL_CONDITIONS", "S_sat_ini")
        )

        # Constants
        self.fpar_max = config.getfloat("CONSTANTS", "fpar_max")
        self.fpar_min = config.getfloat("CONSTANTS", "fpar_min")
        self.lai_max = config.getfloat("CONSTANTS", "lai_max")
        self.I_i = config.getfloat("CONSTANTS", "i_imp")

        print("OK", flush=True)  # RUBEM::Reading input files...

        # # Initialize time series output
        self.OutTssRun = "tss_rnf"
        # self.OutTssPrec =   "tssPrec"
        self.OutTssInt = "tss_itp"
        self.OutTssBflow = "tss_bfw"
        self.OutTssSfRun = "tss_srn"
        self.OutTssEta = "tss_eta"
        self.OutTssLf = "tss_lfw"
        self.OutTssRec = "tss_rec"
        self.OutTssSsat = "tss_smc"

        # Report file
        # name
        self.timeStamp = str(time.strftime("%Y%m%d_%H%M%S", time.localtime(t1)))
        # header
        self.t_round = str(time.strftime("%Y %m %d %H:%M:%S", time.localtime(t1)))

        # Get Tif file Reference
        self.ref = getRefInfo(self, self.demTif)

    def initial(self):
        """Contains the initialization of variables used in the model.

        Contains operations to initialise the state of the model at time step 0.
        Operations included in this section are executed once.
        """
        # Read DEM file
        self.dem = pcrfw.readmap(self.dem_file)

        # Generate the local drain direction map on basis of the elevation map
        self.ldd = pcrfw.lddcreate(self.dem, 1e31, 1e31, 1e31, 1e31)
        # self.ldd = pcr.ldd(readmap(self.ldd_file))

        # Create slope map based on DEM
        self.S = pcrfw.slope(self.dem)

        # Create outflow points map based on ldd
        self.pits = pcrfw.pit(self.ldd)

        # Creat cacthment area basins
        subbasins = pcrfw.catchment(self.ldd, self.pits)

        if genTss:
            # Initialize Tss report at sample locations or pits
            self.TssFileRun = pcrfw.TimeoutputTimeseries(
                self.OutTssRun, self, self.sampleLocs, noHeader=True
            )
            # self.TssFilePrec = pcrfw.TimeoutputTimeseries(
            #     self.OutTssPrec, self, self.sampleLocs, noHeader=True
            # )
            self.TssFileInt = pcrfw.TimeoutputTimeseries(
                self.OutTssInt, self, self.sampleLocs, noHeader=True
            )
            self.TssFileBflow = pcrfw.TimeoutputTimeseries(
                self.OutTssBflow, self, self.sampleLocs, noHeader=True
            )
            self.TssFileSfRun = pcrfw.TimeoutputTimeseries(
                self.OutTssSfRun, self, self.sampleLocs, noHeader=True
            )
            self.TssFileEta = pcrfw.TimeoutputTimeseries(
                self.OutTssEta, self, self.sampleLocs, noHeader=True
            )
            self.TssFileLf = pcrfw.TimeoutputTimeseries(
                self.OutTssLf, self, self.sampleLocs, noHeader=True
            )
            self.TssFileRec = pcrfw.TimeoutputTimeseries(
                self.OutTssRec, self, self.sampleLocs, noHeader=True
            )
            self.TssFileSsat = pcrfw.TimeoutputTimeseries(
                self.OutTssSsat, self, self.sampleLocs, noHeader=True
            )

        # Read min and max ndvi
        self.ndvi_min = pcrfw.scalar(pcrfw.readmap(self.ndviMinFile))
        self.ndvi_max = pcrfw.scalar(pcrfw.readmap(self.ndviMaxFile))

        # Compute min and max sr
        self.sr_min = sr_calc(self, pcr, self.ndvi_min)
        self.sr_max = sr_calc(self, pcr, self.ndvi_max)

        # Read soil attributes
        solo = pcrfw.readmap(self.soil_path)
        self.Kr = pcrfw.lookupscalar(
            self.KrTable, solo
        )  # hydraulic conductivity coefficient
        self.dg = pcrfw.lookupscalar(self.dgTable, solo)  # soil density
        self.Zr = pcrfw.lookupscalar(self.ZrTable, solo)  # root zone depth [cm]
        self.TUsat = (
            pcrfw.lookupscalar(self.TsatTable, solo) * self.dg * self.Zr * 10
        )  # moisture for saturation of the first layer [mm]
        self.TUr_ini = (self.TUsat) * (
            self.ftur_ini
        )  # initial moisture content of the root zone [mm]
        self.TUw = (
            pcrfw.lookupscalar(self.TwTable, solo) * self.dg * self.Zr * 10
        )  # ground wilting point [mm]
        self.TUcc = (
            pcrfw.lookupscalar(self.TccTable, solo) * self.dg * self.Zr * 10
        )  # field capacity [mm]
        self.EB_ini = self.EBini  # initial baseflow [mm]
        self.EB_lim = self.EBlim  # limit for baseflow condition [mm]
        self.TUs_ini = (
            self.Tusini
        )  # initial moisture content of the saturated layer [mm]

        # steps
        self.steps = totalSteps(startDate, endDate)
        self.lastStep = steps[1]

        # Conditions for t = first loop
        self.TUrprev = self.TUr_ini
        self.TUsprev = self.TUs_ini
        self.EBprev = self.EB_ini
        self.TUr = self.TUr_ini
        self.TUs = self.TUs_ini
        self.EB = self.EB_ini
        self.Qini = pcrfw.scalar(0)
        self.Qprev = self.Qini

        if genTss:
            # Information for output, get sample location numbers - integer, from 1 to n
            sample_map = pcrfw.nominal(
                self.sampleLocs
            )  # read sample map location as nominal
            self.mvalue = -999
            # Convert sample location to multidimensional array
            self.sample_array = pcrfw.pcr2numpy(sample_map, self.mvalue)
            # create 1d array with unique locations values (1 to N number os locations)
            self.sample_vals = np.asarray(np.unique(self.sample_array))

    def dynamic(self):
        """Contains the implementation of the dynamic section of the model.

        Contains the operations that are executed consecutively each time step.
        Results of a previous time step can be used as input for the current time step.
        The dynamic section is executed a specified number of timesteps.
        """
        t = self.currentStep
        print(f"Time: {t}", flush=True)

        # Read NDVI
        try:
            NDVI = self.readmap(self.ndvi_path + self.ndviPrefix)
            self.ndvi_ant = NDVI

        except RuntimeError:
            NDVI = self.ndvi_ant

        # Read Landuse Maps
        try:
            self.landuse = self.readmap(self.land_path + self.coverPrefix)
            self.landuse_ant = self.landuse

        except RuntimeError:
            self.landuse = self.landuse_ant

        # Read precipitation maps
        precipitation = pcr.scalar(self.readmap(self.prec_path + self.precPrefix))

        # Read potential evapotranspiration
        ETp = pcr.scalar(self.readmap(self.etp_path + self.etpPrefix))

        # Read Kp
        Kp = pcr.scalar(self.readmap(self.kp_path + self.kpPrefix))

        # Number of rainy days
        month = ((t - 1) % 12) + 1
        rainyDays = pcrfw.lookupscalar(self.rainyDaysTable, month)

        # Read Landuse attributes
        n_manning = pcrfw.lookupscalar(self.manningTable, self.landuse)
        Av = pcrfw.lookupscalar(self.avTable, self.landuse)
        Ao = pcrfw.lookupscalar(self.aoTable, self.landuse)
        As = pcrfw.lookupscalar(self.asTable, self.landuse)
        Ai = pcrfw.lookupscalar(self.aiTable, self.landuse)
        self.kc_min = pcrfw.lookupscalar(self.KcminTable, self.landuse)
        self.kc_max = pcrfw.lookupscalar(self.KcmaxTable, self.landuse)

        print("\tInterception...", end=" ", flush=True)
        ######### compute interception #########
        SR = sr_calc(self, pcr, NDVI)
        FPAR = fpar_calc(
            self, pcr, self.fpar_min, self.fpar_max, SR, self.sr_min, self.sr_max
        )
        LAI = lai_function(self, pcr, FPAR, self.fpar_max, self.lai_max)
        Id, Ir, Iv, I = Interception_function(
            self, pcr, self.alfa, LAI, precipitation, rainyDays, Av
        )

        print("OK", flush=True)  # print("\tInterception... OK", flush=True)

        ######### Compute Evapotranspiration #########
        print("\tEvapotranspiration...", end=" ", flush=True)

        Kc_1 = kc_calc(
            self, pcr, NDVI, self.ndvi_min, self.ndvi_max, self.kc_min, self.kc_max
        )
        # condicao do kc, se NDVI < 1.1NDVI_min, kc = kc_min
        kc_cond1 = pcrfw.scalar(NDVI < 1.1 * self.ndvi_min)
        kc_cond2 = pcrfw.scalar(NDVI > 1.1 * self.ndvi_min)
        Kc = pcr.scalar((kc_cond2 * Kc_1) + (kc_cond1 * self.kc_min))
        Ks = pcr.scalar(Ks_calc(self, pcr, self.TUr, self.TUw, self.TUcc))

        # Vegetated area
        self.ET_av = ETav_calc(self, pcr, ETp, Kc, Ks)

        # Impervious area
        # ET impervious area = Interception of impervious area
        # condicao leva em conta a chuva igual a zero
        # mascara: chuva = 0 -> 0, chuva <> 0 -> 1
        cond = pcr.scalar((precipitation != 0))
        self.ET_ai = self.I_i * cond

        # Open water
        self.ET_ao = ETao_calc(self, pcr, ETp, Kp, precipitation, Ao)
        # self.report(ET_ao,self.outpath+'ETao')

        # Bare soil
        self.ET_as = ETas_calc(self, pcr, ETp, self.kc_min, Ks)
        self.ETr = (
            (Av * self.ET_av)
            + (Ai * self.ET_ai)
            + (Ao * self.ET_ao)
            + (As * self.ET_as)
        )

        print("OK", flush=True)  # print("\tEvapotranspiration... OK", flush=True)

        ######### Surface Runoff #########
        print("\tSurface Runoff...", end=" ", flush=True)

        Pdm = precipitation / rainyDays
        Ch = Ch_calc(self, pcr, self.TUr, self.dg, self.Zr, self.TUsat, self.b)
        Cper = Cper_calc(
            self,
            pcr,
            self.TUw,
            self.dg,
            self.Zr,
            self.S,
            n_manning,
            self.w1,
            self.w2,
            self.w3,
        )
        Aimp, Cimp = Cimp_calc(self, pcr, Ao, Ai)
        Cwp = Cwp_calc(self, pcr, Aimp, Cper, Cimp)
        Csr = Csr_calc(self, pcr, Cwp, Pdm, self.RCD)

        self.ES = ES_calc(
            self, pcr, Csr, Ch, precipitation, I, Ao, self.ET_ao, self.TUr, self.TUsat
        )

        print("OK", flush=True)  # print("\tSurface Runoff... OK", flush=True)

        ######### Lateral Flow #########
        print("\tLateral Flow...", end=" ", flush=True)

        self.LF = LF_calc(self, pcr, self.f, self.Kr, self.TUr, self.TUsat)

        print("OK", flush=True)  # print("\tLateral Flow... OK", flush=True)

        ######### Recharge Flow #########
        print("\tRecharge Flow...", end=" ", flush=True)

        self.REC = REC_calc(self, pcr, self.f, self.Kr, self.TUr, self.TUsat)

        print("OK", flush=True)  # print("\tRecharge Flow... OK", flush=True)

        ######### Baseflow #########
        print("\tBaseflow...", end=" ", flush=True)
        # reportTif(self, self.ref, self.EBprev, 'EBprev', self.outpath, dyn=True)
        # reportTif(self, self.ref, self.TUs, 'TUs2', self.outpath, dyn=True)

        self.EB = EB_calc(
            self, pcr, self.EBprev, self.alfa_gw, self.REC, self.TUs, self.EB_lim
        )
        self.EBprev = self.EB
        # reportTif(self, self.ref, self.EB, 'EB', self.outpath, dyn=True)

        print("OK", flush=True)  # print("\tBaseflow... OK", flush=True)

        ######### Soil Balance #########
        print("\tSoil Balance...", end=" ", flush=True)
        self.TUr = TUr_calc(
            self,
            pcr,
            self.TUrprev,
            precipitation,
            I,
            self.ES,
            self.LF,
            self.REC,
            self.ETr,
            Ao,
            self.TUsat,
        )
        self.TUs = TUs_calc(self, pcr, self.TUsprev, self.REC, self.EB)
        self.TUrprev = self.TUr

        self.TUsprev = self.TUs

        print("OK", flush=True)  # print("\tSoil Balance... OK", flush=True)

        ######### Compute Runoff ########
        print("\tRunoff...", end=" ", flush=True)

        days = daysOfMonth(startDate, t)
        c = days * 24 * 3600

        self.Qtot = self.ES + self.LF + self.EB  # [mm]
        self.Qtotvol = self.Qtot * self.A * 0.001 / c  # [m3/s]

        self.Qt = pcrfw.accuflux(self.ldd, self.Qtotvol)

        self.runoff = self.x * self.Qprev + (1 - self.x) * self.Qt
        self.Qprev = self.runoff

        print("OK", flush=True)  # print("\tRunoff... OK", flush=True)

        os.chdir(self.outpath)
        print("Exporting variables to files...", end=" ", flush=True)
        # Create tss files
        if genTss:
            # Function dictionary to export tss according to filename
            genTssDic = {
                "itp": self.TssFileInt.sample,
                "bfw": self.TssFileBflow.sample,
                "srn": self.TssFileSfRun.sample,
                "eta": self.TssFileEta.sample,
                "lfw": self.TssFileLf.sample,
                "rec": self.TssFileRec.sample,
                "smc": self.TssFileSsat.sample,
                "rnf": self.TssFileRun.sample,
            }

        # Variable dictionary to export according to filename
        varDic = {
            "itp": I,
            "bfw": self.EB,
            "srn": self.ES,
            "eta": self.ETr,
            "lfw": self.LF,
            "rec": self.REC,
            "smc": self.TUr,
            "rnf": self.runoff,
        }

        for fileName, isSelected in genFilesDic.items():
            # Check if the variable (fileName) has been selected for export
            if isSelected:

                # Export *.tiff raster
                if enableTIFFormat:
                    reportTif(
                        self,
                        self.ref,
                        varDic.get(fileName),
                        fileName,
                        self.outpath,
                        dyn=True,
                    )

                # Export *.map raster
                if enableMapFormat:
                    reportMapSeries(self, varDic.get(fileName), fileName)

                # Check if we have to export the time series of the selected variable (fileName)
                if genTss:
                    # Export tss according to variable (fileName) selected
                    # The same as self.TssFileXxx.sample(self.Xxx)
                    genTssDic.get(fileName)(varDic.get(fileName))

        print("OK ", flush=True)  # Exporting variables to files...

        print(f"Ending cycle {t} of {self.lastStep}", flush=True)


if __name__ == "__main__":

    # Configure CLI
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--configfile",
        type=argparse.FileType("r", encoding="utf-8"),
        help="path to configuration file",
        required=True,
    )

    args = parser.parse_args()

    t1 = time.time()
    print("RUBEM::Started", flush=True)

    print("RUBEM::Reading configuration file...", end=" ", flush=True)
    # Reading the config.ini file
    config = configparser.ConfigParser()
    config.read_file(args.configfile)
    print("OK", flush=True)  # RUBEM::Reading configuration file...

    # Make sure to close the input stream when finished
    args.configfile.close()

    # Start and end date of simulation
    startDate = config.get("SIM_TIME", "start")
    endDate = config.get("SIM_TIME", "end")

    # Check whether the output directory exists
    if not os.path.isdir(str(config.get("DIRECTORIES", "output"))):
        # If the output directory doesn't exist create it
        os.mkdir(str(config.get("DIRECTORIES", "output")))

    # Store which variables have or have not been selected for export
    genFilesList = ["itp", "bfw", "srn", "eta", "lfw", "rec", "smc", "rnf"]
    genFilesDic = {}
    for file in genFilesList:
        genFilesDic[file] = config.getboolean("GENERATE_FILE", file)

    # Store the setting that enables the export of time series
    genTss = config.getboolean("GENERATE_FILE", "tss")

    # Store the format in which the resulting files will be exported (*.tif and/or *.map)
    enableTIFFormat = config.getboolean("RASTER_FILE_FORMAT", "tiff_raster_series")
    enableMapFormat = config.getboolean("RASTER_FILE_FORMAT", "map_raster_series")

    steps = totalSteps(startDate, endDate)
    start = steps[0]
    end = steps[1]

    print("RUBEM::Running dynamic model...", flush=True)
    model = RUBEM()
    dynamicModel = pcrfw.DynamicFramework(model, lastTimeStep=end, firstTimestep=start)
    dynamicModel.run()
    tempoExec = time.time() - t1
    print(f"RUBEM::Dynamic model runtime: {tempoExec:.2f} seconds")

    # Check whether the generation of time series has been activated
    if genTss:
        print("RUBEM::Converting *.tss files to *.csv...", end=" ", flush=True)
        cols = [str(n) for n in model.sample_vals[1:]]
        # Convert generated time series to .csv format and removes .tss files
        tss2csv(model.outpath, cols)
        print("OK", flush=True)  # Converting *.tss files to *.csv...

    print("RUBEM::Finished", flush=True)
