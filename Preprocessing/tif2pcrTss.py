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

"""Common file conversion functionality used by RUBEM."""

__author__ = "LabSid PHA EPUSP"
__email__ = "rubem.hydrological@labsid.eng.br"
__copyright__ = "Copyright 2020-2021, LabSid PHA EPUSP"
__license__ = "GPL"
__date__ = "2021-05-19"
__version__ = "0.1.0"

import gdal
import numpy as np
import glob
from pcraster import *
from pcraster.framework import *
import os

class Tif2pcrTss(DynamicModel):
    def __init__(self, Path, Name_prefix, CloneMap):
        """Convert *.tif to tss.
    
        :param Path: Directory containing the files.
        :Path type: str

        :param Name_prefix: Prefix for name the tss files.
        :type Name_prefix: str

        :param CloneMap: Path to clone file with resolution and size desired
        :CloneMap  type: str
 
        :returns: File in tss format
        :rtype: *.00*
        """
        DynamicModel.__init__(self)
        setclone(CloneMap)

        #folders containing files to read
        self.Raster_path = Path
        self.file_name = Name_prefix
    
    def initial(self):
        #files
        self.Raster_files = glob.glob(os.path.join(self.Raster_path,'*.tif'))
        os.chdir(self.Raster_path)
    
    def dynamic(self):
        # Run raster list to generate Tss
        t= int(self.currentStep)
        
        # Read as array 
        file = gdal.Open(self.Raster_files[t-1])
        file_array = np.array(file.GetRasterBand(1).ReadAsArray())

        pcr_file = numpy2pcr(Scalar,file_array,-999)

        self.report(pcr_file,self.file_name)

#Number of timesteps must match to number of files
nrOfTimeSteps = 8
myModel = Tif2pcrTss('/path/to/files/to/be/converted',
                     'prefix',
                     '/path/to/clone.map')
dynamicModel = DynamicFramework(myModel, nrOfTimeSteps)
dynamicModel.run()

