from unittest.mock import MagicMock

import numpy as np
import pytest

from rubem.validation.handlers.raster_no_data import NoDataValidatorHandler
from rubem.validation.raster_data_rules import RasterDataRules
from rubem.configuration.raster_map import RasterMap, RasterBand


class TestNoDataValidatorHandler:

    @pytest.mark.unit
    def test_handle_no_rules_set(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.rules = None

        # Act
        errors = []
        handler = NoDataValidatorHandler()
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is True
        assert not errors

    @pytest.mark.unit
    def test_handle_no_data_rule_not_set(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.rules = (
            RasterDataRules.FORBID_ALL_ONES
            | RasterDataRules.FORBID_ALL_ZEROES
            | RasterDataRules.FORBID_OUT_OF_RANGE
        )

        # Act
        errors = []
        handler = NoDataValidatorHandler()
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is True
        assert not errors

    @pytest.mark.unit
    def test_handle_no_data_present(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.rules = RasterDataRules.FORBID_NO_DATA
        raster_mock.bands = []
        band_mock = MagicMock(spec=RasterBand)
        band_mock.no_data_value = -9999
        band_mock.data_array = np.array([[1, 2, 3], [4, 5, -9999], [7, 8, 9]])
        raster_mock.bands.append(band_mock)

        # Act
        errors = []
        handler = NoDataValidatorHandler()
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is False
        assert len(errors) == 1
        assert errors[0] == RasterDataRules.FORBID_NO_DATA

    @pytest.mark.unit
    def test_handle_no_data_not_present(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.rules = RasterDataRules.FORBID_NO_DATA
        raster_mock.bands = []
        band_mock = MagicMock(spec=RasterBand)
        band_mock.no_data_value = -9999
        band_mock.data_array = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        raster_mock.bands.append(band_mock)

        # Act
        errors = []
        handler = NoDataValidatorHandler()
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is True
        assert not errors
