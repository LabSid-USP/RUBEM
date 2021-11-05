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

"""Common file conversion to generate input data used by RUBEM"""

__author__ = "LabSid PHA EPUSP"
__email__ = "rubem.hydrological@labsid.eng.br"
__copyright__ = "Copyright 2020-2021, LabSid PHA EPUSP"
__license__ = "GPL"
__date__ = "2019-03-25"
__version__ = "0.1.0"


import gdal
import numpy as np
import pcraster as pcr
import os


            
def numpy2tif(sourceTif, outpath, numpy_array):
    """Convert numpy arrays to (*.tif).
    
    :param sourceTif: Path to Digital Elevetion Model (DEM) with same resolution and size that tss files
    :sourceTif type: .tif  file

    :param outpath: Path of the output directory.
    :type path: str

    :param numpy_array: Numpy object to be converter
    :numpy_array  type: numpy.ndarray
 
    :returns: File in .tif format
    :rtype: .tif
    """
    out_tif = str(outpath)        
    ds = gdal.Open(sourceTif)
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    trans = ds.GetGeoTransform()   
    # create the output image
    driver = ds.GetDriver()
    outDs = driver.Create(out_tif, cols, rows, 1, gdal.GDT_Int32,  options = [ 'COMPRESS=LZW' ] )
    outBand = outDs.GetRasterBand(1)
    outBand.SetNoDataValue(-9999)
    outBand.WriteArray(numpy_array)
    outDs.SetGeoTransform(trans)
    ds = None
    outDs = None
    
    return()

def pcrTss2Tif(inputFolder, demSrc):
    """Convert all PCRaster Time Series (*.tss) files present in the specified directory to (*.tif).
        
    :param inputFolder: Directory containing the files.
    :type inputFolder: str

    :param demSrc: Path to Digital Elevetion Model (DEM) with same resolution and size that tss files
    :demSrc type: .tif  file

    :returns: files in .tif format
    :rtype:*.tif
    """

    src = demSrc
    outpath = inputFolder
    print(outpath)
    files_path = [os.path.join(outpath, fn) for fn in next(os.walk(outpath))[2]]
    for i in range(len(files_path)):
        print(files_path[i])
        readFile = pcr.readmap(files_path[i])
        npFile = pcr.pcr2numpy(readFile, -9999)
        outfile = (str(files_path[i][:-4]) +str('-')+ str(i+1) + '.tif')
        numpy2tif(src, outfile, npFile)
    
    return()



pcrTss2Tif('/path/to/files/to/be/converted', '/path/to/DEM.tif')


