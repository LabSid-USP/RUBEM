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

"""Common file conversion to generate input data used by RUBEM."""

__author__ = "LabSid PHA EPUSP"
__email__ = "rubem.hydrological@labsid.eng.br"
__copyright__ = "Copyright 2020-2021, LabSid PHA EPUSP"
__license__ = "GPL"
__date__ = "2019-07-09"
__version__ = "0.1.0"

import gdal
import glob
import os

def tif2map(Tifs_Dir):
    """Convert *.tif to *.map
    
    :param Tifs_Dir: Directory containing the files.
    :Tifs_Dir type: str

    :returns: files in .map format
    :rtype:*.map

    """
    
    # change the current directory 
    # to specified directory 
    os.chdir(Tifs_Dir)
    
    #folders containing files to read
    Raster_path = os.getcwd()

    #files
    Raster_files = glob.glob(os.path.join(Raster_path,'*.tif'))

    #Type output data --- options: gdal.GDT_Byte= BOOLEAN ; gdal.GDT_Int32= NOMINAL ; gdal.GDT_Float32=SCALAR
    outputType= gdal.GDT_Int32

    
    for x in range(len(Raster_files)):
        print(x)
        ## convert to PCRaster file format
        out_map = gdal.Translate(str((Raster_files[x][:-4])+'.map'), Raster_files[x], format ='PCraster', outputType=outputType)
    
    return(out_map)
    



tif2map('/path/to/files/to/be/converted')
