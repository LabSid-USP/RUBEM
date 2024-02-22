from unittest.mock import MagicMock

import numpy as np
import pytest

from rubem.validation.handlers.raster_value_range import ValueRangeValidatorHandler
from rubem.validation.raster_data_rules import RasterDataRules
from rubem.configuration.raster_map import RasterMap, RasterBand


class TestValueRangeValidatorHandler:

    @pytest.mark.unit
    def test_handle_valid_range(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.valid_range = {"min": 0.0, "max": 100.0}
        raster_mock.bands = []
        band_mock = MagicMock(spec=RasterBand)
        band_mock.no_data_value = -9999
        band_mock.data_array = np.array([10, 20, 30, 40, 50])
        raster_mock.bands.append(band_mock)

        # Act
        handler = ValueRangeValidatorHandler()
        errors = []
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is True
        assert not errors

    @pytest.mark.unit
    def test_handle_invalid_range(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.valid_range = {"min": 0.0, "max": 100.0}
        raster_mock.bands = []
        band_mock = MagicMock(spec=RasterBand)
        band_mock.no_data_value = -9999
        band_mock.data_array = np.array([10, 20, 30, 110, 120])
        raster_mock.bands.append(band_mock)

        # Act
        handler = ValueRangeValidatorHandler()
        errors = []
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is False
        assert len(errors) == 1
        assert errors[0] == RasterDataRules.FORBID_OUT_OF_RANGE

    @pytest.mark.unit
    def test_handle_no_range_set(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.valid_range = None
        raster_mock.bands = []
        band_mock = MagicMock(spec=RasterBand)
        band_mock.no_data_value = -9999
        band_mock.data_array = np.array([10, 20, 30, 40, 50])
        raster_mock.bands.append(band_mock)

        # Act
        handler = ValueRangeValidatorHandler()
        errors = []
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is True
        assert not errors
