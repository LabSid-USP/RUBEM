import numpy as np

from rubem.validation.handlers.base import BaseValidatorHandler
from rubem.validation.raster_data_rules import RasterDataRules


class AllOnesValidatorHandler(BaseValidatorHandler):
    """
    A validator handler that checks if all values in a raster are one.

    This handler checks if the rule ``FORBID_ALL_ONES`` is set for the raster.
    If the rule is set and all values in the raster are one, it returns ``False``,
    indicating that the validation has failed. Otherwise, it delegates the handling
    to the base validator handler.

    :param raster: The raster object to be validated.
    :type raster:

    :return: ``True`` if the raster data is valid, ``False`` otherwise.
    """

    def handle(self, raster):
        if not raster.rules:
            self.logger.info("`FORBID_ALL_ONES` validator skipped because no rules were set.")
            return super().handle(raster)

        if not RasterDataRules.FORBID_ALL_ONES in raster.rules:
            self.logger.debug("`FORBID_ALL_ONES` validator skipped because the rule was not set.")
            return super().handle(raster)

        band_array = raster.bands[0].data_array
        all_ones_condition = np.allclose(band_array, 1, atol=1e-8)

        if all_ones_condition:
            return False

        return super().handle(raster)
