from unittest.mock import MagicMock

import pytest

from rubem.configuration.raster_map import RasterMap, RasterDataRules, RasterBand


class TestRasterMap:

    @pytest.mark.unit
    def test_init_valid_file_no_range_no_rules(self, mocker):
        # Arrange
        file_path = "/path/to/raster.tif"
        mocker.patch("osgeo.gdal.OpenEx")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.path.getsize", return_value=100)
        mocker.patch(
            "rubem.configuration.raster_map.RasterBand", return_value=MagicMock(spec=RasterBand)
        )
        # Act
        raster_map = RasterMap(file_path)

        # Assert
        assert raster_map is not None
        assert len(raster_map.bands) == 1

    @pytest.mark.unit
    def test_init_valid_file_with_range_with_rules(self, mocker):
        # Arrange
        file_path = "/path/to/raster.tif"
        valid_range = {"min": 0.0, "max": 255.0}
        rules = RasterDataRules.FORBID_ALL_ZEROES | RasterDataRules.FORBID_ALL_ONES
        mocker.patch("osgeo.gdal.OpenEx")
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.path.getsize", return_value=100)
        mocker.patch(
            "rubem.configuration.raster_map.RasterBand", return_value=MagicMock(spec=RasterBand)
        )
        # Act
        raster_map = RasterMap(file_path, valid_range, rules)

        # Assert
        assert raster_map is not None
        assert raster_map.valid_range == valid_range
        assert raster_map.rules == rules
        assert len(raster_map.bands) == 1

    @pytest.mark.unit
    def test_init_invalid_file(self, mocker):
        mocker.patch("os.path.isfile", return_value=False)
        with pytest.raises(FileNotFoundError):
            RasterMap("/path/to/invalid_raster.tif")

    @pytest.mark.unit
    def test_init_empty_file(self, mocker):
        file_path = "/path/to/empty_raster.tif"
        valid_range = {"min": 0.0, "max": 255.0}
        rules = RasterDataRules.FORBID_ALL_ZEROES
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.path.getsize", return_value=0),
        with pytest.raises(ValueError):
            RasterMap(file_path, valid_range, rules)

    @pytest.mark.unit
    def test_init_invalid_extension(self, mocker):
        file_path = "/path/to/invalid_extension.xyz"
        valid_range = {"min": 0.0, "max": 255.0}
        rules = RasterDataRules.FORBID_ALL_ZEROES
        mocker.patch("os.path.isfile", return_value=True)
        mocker.patch("os.path.getsize", return_value=100)
        with pytest.raises(ValueError):
            RasterMap(file_path, valid_range, rules)
