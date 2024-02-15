import logging

from rubem.validation.handlers.raster_all_ones import AllOnesValidatorHandler
from rubem.validation.handlers.raster_all_zeroes import AllZeroesValidatorHandler
from rubem.validation.handlers.raster_no_data import NoDataValidatorHandler
from rubem.validation.handlers.raster_value_range import ValueRangeValidatorHandler


class RasterMapValidator:
    """
    Class to validate raster maps data.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def validate(self, raster):
        """
        Validate the given raster map data.

        :param raster: The raster map to be validated.
        :type raster:

        :return: True if the raster map is valid, False otherwise.
        :rtype: bool
        """

        value_range = ValueRangeValidatorHandler()
        no_data = NoDataValidatorHandler()
        all_zeroes = AllZeroesValidatorHandler()
        all_ones = AllOnesValidatorHandler()

        value_range.set_next(no_data)
        no_data.set_next(all_zeroes)
        all_zeroes.set_next(all_ones)

        return value_range.handle(raster)
