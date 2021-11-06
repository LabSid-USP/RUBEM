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

"""Interpolation method for generated metereological forcing maps series."""

__author__ = "LabSid PHA EPUSP"
__email__ = "rubem.hydrological@labsid.eng.br"
__copyright__ = "Copyright 2020-2021, LabSid PHA EPUSP"
__license__ = "GPL"
__date__ = "2019-06-23"
__version__ = "0.1.0"

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
        """Variable interpolation using the kriging method.
    
        :param Path: Directory containing the files.
        :Path type: str

        :param demMap: Path to Digital Elevetion Model (DEM) .map format
        :demMap  type: str

        :param CSV: Path to data 
        :type CSV: str
 

        """

        DynamicModel.__init__(self)
        setclone(demMap)
        self.src_ds = demMap
        self.rain_file = CSV
        self.Files_path = path
              
        
    
    def initial(self):  
        """Prepare the set of input variables to run the timestep 1 """
        # Get geometry data from raster
        ds = gdal.Open(self.src_ds)
        ulx, xres, xskew, uly, yskew, yres  = ds.GetGeoTransform()
        lrx = ulx + (ds.RasterXSize * xres)
        lry = uly + (ds.RasterYSize * yres)
        self.gridx = np.arange(ulx+(xres/2), lrx, xres)
        self.gridy = np.arange(lry+(-yres/2), uly, -yres)
        os.chdir(self.Files_path)
  

        #User must define Number of lags (depends on the number of stations)
        self.n_lags= 25
        
    def dynamic(self):
        """Return tss files with interpolate variable using krigging method

        :returns: tss files interpolated
        :rtype:PCRaster MAP Series"""

    
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

        #Second argument correspon to files prefix (e.g. 'prec','etp','kp')
        self.report(self.rain,'prec')


#Number of timesteps must to be <= csv columns data
nrOfTimeSteps = 20
myModel = Krige_Interpolation('/path/for/output/files/','/path/and/filename/dem.map','/path/and/filename/CSV/file/data.csv')
dynamicModel = DynamicFramework(myModel, nrOfTimeSteps)
dynamicModel.run()

tempoExec = time.time() - t1
print("Tempo de execução: {} segundos".format(tempoExec))