import time
t1 = time.time()
import os
import gdal
import numpy as np
import skgstat as skg
import pykrige.kriging_tools as kt
from pykrige.ok import OrdinaryKriging
from pcraster import *
from pcraster.framework import *



class Krige_Interpolation(DynamicModel):
    def __init__(self, path, demMap, CSV):

        """Generated tss files with interpolate variable using krigging method.
    
        :param Path: Directory containing the files.
        :Path type: str

        :param demMap: Path to Digital Elevetion Model (DEM) .map format
        :demMap  type: str

        :param CSV: Path to dataset) 
        :type CSV: str
 
        :returns: tss files interpolated
        :rtype"""
        DynamicModel.__init__(self)
        setclone(demMap)
        self.src_ds = demMap
        self.rain_file = CSV
        self.Files_path = path
        
        
        #self.OutMap = outMap
    
    def initial(self):   
        # Get geometry data from raster
        ds = gdal.Open(self.src_ds)
        ulx, xres, xskew, uly, yskew, yres  = ds.GetGeoTransform()
        lrx = ulx + (ds.RasterXSize * xres)
        lry = uly + (ds.RasterYSize * yres)
        self.gridx = np.arange(ulx+(xres/2), lrx, xres)
        self.gridy = np.arange(lry+(-yres/2), uly, -yres)
        os.chdir(self.Files_path)
  

        #Define Number of lags (depends on the number of stations)
        self.n_lags= 25
        
    def dynamic(self):
        # Pykrige - https://pypi.org/project/PyKrige/
        # scikit - https://pypi.org/project/scikit-gstat/
        t= scalar(self.currentStep)
        x = int(np.unique(pcr2numpy(t+1,-999)))
        rain_data = np.genfromtxt(self.rain_file,delimiter=';')
        values=rain_data[:, x] 
        result = np.all(values == values[0])
        if result:
            self.z1 = np.full((self.gridy.size, self.gridx.size), values[0])
        else:
            self.V = skg.Variogram(coordinates=(np.array([rain_data[:, 0],rain_data[:, 1]]).T), values=rain_data[:, x] ,bin_func='uniform', n_lags=self.n_lags)
            OK = OrdinaryKriging(rain_data[:, 0], rain_data[:, 1], rain_data[:, x],
                                variogram_model='spherical', variogram_parameters= [(self.V.parameters[1]),(self.V.parameters[0]),(self.V.parameters[2])], verbose=False, nlags=self.n_lags, weight=True, enable_plotting=False, coordinates_type='geographic')
            self.z, ss = OK.execute('grid', self.gridx, (np.flip(self.gridy,axis=0)))
            self.z1 = np.where(self.z<0,0,self.z)
          
            
        self.rain = numpy2pcr(Scalar,self.z1,-999)

        self.report(self.rain,'prec')
        
nrOfTimeSteps = 20
myModel = Krige_Interpolation('D:/Krigagem/','D:/Krigagem/dem.map','D:/Krigagem/Rains.csv')
dynamicModel = DynamicFramework(myModel, nrOfTimeSteps)
dynamicModel.run()


import time
tempoExec = time.time() - t1
print("Tempo de execução: {} segundos".format(tempoExec))