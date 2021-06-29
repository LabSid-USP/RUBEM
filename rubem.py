# coding=utf-8
# RUBEM RUBEM is a distributed hydrological model to calculate monthly 
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

__author__ = 'LabSid PHA EPUSP'
__email__ = "rubem.hydrological@labsid.eng.br"
__copyright__ = 'Copyright 2020-2021, LabSid PHA EPUSP'
__license__ = "GPL"
__date__ = '2021-05-19'
__version__ = "0.1.0"

import os
import time
import configparser
import argparse

import numpy as np
import pcraster.framework as pcrfw
import pcraster as pcr

# Importing rainfall runoff model functions
from modules.interception import *
from modules.evapotranspiration import *
from modules.surface_runoff import *
from modules.soil import *

from utilities.file_convertions import tss2csv
from utilities.file_generators import *
from utilities.date_calc import *
 
########## Dynamic Model ##########
class Modelo(pcrfw.DynamicModel):
    """Constructor"""
    def __init__(self):
        pcrfw.DynamicModel.__init__(self)
        print("RUBEM::Reading input files...", end=" ", flush=True)
        
        #TODO: Check if loaded config info is valid
        # Read file locations
        self.inpath = config.get('FILES', 'input')
        self.dem_file = config.get('FILES', 'dem')
        self.demTif = config.get('FILES', 'demtif')
        self.clone_file = config.get('FILES', 'clone')
        # self.ldd_file = config.get('FILES', 'lddTif')
        self.etp_path = config.get('FILES', 'etp')
        self.prec_path = config.get('FILES', 'prec')
        self.ndvi_path = config.get('FILES', 'ndvi')
        self.kp_path = config.get('FILES', 'kp')
        self.land_path = config.get('FILES', 'landuse')
        self.soil_path = config.get('FILES', 'solo')
        self.outpath = config.get('FILES', 'output')
        self.sampleLocs = config.get('FILES', 'samples')

        # Set clone
        pcr.setclone(self.clone_file)

        # Read temporal filenames prefix
        self.etpPrefix = config.get('FILES', 'etpFilePrefix')
        self.precPrefix = config.get('FILES', 'precFilePrefix')
        self.ndviPrefix = config.get('FILES', 'ndviFilePrefix')  
        self.ndviMaxFile = config.get('FILES', 'ndvimax') 
        self.ndviMinFile = config.get('FILES', 'ndvimin') 
        self.kpPrefix = config.get('FILES', 'kpFilePrefix')
        self.coverPrefix = config.get('FILES', 'landuseFilePrefix')

        # Read text lookuptables from config file
        self.rainyDaysTable = config.get('PARAMETERS', 'rainydays')
        self.aiTable = config.get('PARAMETERS', 'a_i')
        self.aoTable = config.get('PARAMETERS', 'a_o')
        self.asTable = config.get('PARAMETERS', 'a_s')
        self.avTable = config.get('PARAMETERS', 'a_v')
        self.manningTable = config.get('PARAMETERS', 'manning')
        self.dgTable = config.get('PARAMETERS', 'dg')
        self.KrTable = config.get('PARAMETERS', 'kr')
        self.TccTable = config.get('PARAMETERS', 'capCampo')
        self.Tporosidade = config.get('PARAMETERS', 'porosidade')
        self.TsatTable = config.get('PARAMETERS', 'saturacao')
        self.TwTable = config.get('PARAMETERS', 'pontomurcha')
        self.ZrTable = config.get('PARAMETERS', 'zr')
        self.KcminTable = config.get('PARAMETERS', 'kcmin')
        self.KcmaxTable = config.get('PARAMETERS', 'kcmax')

        #TODO: Automatic calculation of cell area
        # Cell area 
        self.A = config.getfloat('GRID', 'grid')

        # Read calibration parameters from config file
        self.alfa = config.getfloat('CALIBRATION', 'alfa')
        self.b = config.getfloat('CALIBRATION', 'b')
        self.w1 = config.getfloat('CALIBRATION', 'w1')
        self.w2 = config.getfloat('CALIBRATION', 'w2')
        self.w3 = config.getfloat('CALIBRATION', 'w3')
        self.RCD = config.getfloat('CALIBRATION', 'rcd')
        self.f = config.getfloat('CALIBRATION', 'f')
        self.alfa_gw = config.getfloat('CALIBRATION', 'alfa_gw')
        self.x = config.getfloat('CALIBRATION', 'x')

        # Read soil conditions from config file
        # Initial moisture content of the root zone (fraction of saturation content)
        self.ftur_ini = config.getfloat('INITIAL SOIL CONDITIONS', 'ftur_ini')
        # Initial baseflow
        self.EBini = pcrfw.scalar(config.getfloat('INITIAL SOIL CONDITIONS', 'eb_ini'))
        # limit for baseflow
        self.EBlim = pcrfw.scalar(config.getfloat('INITIAL SOIL CONDITIONS', 'eb_lim'))
        # Initial moisture content of the saturated zone
        self.Tusini = pcrfw.scalar(config.getfloat('INITIAL SOIL CONDITIONS', 'tus_ini'))

        # Constants
        self.fpar_max = config.getfloat('CONSTANT', 'fpar_max')
        self.fpar_min = config.getfloat('CONSTANT', 'fpar_min')
        self.lai_max = config.getfloat('CONSTANT', 'lai_max')
        self.I_i = config.getfloat('CONSTANT', 'i_imp')
        
        print("OK", flush=True) # RUBEM::Reading input files...

        # # Initialize time series output
        self.OutTssRun = 'outRun'
        self.OutTssPrec = 'outPrec'
        self.OutTssInt = 'outInt'
        self.OutTssBflow =  'outBflow'
        self.OutTssSfRun = 'outSfRun'
        self.OutTssEtp = 'outEtp'
        self.OutTssLf =  'outLf'
        self.OutTssRec = 'outRec'
        self.OutTssSsat = 'outSsat'

        # Report file
        # name
        self.timeStamp = str(time.strftime("%Y%m%d_%H%M%S",time.localtime(t1)))
        # header 
        self.t_round = str(time.strftime("%Y %m %d %H:%M:%S",time.localtime(t1)))

        # Get Tif file Reference
        self.ref = getRefInfo(self, self.demTif)      
   
    def initial(self):
        """  """       
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

        # Initialize Tss report at sample locations or pits
        self.TssFileRun = pcrfw.TimeoutputTimeseries(self.OutTssRun, self, self.sampleLocs, noHeader=True)
        self.TssFilePrec = pcrfw.TimeoutputTimeseries(self.OutTssPrec, self, self.sampleLocs, noHeader=True)
        self.TssFileInt = pcrfw.TimeoutputTimeseries(self.OutTssInt, self, self.sampleLocs, noHeader=True)
        self.TssFileBflow = pcrfw.TimeoutputTimeseries(self.OutTssBflow, self, self.sampleLocs, noHeader=True)
        self.TssFileSfRun = pcrfw.TimeoutputTimeseries(self.OutTssSfRun, self, self.sampleLocs, noHeader=True)
        self.TssFileEtp = pcrfw.TimeoutputTimeseries(self.OutTssEtp, self, self.sampleLocs, noHeader=True)
        self.TssFileLf = pcrfw.TimeoutputTimeseries(self.OutTssLf, self, self.sampleLocs, noHeader=True)
        self.TssFileRec = pcrfw.TimeoutputTimeseries(self.OutTssRec, self, self.sampleLocs, noHeader=True)
        self.TssFileSsat = pcrfw.TimeoutputTimeseries(self.OutTssSsat, self, self.sampleLocs, noHeader=True)        

        # Read min and max ndvi
        self.ndvi_min = pcrfw.scalar(pcrfw.readmap(self.ndviMinFile))
        self.ndvi_max = pcrfw.scalar(pcrfw.readmap(self.ndviMaxFile))

        # Compute min and max sr
        self.sr_min = sr_calc(self, pcr,self.ndvi_min)
        self.sr_max = sr_calc(self, pcr,self.ndvi_max)

        # Read soil attributes
        solo = pcrfw.readmap(self.soil_path)
        self.Kr = pcrfw.lookupscalar(self.KrTable,solo) # hydraulic conductivity coefficient
        self.dg = pcrfw.lookupscalar(self.dgTable,solo) # soil density
        self.Zr = pcrfw.lookupscalar(self.ZrTable,solo) # root zone depth [cm]
        self.TUsat = pcrfw.lookupscalar(self.TsatTable,solo)*self.dg*self.Zr*10 # moisture for saturation of the first layer [mm]
        self.TUr_ini = (self.TUsat)*(self.ftur_ini) # initial moisture content of the root zone [mm]
        self.TUw = pcrfw.lookupscalar(self.TwTable,solo)*self.dg*self.Zr*10  # ground wilting point [mm]
        self.TUcc = pcrfw.lookupscalar(self.TccTable,solo)*self.dg*self.Zr*10 # field capacity [mm]
        self.Tpor = pcrfw.lookupscalar(self.Tporosidade,solo) # porosity [%]
        self.EB_ini = self.EBini # initial baseflow [mm]
        self.EB_lim = self.EBlim # limit for baseflow condition [mm]
        self.TUs_ini = self.Tusini # initial moisture content of the saturated layer [mm]

        # steps
        self.steps = totalSteps(startDate,endDate)
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

        # initialize first landuse map
        self.landuse = self.readmap(self.land_path + self.coverPrefix)
        self.landuse_ant = self.landuse

        # Information for output, get sample location numbers - integer, from 1 to n
        sample_map = pcrfw.nominal(self.sampleLocs) # read sample map location as nominal
        self.mvalue = -999
        #converts sample location to multidimensional array
        self.sample_array = pcrfw.pcr2numpy(sample_map, self.mvalue) 
        # create 1d array with unique locations values (1 to N number os locations)
        self.sample_vals = np.asarray(np.unique(self.sample_array))               

    def dynamic(self):
        """  """         
        t = self.currentStep
        print(f'Time: {t}', flush=True)     

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
        month = ((t-1)%12)+1
        rainyDays = pcrfw.lookupscalar(self.rainyDaysTable, month)

        # Read Landuse attributes 
        n_manning = pcrfw.lookupscalar(self.manningTable,self.landuse)
        Av = pcrfw.lookupscalar(self.avTable,self.landuse)
        Ao = pcrfw.lookupscalar(self.aoTable,self.landuse)
        As = pcrfw.lookupscalar(self.asTable,self.landuse)
        Ai = pcrfw.lookupscalar(self.aiTable,self.landuse)
        self.kc_min = pcrfw.lookupscalar(self.KcminTable,self.landuse)
        self.kc_max = pcrfw.lookupscalar(self.KcmaxTable,self.landuse)

        print("\tInterception...", end=" ", flush=True)
        ######### compute interception #########      
        SR = sr_calc(self, pcr,NDVI)
        FPAR = fpar_calc(self, pcr, self.fpar_min, self.fpar_max, SR, self.sr_min, self.sr_max)
        LAI = lai_function(self, pcr, FPAR, self.fpar_max, self.lai_max)
        Id, Ir, Iv, I = Interception_function(self, pcr, self.alfa, LAI, precipitation, rainyDays, Av)

        print("OK", flush=True)  #print("\tInterception... OK", flush=True)
        
        ######### Compute Evapotranspiration #########
        print("\tEvapotranspiration...", end=" ", flush=True)

        Kc_1 = kc_calc(self, pcr, NDVI, self.ndvi_min, self.ndvi_max, self.kc_min, self.kc_max)
        # condicao do kc, se NDVI < 1.1NDVI_min, kc = kc_min
        kc_cond1 = pcrfw.scalar(NDVI < 1.1*self.ndvi_min)
        kc_cond2 = pcrfw.scalar(NDVI > 1.1*self.ndvi_min)
        Kc = pcr.scalar((kc_cond2*Kc_1) + (kc_cond1*self.kc_min))  
        Ks = pcr.scalar(Ks_calc(self, pcr, self.TUr, self.TUw, self.TUcc))

        # Vegetated area
        self.ET_av = ETav_calc(self, pcr, ETp, Kc, Ks)

        # Impervious area
        # ET impervious area = Interception of impervious area
        # condicao leva em conta a chuva igual a zero
        # mascara: chuva = 0 -> 0, chuva <> 0 -> 1
        cond = pcr.scalar((precipitation != 0))
        self.ET_ai = (self.I_i*cond)

        # Open water
        self.ET_ao = ETao_calc(self, pcr, ETp, Kp, precipitation, Ao)
        #self.report(ET_ao,self.outpath+'ETao')

        # Bare soil
        self.ET_as = ETas_calc(self, pcr, ETp, self.kc_min, Ks)
        self.ETr = (Av*self.ET_av) + (Ai*self.ET_ai) + (Ao*self.ET_ao) + (As*self.ET_as) 

        print("OK", flush=True)  #print("\tEvapotranspiration... OK", flush=True)

        ######### Surface Runoff #########      
        print("\tSurface Runoff...", end=" ", flush=True)
        
        Pdm = (precipitation/rainyDays)      
        Ch = Ch_calc(self, pcr, self.TUr, self.dg, self.Zr, self.Tpor, self.b)      
        Cper = Cper_calc(self, pcr, self.TUw, self.dg, self.Zr, self.S, n_manning, self.w1, self.w2, self.w3)       
        Aimp, Cimp = Cimp_calc(self, pcr, Ao, Ai)     
        Cwp = Cwp_calc(self, pcr, Aimp, Cper, Cimp)      
        Csr = Csr_calc(self, pcr, Cwp, Pdm, self.RCD)

        self.ES = ES_calc(self, pcr, Csr, Ch, precipitation, I, Ao, self.ET_ao)

        print("OK", flush=True)  #print("\tSurface Runoff... OK", flush=True)

        ######### Lateral Flow #########
        print("\tLateral Flow...", end=" ", flush=True)

        self.LF = LF_calc(self, pcr, self.f, self.Kr, self.TUr, self.TUsat)

        print("OK", flush=True)  #print("\tLateral Flow... OK", flush=True)

        ######### Recharge Flow #########
        print("\tRecharge Flow...", end=" ", flush=True)

        self.REC = REC_calc(self, pcr, self.f, self.Kr, self.TUr, self.TUsat)

        print("OK", flush=True) #print("\tRecharge Flow... OK", flush=True)

        ######### Baseflow #########
        print("\tBaseflow...", end=" ", flush=True)
        # reportTif(self, self.ref, self.EBprev, 'EBprev', self.outpath, dyn=True)
        # reportTif(self, self.ref, self.TUs, 'TUs2', self.outpath, dyn=True)

        self.EB = EB_calc(self, pcr, self.EBprev, self.alfa_gw, self.REC, self.TUs, self.EB_lim)
        self.EBprev = self.EB
        # reportTif(self, self.ref, self.EB, 'EB', self.outpath, dyn=True)
        
        print("OK", flush=True)  #print("\tBaseflow... OK", flush=True)

        ######### Soil Balance #########
        print("\tSoil Balance...", end=" ", flush=True)
        self.TUr = TUr_calc(self, pcr, self.TUrprev, precipitation, I, self.ES, self.LF, self.REC, self.ETr, Ao, self.TUsat)
        self.TUs = TUs_calc(self, pcr, self.TUsprev, self.REC, self.EB)
        self.TUrprev = self.TUr

        self.TUsprev = self.TUs
        
        print("OK", flush=True)  #print("\tSoil Balance... OK", flush=True)

        ######### Compute Runoff ########    
        print("\tRunoff...", end=" ", flush=True)

        days = daysOfMonth(startDate,t)  
        c = days*24*3600

        self.Qtot = ((self.ES + self.LF + self.EB)) # [mm]
        self.Qtotvol = self.Qtot*self.A*0.001/c # [m3/s]

        self.Qt = pcrfw.accuflux(self.ldd, self.Qtotvol)

        self.runoff = self.x*self.Qprev + (1-self.x)*self.Qt
        self.Qprev = self.runoff

        print("OK", flush=True)  #print("\tRunoff... OK", flush=True)

        os.chdir(self.outpath)
        print("Exporting variables to files...", end=" ", flush=True)   
        # Create tss files
        if genTss: 
            # Function dictionary to export tss according to filename
            genTssDic = {   
                'Int' : self.TssFileInt.sample, 
                'Bflow' : self.TssFileBflow.sample, 
                'SfRun' : self.TssFileSfRun.sample, 
                'Etp' : self.TssFileEtp.sample, 
                'Lf' : self.TssFileLf.sample, 
                'Rec' : self.TssFileRec.sample, 
                'Ssat' : self.TssFileSsat.sample, 
                'Runoff' : self.TssFileRun.sample
            }
        
        # Variable dictionary to export according to filename
        varDic = {
            'Int' : I, 
            'Bflow' : self.EB, 
            'SfRun' : self.ES, 
            'Etp' : self.ETr, 
            'Lf' : self.LF, 
            'Rec' : self.REC, 
            'Ssat' : self.TUr, 
            'Runoff' : self.runoff
        }

        for fileName, isSelected in genFilesDic.items():
            # Check if the variable (fileName) has been selected for export
            if isSelected:

                # Export raster by default
                reportTif(self, self.ref, varDic.get(fileName), fileName, self.outpath, dyn=True)

                # Check if we have to export the time series of the selected variable (fileName)
                if genTss:
                    # Export tss according to variable (fileName) selected
                    # The same as self.TssFileXxx.sample(self.Xxx)
                    genTssDic.get(fileName)(varDic.get(fileName))

        print("OK ", flush=True) # Exporting variables to files...       

        print(f'Ending cycle {t} of {self.lastStep}', flush=True)                        
      
