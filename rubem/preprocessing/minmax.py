# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Contact: rubem.hydrological@labsid.eng.br

"""Common file conversion functionality used by RUBEM."""

import os
import glob
from osgeo import gdal
import numpy as np


##Attributes, defined by the user
# Input_path =  'Directory containing the files'.
# dem_source = 'Path to Digital Elevetion Model (DEM) with same resolution and size that input_path files- example:D:/dem.tif'
# outpath_min = 'Path and name minimum output file example=D:/ndvi_min.tif'
# outpath_max = 'Path and name maximum output file example=D:/ndvi_max.tif'


Input_path = ""
dem_source = ""
outpath_min = ""
outpath_max = ""

# files
Raster_files = glob.glob(os.path.join(Input_path, "*.tif"))


def readfile(file):
    """Read file usins Gdal.

    :param file: Path to file in .tif format
    :file type: str

    :returns: numpy array
    :rtype: numpy array#
    """
    open_file = gdal.Open(file)
    ds = np.array(open_file.GetRasterBand(1).ReadAsArray())

    return ds


# Export numpy 2 tif files using gdal
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
    outDs = driver.Create(
        out_tif, cols, rows, 1, gdal.GDT_Float64, options=["COMPRESS=LZW"]
    )
    outBand = outDs.GetRasterBand(1)
    outBand.SetNoDataValue(-999)
    outBand.WriteArray(numpy_array)
    outDs.SetGeoTransform(trans)
    ds = None
    outDs = None

    return ()


# apply function, and convert type list to type array
dataset = np.asarray([readfile(x) for x in Raster_files])

# lenght of list has to be the number of files on the given path
print(len(dataset))

# converts the input (list) to an array before finding the minimum along that axis 0
min_data = dataset.min(0)
numpy2tif(dem_source, outpath_min, min_data)

# converts the input to an array before finding the minimum along that axis 0
max_data = dataset.max(0)
numpy2tif(dem_source, outpath_max, max_data)
