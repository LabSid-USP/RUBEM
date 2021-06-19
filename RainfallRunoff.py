# coding=utf-8

import os
import time
import datetime
import calendar
import configparser
import argparse
# importacao GDAL mais recente mantendo compatibilidade
try:
    from osgeo import gdal
except ImportError:
    import gdal
import numpy as np
import pcraster.framework as pcrfw
import pcraster as pcr

# importacao de funcoes do modelo chuva vazao
from interception import *
from evapotranspiration import *
from surface_runoff import *
from soil import *

########## Funcoes auxiliares ##########
gdal.UseExceptions() 
def getRefInfo(self, sourceTif):
    """
    :param sourceTif:
    :sourceTif type:

    :returns:
    :rtype:     
    """ 
    gdal.AllRegister()
    ds = gdal.OpenEx(sourceTif)
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    trans = ds.GetGeoTransform()
    driver = ds.GetDriver()
    Ref = [cols, rows, trans, driver]
    
    return Ref 

def reportTif(self, tifRef, pcrObj, fileName, outpath, dyn=False):
    """
    :param tifRef:
    :tifRef  type:

    :param pcrObj: PCRaster object to export.
    :pcrObj  type:    
    
    :param fileName: Base name of the output file.
    :fileName  type: str

    :param outpath: Path of the output directory.
    :outpath  type: str   
    
    :param dyn: If dynamic mode is True, otherwise defaults to False.
    :dyn  type: int
    """ 
    # sourceTif = file to get attibutes from - DEM
    # pcrObj  = pcraster to export
    # fileName = string format
    # dyn = if dynamic mode = 1, otherwise 0
    # outpath = path to save Tif file
    
    # convert to np array
    npFile = pcrfw.pcr2numpy(pcrObj,-999)  
    
    # generate file name
    if not dyn:
        out_tif = str(outpath + '/'+ fileName+'.tif')
    if dyn:
        digits = 10 - len(fileName)
        out_tif = str(outpath + '/'+ fileName + str(self.currentStep).zfill(digits)+'.tif')
    
    # initialize export    
    cols = tifRef[0]
    rows = tifRef[1]
    trans = tifRef[2]
    driver = tifRef[3]
    
    # create the output image 
    outDs = driver.Create(out_tif, cols, rows, 1, gdal.GDT_Float32,  options = [ 'COMPRESS=LZW' ] )
    outBand = outDs.GetRasterBand(1)
    outBand.SetNoDataValue(-9999)
    outBand.WriteArray(npFile)
    outDs.SetGeoTransform(trans)
    ds = None
    outDs = None

# Calculo de numero de meses (steps) com base nas datas inicial e final de simulacao
def totalSteps(startDate, endDate):
  """Get the number of months between start and end dates
  
  :param startDate: Start date.
  :startDate type: str
  
  :param startDate: End date.
  :startDate type: str
  
  :return: First step, Last step and Number of months between start and end dates
  :rtype: tuple(int, int ,int)
  """
  start = datetime.datetime.strptime(startDate ,'%d/%m/%Y')
  end = datetime.datetime.strptime(endDate ,'%d/%m/%Y')
  # End date must be greater than start date
  assert end > start 
  nTimeSteps = (end.year - start.year)*12 + (end.month - start.month)
  lastTimeStep = nTimeSteps
  # PCRaster: first timestep argument of DynamicFramework must be > 0
  firstTimestep = 1  
  return (firstTimestep, lastTimeStep, nTimeSteps)

# Calculo de numero de dias no mes a partir do timestep (para conversao de vazao de mm para m3/s)
def daysOfMonth(startDate, timestep):
    """
    :param startDate: Start date.
    :startDate  type: str

    :param timestep:
    :timestep  type: int

    :returns: Days of month.
    :rtype: int        
    """     
    sourcedate = datetime.datetime.strptime(startDate,'%d/%m/%Y')
    month = sourcedate.month -2 + timestep
    year = sourcedate.year + month // 12
    month = (month % 12) +1
    days = calendar.monthrange(year,month)[1]
    return days
 
