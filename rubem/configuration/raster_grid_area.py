import logging


class RasterGrid:
    """
    Represents a raster grid properties.

    :param size: Size of the grid area.
    :type size: float
    """

    def __init__(self, size: float) -> None:
        self.logger = logging.getLogger(__name__)
        if size <= 0:
            raise ValueError(f"Invalid grid area: {size}")

        self.area = size**2

    def __str__(self) -> str:
        return f"{ self.area } [m²]"
