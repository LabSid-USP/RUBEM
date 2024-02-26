from unittest.mock import MagicMock

import numpy as np
import pytest

from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.raster_map import RasterBand


class TestModelConfiguration:

    valid_config_input = {
        "SIM_TIME": {"start": "01/01/2019", "end": "01/12/2020"},
        "DIRECTORIES": {
            "output": "test_path",
            "etp": "test_path",
            "prec": "test_path",
            "ndvi": "test_path",
            "kp": "test_path",
            "landuse": "test_path",
        },
        "FILENAME_PREFIXES": {
            "etp_prefix": "etp",
            "prec_prefix": "prec",
            "ndvi_prefix": "ndvi",
            "kp_prefix": "kp",
            "landuse_prefix": "cob",
        },
        "RASTERS": {
            "dem": "test_path/test_file.map",
            "clone": "test_path/test_file.map",
            "ndvi_max": "test_path/test_file.map",
            "ndvi_min": "test_path/test_file.map",
            "soil": "test_path/test_file.map",
            "samples": "test_path/test_file.map",
        },
        "TABLES": {
            "rainydays": "test_path/test_file.txt",
            "a_i": "test_path/test_file.txt",
            "a_o": "test_path/test_file.txt",
            "a_s": "test_path/test_file.txt",
            "a_v": "test_path/test_file.txt",
            "manning": "test_path/test_file.txt",
            "bulk_density": "test_path/test_file.txt",
            "k_sat": "test_path/test_file.txt",
            "t_fcap": "test_path/test_file.txt",
            "t_sat": "test_path/test_file.txt",
            "t_wp": "test_path/test_file.txt",
            "rootzone_depth": "test_path/test_file.txt",
            "k_c_min": "test_path/test_file.txt",
            "k_c_max": "test_path/test_file.txt",
            "t_por": "test_path/test_file.txt",
        },
        "GRID": {"grid": 500.0},
        "CALIBRATION": {
            "alpha": 4.5,
            "b": 0.5,
            "w_1": 0.333,
            "w_2": 0.333,
            "w_3": 0.334,
            "rcd": 5.0,
            "f": 0.5,
            "alpha_gw": 0.5,
            "x": 0.5,
        },
        "INITIAL_SOIL_CONDITIONS": {
            "t_ini": 1.0,
            "bfw_ini": 0.1,
            "bfw_lim": 1.0,
            "s_sat_ini": 1.1,
        },
        "CONSTANTS": {"fpar_max": 0.95, "fpar_min": 0.001, "lai_max": 12.0, "i_imp": 2.5},
        "GENERATE_FILE": {
            "itp": True,
            "bfw": True,
            "srn": True,
            "eta": True,
            "lfw": True,
            "rec": True,
            "smc": True,
            "rnf": True,
            "tss": True,
        },
        "RASTER_FILE_FORMAT": {"map_raster_series": True, "tiff_raster_series": True},
    }
    valid_config_ini_content = """
        [SIM_TIME]
        start = 01/01/2019
        end = 01/12/2020
        [DIRECTORIES]
        output = /test_path/
        etp = /test_path/
        prec = /test_path/
        ndvi = /test_path/
        kp = /test_path/
        landuse = /test_path/
        [FILENAME_PREFIXES]
        etp_prefix = etp
        prec_prefix = prec
        ndvi_prefix = ndvi
        kp_prefix = kp
        landuse_prefix = cob
        [RASTERS]
        dem = /test_path/test_file.map
        clone = /test_path/test_file.map
        ndvi_max = /test_path/test_file.map
        ndvi_min = /test_path/test_file.map
        soil = /test_path/test_file.map
        samples = /test_path/test_file.map
        [TABLES]
        rainydays = /test_path/test_file.txt
        a_i = /test_path/test_file.txt
        a_o = /test_path/test_file.txt
        a_s = /test_path/test_file.txt
        a_v = /test_path/test_file.txt
        manning = /test_path/test_file.txt
        bulk_density = /test_path/test_file.txt
        k_sat = /test_path/test_file.txt
        t_fcap = /test_path/test_file.txt
        t_sat = /test_path/test_file.txt
        t_wp = /test_path/test_file.txt
        rootzone_depth = /test_path/test_file.txt
        k_c_min = /test_path/test_file.txt
        k_c_max = /test_path/test_file.txt
        t_por = /test_path/test_file.txt
        [GRID]
        grid = 500.0
        [CALIBRATION]
        alpha = 4.5
        b = 0.5
        w_1 = 0.333
        w_2 = 0.333
        w_3 = 0.334
        rcd = 5.0
        f = 0.5
        alpha_gw = 0.5
        x = 0.5
        [INITIAL_SOIL_CONDITIONS]
        t_ini = 1.0
        bfw_ini = 0.1
        bfw_lim = 1.0
        s_sat_ini = 1.1
        [CONSTANTS]
        fpar_max = 0.95
        fpar_min = 0.001
        lai_max = 12.0
        i_imp = 2.5
        [GENERATE_FILE]
        itp = True
        bfw = True
        srn = True
        eta = True
        lfw = True
        rec = True
        smc = True
        rnf = True
        tss = True
        [RASTER_FILE_FORMAT]
        map_raster_series = True
        tiff_raster_series = True
    """
    valid_config_json_content = """
    {
        "SIM_TIME": {
            "start": "01/01/2019",
            "end": "01/12/2020"
        },
        "DIRECTORIES": {
            "output": "test_path/",
            "etp": "test_path/",
            "prec": "test_path/",
            "ndvi": "test_path/",
            "kp": "test_path/",
            "landuse": "test_path/"
        },
        "FILENAME_PREFIXES": {
            "etp_prefix": "etp",
            "prec_prefix": "prec",
            "ndvi_prefix": "ndvi",
            "kp_prefix": "kp",
            "landuse_prefix": "cob"
        },
        "RASTERS": {
            "dem": "test_path/test_file.map",
            "clone": "test_path/test_file.map",
            "ndvi_max": "test_path/test_file.map",
            "ndvi_min": "test_path/test_file.map",
            "soil": "test_path/test_file.map",
            "samples": "test_path/test_file.map"
        },
        "TABLES": {
            "rainydays": "test_path/test_file.txt",
            "a_i": "test_path/test_file.txt",
            "a_o": "test_path/test_file.txt",
            "a_s": "test_path/test_file.txt",
            "a_v": "test_path/test_file.txt",
            "manning": "test_path/test_file.txt",
            "bulk_density": "test_path/test_file.txt",
            "k_sat": "test_path/test_file.txt",
            "t_fcap": "test_path/test_file.txt",
            "t_sat": "test_path/test_file.txt",
            "t_wp": "test_path/test_file.txt",
            "rootzone_depth": "test_path/test_file.txt",
            "k_c_min": "test_path/test_file.txt",
            "k_c_max": "test_path/test_file.txt",
            "t_por": "test_path/test_file.txt"
        },
        "GRID": {
            "grid": 500.0
        },
        "CALIBRATION": {
            "alpha": 4.5,
            "b": 0.5,
            "w_1": 0.333,
            "w_2": 0.333,
            "w_3": 0.334,
            "rcd": 5.0,
            "f": 0.5,
            "alpha_gw": 0.5,
            "x": 0.5
        },
        "INITIAL_SOIL_CONDITIONS": {
            "t_ini": 1.0,
            "bfw_ini": 0.1,
            "bfw_lim": 1.0,
            "s_sat_ini": 1.1
        },
        "CONSTANTS": {
            "fpar_max": 0.95,
            "fpar_min": 0.001,
            "lai_max": 12.0,
            "i_imp": 2.5
        },
        "GENERATE_FILE": {
            "itp": true,
            "bfw": true,
            "srn": true,
            "eta": true,
            "lfw": true,
            "rec": true,
            "smc": true,
            "rnf": true,
            "tss": true
        },
        "RASTER_FILE_FORMAT": {
            "map_raster_series": true,
            "tiff_raster_series": true
        }
    }    
    """

    @pytest.fixture(autouse=True)
    def setup(self, fs):
        fs.create_file("/test_path/test_file.map", contents="42")
        fs.create_file("/test_path/test_file.tif", contents="42")
        fs.create_file("/test_path/test_file.txt", contents="42")
        fs.create_file("/test_path/etp00000.001", contents="42")
        fs.create_file("/test_path/prec0000.001", contents="42")
        fs.create_file("/test_path/ndvi0000.001", contents="42")
        fs.create_file("/test_path/kp000000.001", contents="42")
        fs.create_file("/test_path/cob00000.001", contents="42")

    @pytest.mark.unit
    def test_init_with_dictionary(self, mocker):
        band_mock = MagicMock(spec=RasterBand)
        band_mock.no_data_value = -9999
        band_mock.data_array = np.ones((3, 3))
        mocker.patch("osgeo.gdal.OpenEx")
        mocker.patch("osgeo.gdal.GetDataTypeName")
        mocker.patch("os.path.getsize", return_value=100)
        mocker.patch("rubem.configuration.raster_map.RasterBand", return_value=band_mock)
        _ = ModelConfiguration(self.valid_config_input)

    @pytest.mark.unit
    def test_init_with_dictionary_optional_ldd(self, mocker):
        band_mock = MagicMock(spec=RasterBand)
        band_mock.no_data_value = -9999
        band_mock.data_array = np.ones((3, 3))
        mocker.patch("osgeo.gdal.OpenEx")
        mocker.patch("osgeo.gdal.GetDataTypeName")
        mocker.patch("os.path.getsize", return_value=100)
        mocker.patch("rubem.configuration.raster_map.RasterBand", return_value=band_mock)
        input_dict = self.valid_config_input.copy()
        input_dict["RASTERS"]["ldd"] = "test_path/test_file.map"
        _ = ModelConfiguration(input_dict)

    @pytest.mark.unit
    def test_init_with_dictionary_optional_samples(self, mocker):
        band_mock = MagicMock(spec=RasterBand)
        band_mock.no_data_value = -9999
        band_mock.data_array = np.ones((3, 3))
        mocker.patch("osgeo.gdal.OpenEx")
        mocker.patch("osgeo.gdal.GetDataTypeName")
        mocker.patch("os.path.getsize", return_value=100)
        mocker.patch("rubem.configuration.raster_map.RasterBand", return_value=band_mock)
        input_dict = self.valid_config_input.copy()
        input_dict["RASTERS"]["samples"] = None
        _ = ModelConfiguration(input_dict)

    @pytest.mark.unit
    def test_init_with_empty_dictionary(self):
        with pytest.raises(Exception):
            _ = ModelConfiguration({})

    @pytest.mark.unit
    def test_init_with_invalid_dictionary(self):
        with pytest.raises(Exception):
            _ = ModelConfiguration({"invalid": "invalid"})

    @pytest.mark.unit
    def test_init_with_incomplete_dictionary(self):
        with pytest.raises(Exception):
            _ = ModelConfiguration({"SIM_TIME": {"start": "01/01/2019", "end": "01/12/2020"}})

    @pytest.mark.unit
    def test_init_with_ini_file(self, fs, mocker):
        band_mock = MagicMock(spec=RasterBand)
        band_mock.no_data_value = -9999
        band_mock.data_array = np.ones((3, 3))
        fs.create_file(
            "/test_path/config.ini",
            contents=self.valid_config_ini_content,
        )
        mocker.patch("osgeo.gdal.OpenEx")
        mocker.patch("osgeo.gdal.GetDataTypeName")
        mocker.patch("os.path.getsize", return_value=100)
        mocker.patch("rubem.configuration.raster_map.RasterBand", return_value=band_mock)
        _ = ModelConfiguration("/test_path/config.ini")

    @pytest.mark.unit
    def test_init_with_not_existent_ini_file(self):
        with pytest.raises(Exception):
            _ = ModelConfiguration("/test_path/config.ini")

    @pytest.mark.unit
    def test_init_with_empty_ini_file(self, fs):
        fs.create_file("/test_path/config.ini")
        with pytest.raises(Exception):
            _ = ModelConfiguration("/test_path/config.ini")

    @pytest.mark.unit
    def test_init_with_invalid_ini_file(self, fs):
        fs.create_file("/test_path/config.ini", contents="invalid")
        with pytest.raises(Exception):
            _ = ModelConfiguration("/test_path/config.ini")

    @pytest.mark.unit
    def test_init_with_incomplete_ini_file(self, fs):
        fs.create_file(
            "/test_path/config.ini",
            contents="[SIM_TIME]\nstart = 01/01/2019\nend = 01/12/2020",
        )
        with pytest.raises(Exception):
            _ = ModelConfiguration("/test_path/config.ini")

    @pytest.mark.unit
    def test_init_with_json_file(self, fs, mocker):
        band_mock = MagicMock(spec=RasterBand)
        band_mock.no_data_value = -9999
        band_mock.data_array = np.ones((3, 3))
        fs.create_file(
            "/test_path/config.json",
            contents=self.valid_config_json_content,
        )
        mocker.patch("osgeo.gdal.OpenEx")
        mocker.patch("osgeo.gdal.GetDataTypeName")
        mocker.patch("os.path.getsize", return_value=100)
        mocker.patch("rubem.configuration.raster_map.RasterBand", return_value=band_mock)
        _ = ModelConfiguration("/test_path/config.json")

    @pytest.mark.unit
    def test_init_with_not_existent_json_file(self):
        with pytest.raises(Exception):
            _ = ModelConfiguration("/test_path/config.json")

    @pytest.mark.unit
    def test_init_with_empty_json_file(self, fs):
        fs.create_file("/test_path/config.json")
        with pytest.raises(Exception):
            _ = ModelConfiguration("/test_path/config.json")

    @pytest.mark.unit
    def test_init_with_invalid_json_file(self, fs):
        fs.create_file("/test_path/config.json", contents="invalid")
        with pytest.raises(Exception):
            _ = ModelConfiguration("/test_path/config.json")

    @pytest.mark.unit
    def test_init_with_incomplete_json_file(self, fs):
        fs.create_file(
            "/test_path/config.json",
            contents='{"SIM_TIME": {"start": "01/01/2019", "end": "01/12/2020"}}',
        )
        with pytest.raises(Exception):
            _ = ModelConfiguration("/test_path/config.json")
