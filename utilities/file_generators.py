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

"""Common file generation functionality used by RUBEM."""

__author__ = "LabSid PHA EPUSP"
__email__ = "rubem.hydrological@labsid.eng.br"
__copyright__ = "Copyright 2020-2021, LabSid PHA EPUSP"
__license__ = "GPL"
__date__ = "2021-05-19"
__version__ = "0.1.0"

# Import the latest GDAL library while maintaining
# backward compatibility
try:
    from osgeo.gdal import AllRegister, GDT_Float32, OpenEx, UseExceptions
except ImportError:
    from gdal import UseExceptions, AllRegister, OpenEx, GDT_Float32

from pcraster.framework import pcr2numpy

UseExceptions()


def getRefInfo(self, sourceTif):
    """Return size, resolution and corner coordinates from a Raster file (DEM in RUBEM).
    
    :param sourceTif: Path to DEM file to get information
    :sourceTif type: str

    :returns: Array with information
    :rtype: array
    """
    AllRegister()
    ds = OpenEx(sourceTif)
    cols = ds.RasterXSize
    rows = ds.RasterYSize
    trans = ds.GetGeoTransform()
    driver = ds.GetDriver()
    Ref = [cols, rows, trans, driver]

    return Ref


def reportTif(self, tifRef, pcrObj, fileName, outpath, dyn=False):
    """Create a .tif raster from a PCRaster object.
    
    :param tifRef: array with dem raster information
    :tifRef  type: array

    :param pcrObj: PCRaster object to export.
    :pcrObj  type: Either Boolean, Nominal, Ordinal, Scalar, Directional or Ldd

    :param fileName: Base name of the output file.
    :fileName  type: str

    :param outpath: Path of the output directory.
    :outpath  type: str

    :param dyn: If dynamic mode is True, otherwise defaults to False.
    :dyn  type: int

    :returns: File in .tif format
    :rtype: .tif
    """
 

    # convert to np array
    npFile = pcr2numpy(pcrObj, -999)

    # generate file name
    if not dyn:
        out_tif = str(outpath + "/" + fileName + ".tif")
    if dyn:
        digits = 10 - len(fileName)
        out_tif = str(
            outpath + "/" + fileName + str(self.currentStep).zfill(digits) + ".tif"
        )

    # initialize export
    cols = tifRef[0]
    rows = tifRef[1]
    trans = tifRef[2]
    driver = tifRef[3]

    # create the output image
    outDs = driver.Create(out_tif, cols, rows, 1, GDT_Float32, options=["COMPRESS=LZW"])
    outBand = outDs.GetRasterBand(1)
    outBand.SetNoDataValue(-9999)
    outBand.WriteArray(npFile)
    outDs.SetGeoTransform(trans)
    ds = None
    outDs = None

def reportMapSeries(self, VariableName, fileName):
    """Store map data in the specified file.

    :param fileName: Prefix name of the output file.
    :fileName  type: str
    
    :param VariableName: Base name of variable to be export.
    :fileName  type: str
    """ 
    self.report(VariableName,fileName)