if __name__ == "__main__":
    
    # Configure CLI
    parser = argparse.ArgumentParser()
    parser.add_argument('--configfile', 
                        type=argparse.FileType('r', encoding='utf-8'), 
                        help="path to configuration file",
                        required=True)
                            
    args = parser.parse_args()

    t1 = time.time()
    print("RUBEM::Started", flush=True)

    print("RUBEM::Reading configuration file...", end=" ", flush=True)
    # Reading the config.ini file
    config = configparser.ConfigParser()
    config.read_file(args.configfile)
    print("OK", flush=True) # RUBEM::Reading configuration file...
    
    # Make sure to close the input stream when finished
    args.configfile.close()

    # Start and end date of simulation
    startDate = config.get('SIM_TIME', 'start')
    endDate = config.get('SIM_TIME', 'end')

    # Check whether the output directory exists
    if not os.path.isdir(str(config.get('FILES', 'output'))):
        # If the output directory doesn't exist create it
        os.mkdir(str(config.get('FILES', 'output')))

    # Store which variables have or have not been selected for export
    genFilesList = ['Int', 'Bflow', 'SfRun', 'Etp', 'Lf', 'Rec', 'Ssat', 'Runoff']
    genFilesDic = {}
    for file in genFilesList:
        genFilesDic[file] = config.getboolean('GENERATE_FILE', file)

    # Check if time series generation has been activated
    genTss = config.getboolean('GENERATE_FILE', 'genTss')        

    steps = totalSteps(startDate,endDate)
    start = steps[0]
    end = steps[1]
    
    print("RUBEM::Running dynamic model...", flush=True)
    myModel = Modelo()
    dynamicModel = pcrfw.DynamicFramework(myModel,lastTimeStep=end, firstTimestep=start)
    dynamicModel.run()
    tempoExec = time.time() - t1
    print(f'RUBEM::Dynamic model runtime: {tempoExec:.2f} seconds')

    # Check whether the generation of time series has been activated
    if genTss:
        print("RUBEM::Converting *.tss files to *.csv...", end=" ", flush=True)
        # Converts generated time series to .csv format and removes .tss files
        tss2csv(myModel.outpath)
        print("OK", flush=True) # Converting *.tss files to *.csv...

    print("RUBEM::Finished", flush=True)