########## Dynamic Mode ##########
#raise SystemExit
class Modelo(pcrfw.DynamicModel):
    """Constructor"""
    def __init__(self):
        pcrfw.DynamicModel.__init__(self)
        print("Lendo arquivos de entrada", flush=True)
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

        # Area da celula #pendente = calculo automatico da area da celula
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
        # teor de umidade inicial da zona radicular (fracao do teor de saturacao)
        self.ftur_ini = config.getfloat('INITIAL SOIL CONDITIONS', 'ftur_ini')
        # escoamento basico inicial
        self.EBini = pcrfw.scalar(config.getfloat('INITIAL SOIL CONDITIONS', 'eb_ini'))
        # limite para escoamento basico
        self.EBlim = pcrfw.scalar(config.getfloat('INITIAL SOIL CONDITIONS', 'eb_lim'))
        # teor de umidade inicial da zona saturada
        self.Tusini = pcrfw.scalar(config.getfloat('INITIAL SOIL CONDITIONS', 'tus_ini'))

        # constantes
        self.fpar_max = config.getfloat('CONSTANT', 'fpar_max')
        self.fpar_min = config.getfloat('CONSTANT', 'fpar_min')
        self.lai_max = config.getfloat('CONSTANT', 'lai_max')
        self.I_i = config.getfloat('CONSTANT', 'i_imp')

        # Make sure to close the input stream when finished
        args.configfile.close()

        # # Initialize time series output
        self.OutTssRun= 'outRun'

        # Report file
        # name
        self.timeStamp = str(time.strftime("%Y%m%d_%H%M%S",time.localtime(t1)))
        # header 
        self.t_round = str(time.strftime("%Y %m %d %H:%M:%S",time.localtime(t1)))

        # Get Tif file Reference
        self.ref = getRefInfo(self, self.demTif)      
   
    def initial(self):
        """  """       
        # Read dem file
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

        # Initializa Tss report at sample locations or pits
        self.TssFileRun = pcrfw.TimeoutputTimeseries(self.OutTssRun, self, self.sampleLocs, noHeader=True)

        # Read min and max ndvi
        self.ndvi_min = pcrfw.scalar(pcrfw.readmap(self.ndviMinFile))
        self.ndvi_max = pcrfw.scalar(pcrfw.readmap(self.ndviMaxFile))

        # Compute min and max sr
        self.sr_min = sr_calc(self, pcr,self.ndvi_min)
        self.sr_max = sr_calc(self, pcr,self.ndvi_max)

        # Read soil atributes
        solo = pcrfw.readmap(self.soil_path)
        self.Kr = pcrfw.lookupscalar(self.KrTable,solo) #coeficiente de condutividade hidraulica
        self.dg = pcrfw.lookupscalar(self.dgTable,solo) #densidade do solo
        self.Zr = pcrfw.lookupscalar(self.ZrTable,solo) # profundidade da zona radicular [cm]
        self.TUsat = pcrfw.lookupscalar(self.TsatTable,solo)*self.dg*self.Zr*10 # umidade para saturacao da primeira camada [mm]
        self.TUr_ini = (self.TUsat)*(self.ftur_ini) # teor de umidade inicial da zona radicular [mm]
        self.TUw = pcrfw.lookupscalar(self.TwTable,solo)*self.dg*self.Zr*10  # ponto de mucrha do solo [mm]
        self.TUcc = pcrfw.lookupscalar(self.TccTable,solo)*self.dg*self.Zr*10 # capacidade de campo [mm]
        self.Tpor = pcrfw.lookupscalar(self.Tporosidade,solo) # porosidade [%]
        self.EB_ini = self.EBini # escoamento basico inicial [mm]
        self.EB_lim = self.EBlim # limite para condicao de escoamento basico [mm]
        self.TUs_ini = self.Tusini # teor de umidade inicial da camada saturada [mm]

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

    def dynamic(self):
        """  """         
        t = self.currentStep
        #print(t)
        print("Tempo: "+str(t), flush=True)     

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

        ######### compute interception #########      
        SR = sr_calc(self, pcr,NDVI)
        FPAR = fpar_calc(self, pcr, self.fpar_min, self.fpar_max, SR, self.sr_min, self.sr_max)
        LAI = lai_function(self, pcr, FPAR, self.fpar_max, self.lai_max)
        Id, Ir, Iv, I = Interception_function(self, pcr, self.alfa, LAI, precipitation, rainyDays, Av)

        print("\tInterceptacao... OK", flush=True)
        ######### Compute Evapotranspiration #########

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

        print("\tEvapotranspiracao... OK", flush=True)

        ######### Surface Runoff #########      
        Pdm = (precipitation/rainyDays)      
        Ch = Ch_calc(self, pcr, self.TUr, self.dg, self.Zr, self.Tpor, self.b)      
        Cper = Cper_calc(self, pcr, self.TUw, self.dg, self.Zr, self.S, n_manning, self.w1, self.w2, self.w3)       
        Aimp, Cimp = Cimp_calc(self, pcr, Ao, Ai)     
        Cwp = Cwp_calc(self, pcr, Aimp, Cper, Cimp)      
        Csr = Csr_calc(self, pcr, Cwp, Pdm, self.RCD)

        self.ES = ES_calc(self, pcr, Csr, Ch, precipitation, I, Ao, self.ET_ao)

        print("\tEscoamento Superficial... OK", flush=True)
        ######### Lateral Flow #########
        self.LF = LF_calc(self, pcr, self.f, self.Kr, self.TUr, self.TUsat)

        print("\tFluxo Lateral... OK", flush=True)
        ######### Recharge Flow #########
        self.REC = REC_calc(self, pcr, self.f, self.Kr, self.TUr, self.TUsat)

        print("\tRecarga... OK", flush=True)
        ######### Base Flow #########
        # reportTif(self, self.ref, self.EBprev, 'EBprev', self.outpath, dyn=True)
        # reportTif(self, self.ref, self.TUs, 'TUs2', self.outpath, dyn=True)

        self.EB = EB_calc(self, pcr, self.EBprev, self.alfa_gw, self.REC, self.TUs, self.EB_lim)
        self.EBprev = self.EB
        # reportTif(self, self.ref, self.EB, 'EB', self.outpath, dyn=True)

        ######### Soil Balance #########
        self.TUr = TUr_calc(self, pcr, self.TUrprev, precipitation, I, self.ES, self.LF, self.REC, self.ETr, Ao, self.TUsat)
        self.TUs = TUs_calc(self, pcr, self.TUsprev, self.REC, self.EB)
        self.TUrprev = self.TUr

        self.TUsprev = self.TUs
        print("\tBalanco hidrico do solo... OK", flush=True)
        ######### Compute Runoff ########      
        days = daysOfMonth(startDate,t)  
        c = days*24*3600

        self.Qtot = ((self.ES + self.LF + self.EB)) # [mm]
        self.Qtotvol = self.Qtot*self.A*0.001/c # [m3/s]

        self.Qt = pcrfw.accuflux(self.ldd, self.Qtotvol)

        self.runoff = self.x*self.Qprev + (1-self.x)*self.Qt
        self.Qprev = self.runoff

        print("\tVazao... OK", flush=True)

        # # Create tss files
        os.chdir(self.outpath)

        # Lista de arquivos para exportar - ordenados igual a lista de entrada:
        #           ['Int', 'Eb', 'Esd', 'Evp', 'Lf', 'Rec', 'Tur', 'Vazao', 'auxQtot', 'auxRec']
        filesList = [I, self.EB, self. ES, self.ETr, self.LF, self.REC, self.TUr, self.runoff, self.Qtot, self.REC]
        for fileToExport, fileName in zip(filesList, genFilesList):
            if genFilesDic[fileName]:
                reportTif(self, self.ref, fileToExport, fileName, self.outpath, dyn=True)

        print("Finalizando ciclo "+str(t) + " de "+ str(self.lastStep), flush=True)                        
      
