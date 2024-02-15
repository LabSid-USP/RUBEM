import numpy as np

from rubem.validation.handlers.base import BaseValidatorHandler


class ValueRangeValidatorHandler(BaseValidatorHandler):
    """
    A validator handler that checks if the values in a raster are within a valid range.

    :param raster: The raster to be validated.
    :type raster:

    :return: ``True`` if all values are within the valid range, ``False`` otherwise.
    :rtype: bool
    """

    def handle(self, raster):
        if not raster.valid_range:
            self.logger.info("`ValueRange` validator skipped because no value range was set.")
            return super().handle(raster)

        min_value = raster.valid_range["min"]
        max_value = raster.valid_range["max"]
        no_data_value = raster.bands[0].no_data_value
        band_array = raster.bands[0].data_array

        if no_data_value is not None:
            band_array = band_array[band_array != no_data_value]

        has_valid_range_condition = np.all((band_array >= min_value) & (band_array <= max_value))

        if not has_valid_range_condition:
            return False

        return super().handle(raster)
