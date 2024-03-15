import logging
import os
from typing import Union

from ..configuration.raster_map import RasterMap


class OutputRasterBase:
    def __init__(self, base_raster_path: Union[str, bytes, os.PathLike]):
        self.logger = logging.getLogger(__name__)
        base_raster = RasterMap(base_raster_path)
        self.cols = base_raster.raster.RasterXSize
        self.rows = base_raster.raster.RasterYSize
        self.transformation = base_raster.raster.GetGeoTransform()
        base_raster = None
