from unittest.mock import MagicMock

import numpy as np
import pytest

from rubem.validation.handlers.raster_all_zeroes import AllZeroesValidatorHandler
from rubem.validation.raster_data_rules import RasterDataRules
from rubem.configuration.raster_map import RasterMap, RasterBand


class TestAllZeroesValidatorHandler:

    @pytest.mark.unit
    def test_handle_no_rules(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.rules = None

        # Act
        errors = []
        handler = AllZeroesValidatorHandler()
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is True
        assert not errors

    @pytest.mark.unit
    def test_handle_rule_not_set(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.rules = (
            RasterDataRules.FORBID_ALL_ONES
            | RasterDataRules.FORBID_NO_DATA
            | RasterDataRules.FORBID_OUT_OF_RANGE
        )

        # Act
        errors = []
        handler = AllZeroesValidatorHandler()
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is True
        assert not errors

    @pytest.mark.unit
    def test_handle_all_zeroes(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.rules = [RasterDataRules.FORBID_ALL_ZEROES]
        raster_mock.bands = []
        band_mock = MagicMock(spec=RasterBand)
        band_mock.data_array = np.zeros((10, 10))
        raster_mock.bands.append(band_mock)

        # Act
        errors = []
        handler = AllZeroesValidatorHandler()
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is False
        assert errors == [RasterDataRules.FORBID_ALL_ZEROES]

    @pytest.mark.unit
    def test_handle_not_all_zeroes(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.rules = [RasterDataRules.FORBID_ALL_ZEROES]
        raster_mock.bands = []
        band_mock = MagicMock(spec=RasterBand)
        band_mock.data_array = np.ones((10, 10))
        raster_mock.bands.append(band_mock)

        # Act
        errors = []
        handler = AllZeroesValidatorHandler()
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is True
        assert not errors

    @pytest.mark.unit
    def test_handle_multiple_bands(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.rules = [RasterDataRules.FORBID_ALL_ZEROES]
        raster_mock.bands = []
        band1_mock = MagicMock(spec=RasterBand)
        band1_mock.data_array = np.ones((10, 10))
        raster_mock.bands.append(band1_mock)
        band2_mock = MagicMock(spec=RasterBand)
        band2_mock.data_array = np.zeros((10, 10))
        raster_mock.bands.append(band2_mock)

        # Act
        errors = []
        handler = AllZeroesValidatorHandler()
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is False
        assert errors == [RasterDataRules.FORBID_ALL_ZEROES]
