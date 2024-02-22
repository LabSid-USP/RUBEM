from enum import Flag, auto


class RasterDataRules(Flag):
    """
    Enumeration class representing different rules for raster data.
    """

    FORBID_ALL_ZEROES = auto()
    """
    Raster pixels cannot consist entirely of ``0.0`` values.
    """

    FORBID_ALL_ONES = auto()
    """
    Raster pixels cannot consist entirely of ``1.0`` values.
    """

    FORBID_NO_DATA = auto()
    """
    None of the raster pixels must contain ``NO_DATA`` values.
    """

    FORBID_OUT_OF_RANGE = auto()
    """
    Raster pixels must be within the specified valid range.
    """

    def __str__(self):
        return self.name.upper()