if __name__ == "__main__":
    
    # Configure CLI
    parser = argparse.ArgumentParser()
    parser.add_argument('--configfile', 
                        type=argparse.FileType('r', encoding='utf-8'), 
                        help="path to configuration file",
                        required=True)
                            
    args = parser.parse_args()

    t1 = time.time()
    print("Inicio", flush=True)

    # Leitura de arquivo config.ini
    config = configparser.ConfigParser()
    config.read_file(args.configfile)

    # Data inicial e final da simulacao
    startDate = config.get('SIM_TIME', 'start')
    endDate = config.get('SIM_TIME', 'end')

    # mkDir "OutPut"
    if not os.path.isdir(str(config.get('FILES', 'output'))):
        os.mkdir(str(config.get('FILES', 'output')))

    # get files to export
    genFilesList = ['Int', 'Eb', 'Esd', 'Evp', 'Lf', 'Rec', 'Tur', 'Vazao', 'auxQtot', 'auxRec']
    genFilesDic = {}
    for file in genFilesList:
        genFilesDic[file] = config.getboolean('GENERATE_FILE', file)

    steps = totalSteps(startDate,endDate)
    start = steps[0]
    end = steps[1]
    myModel = Modelo()
    dynamicModel = pcrfw.DynamicFramework(myModel,lastTimeStep=end, firstTimestep=start)
    dynamicModel.run()
    tempoExec = time.time() - t1
    print("Tempo de execucao: {:.2f} segundos".format(tempoExec))
    print("Fim", flush=True)