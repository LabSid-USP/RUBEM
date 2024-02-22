from unittest.mock import MagicMock

import pytest
import numpy as np

from rubem.validation.handlers.raster_all_ones import AllOnesValidatorHandler
from rubem.validation.raster_data_rules import RasterDataRules
from rubem.configuration.raster_map import RasterMap, RasterBand


class TestAllOnesValidatorHandler:

    @pytest.mark.unit
    def test_handle_no_rules_set(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        handler = AllOnesValidatorHandler()
        raster_mock.rules = None

        # Act
        errors = []
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is True
        assert not errors

    @pytest.mark.unit
    def test_handle_rule_not_set(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.rules = (
            RasterDataRules.FORBID_ALL_ZEROES
            | RasterDataRules.FORBID_NO_DATA
            | RasterDataRules.FORBID_OUT_OF_RANGE
        )

        # Act
        handler = AllOnesValidatorHandler()
        errors = []
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is True
        assert not errors

    @pytest.mark.unit
    def test_handle_all_ones(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.rules = RasterDataRules.FORBID_ALL_ONES
        raster_mock.bands = []
        band_mock = MagicMock(spec=RasterBand)
        band_mock.data_array = np.ones((10, 10))
        raster_mock.bands.append(band_mock)

        # Act
        handler = AllOnesValidatorHandler()
        errors = []
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is False
        assert len(errors) == 1
        assert errors[0] == RasterDataRules.FORBID_ALL_ONES

    @pytest.mark.unit
    def test_handle_not_all_ones(self):
        # Arrange
        raster_mock = MagicMock(spec=RasterMap)
        raster_mock.rules = RasterDataRules.FORBID_ALL_ONES
        raster_mock.bands = []
        band_mock = MagicMock(spec=RasterBand)
        band_mock.data_array = np.zeros((10, 10))
        raster_mock.bands.append(band_mock)

        # Act
        handler = AllOnesValidatorHandler()
        errors = []
        result = handler.handle(raster_mock, errors)

        # Assert
        assert result is True
        assert not errors
