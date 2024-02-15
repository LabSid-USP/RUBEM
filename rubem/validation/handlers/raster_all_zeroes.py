import numpy as np

from rubem.validation.handlers.base import BaseValidatorHandler
from rubem.validation.raster_data_rules import RasterDataRules


class AllZeroesValidatorHandler(BaseValidatorHandler):
    """
    A validator handler that checks if all values in a raster are zero.

    This handler checks if the rule ``FORBID_ALL_ZEROES`` is set for the raster.
    If the rule is set and all values in the raster are zero, it returns ``False``,
    indicating that the validation has failed. Otherwise, it delegates the handling
    to the base validator handler.

    :param raster: The raster object to be validated.
    :type raster:

    :return: ``True`` if the raster data is valid, ``False`` otherwise.
    """

    def handle(self, raster):
        """
        Handle the validation for the given raster.

        Args:
            raster: The raster object to be validated.

        Returns:
            bool: True if the validation passes, False otherwise.
        """
        if not raster.rules:
            self.logger.info("`FORBID_ALL_ZEROES` validator skipped because no rules were set.")
            return super().handle(raster)

        if not RasterDataRules.FORBID_ALL_ZEROES in raster.rules:
            self.logger.debug("`FORBID_ALL_ZEROES` validator skipped because the rule was not set.")
            return super().handle(raster)

        band_array = raster.bands[0].data_array
        zero_condition = np.allclose(band_array, 0, atol=1e-8)

        if zero_condition:
            return False

        return super().handle(raster)
