import numpy as np

from rubem.validation.handlers.base import BaseValidatorHandler
from rubem.validation.raster_data_rules import RasterDataRules


class NoDataValidatorHandler(BaseValidatorHandler):
    """
    A validator handler that checks the presence of ``NO_DATA`` values in a raster.

    This handler checks if the raster data contains ``NO_DATA`` values based on the rules set.
    If the rules are not set or the specific rule for forbidding ``NO_DATA`` values is not set,
    the validation is skipped. Otherwise, it checks if all the pixels in the raster
    have the ``NO_DATA`` value and returns ``False`` if they do.

    :param raster: The raster object to be validated.
    :type raster: RasterMap

    :return: ``True`` if the raster data is valid, ``False`` otherwise.
    """

    def handle(self, raster, errors):
        if not raster.rules:
            self.logger.info("`FORBID_NO_DATA` validator skipped because no rules were set.")
            return super().handle(raster, errors)

        if not RasterDataRules.FORBID_NO_DATA in raster.rules:
            self.logger.debug("`FORBID_NO_DATA` validator skipped because the rule was not set.")
            return super().handle(raster, errors)

        for band in raster.bands:
            no_data_value = band.no_data_value
            band_array = band.data_array
            no_data_condition = np.any(band_array == no_data_value)

            if no_data_condition:
                errors.append(RasterDataRules.FORBID_NO_DATA)
                return False

        return super().handle(raster, errors)
