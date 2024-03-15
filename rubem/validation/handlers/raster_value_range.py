import numpy as np

from ...validation.handlers.base import BaseValidatorHandler
from ...validation.raster_data_rules import RasterDataRules


class ValueRangeValidatorHandler(BaseValidatorHandler):
    """
    A validator handler that checks if the values in a raster are within a valid range.

    :param raster: The raster to be validated.
    :type raster: RasterMap

    :return: ``True`` if all values are within the valid range, ``False`` otherwise.
    :rtype: bool
    """

    def handle(self, raster, errors):
        if not raster.valid_range:
            self.logger.info("`ValueRange` validator skipped because no value range was set.")
            return super().handle(raster, errors)

        min_value = raster.valid_range["min"]
        max_value = raster.valid_range["max"]

        for band in raster.bands:
            no_data_value = band.no_data_value
            band_array = band.data_array

            if no_data_value is not None:
                band_array = band_array[band_array != no_data_value]

            has_valid_range_condition = np.all(
                (band_array >= min_value) & (band_array <= max_value)
            )

            if not has_valid_range_condition:
                errors.append(RasterDataRules.FORBID_OUT_OF_RANGE)
                return False

        return super().handle(raster, errors)
