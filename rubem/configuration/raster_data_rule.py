from enum import Enum


class RasterDataRule(Enum):
    """
    Enumeration class representing different rules for raster data.
    """

    ALLOW_ALL_ZEROES = 1
    ALLOW_ALL_ONES = 2
    FORBID_ALL_ZEROES = 3
    FORBID_ALL_ONES = 4
    FORBID_NO_DATA = 5
