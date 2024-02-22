from unittest.mock import MagicMock

import pytest

from rubem.configuration.raster_map import RasterBand


class TestRasterBand:

    @pytest.mark.unit
    def test_init_valid_band(self):
        band_mock = MagicMock()
        band_mock.GetNoDataValue.return_value = -9999
        band_mock.GetStatistics.return_value = (0, 255, 127.5, 50)
        band_mock.DataType = 1
        band_mock.ReadAsArray.return_value = [[1, 2], [3, 4]]

        raster_band = RasterBand(1, band_mock)

        assert raster_band.index == 1
        assert raster_band.band == band_mock
        assert raster_band.no_data_value == -9999
        assert raster_band.min == 0
        assert raster_band.max == 255
        assert raster_band.mean == 127.5
        assert raster_band.std_dev == 50
        assert raster_band.data_type == "Byte"
        assert raster_band.data_array == [[1, 2], [3, 4]]

    @pytest.mark.unit
    def test_init_invalid_band(self):
        with pytest.raises(ValueError):
            RasterBand(1, None)

    @pytest.mark.unit
    def test_str(self):
        band_mock = MagicMock()
        band_mock.GetNoDataValue.return_value = -9999
        band_mock.GetStatistics.return_value = (0, 255, 127.5, 50)
        band_mock.DataType = 1

        raster_band = RasterBand(1, band_mock)

        expected_output = (
            "Index: 1, "
            "Data Type: Byte, "
            "NoData Value: -9999, "
            "Statistics: Min: 0, Max: 255, Mean: 127.5, Std Dev: 50"
        )

        assert str(raster_band) == expected_output
