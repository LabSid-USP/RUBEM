import json
import os
import subprocess
import tempfile

import pytest


class TestCliApp:

    test_data_dir = os.path.join(os.path.dirname(__file__), os.path.pardir)
    config = {
        "SIM_TIME": {"start": "01/01/2000", "end": "01/03/2000"},
        "DIRECTORIES": {
            "output": None,
            "etp": f"{test_data_dir}/fixtures/base/maps/etp/",
            "prec": f"{test_data_dir}/fixtures/base/maps/rain/",
            "ndvi": f"{test_data_dir}/fixtures/base/maps/ndvi/",
            "kp": f"{test_data_dir}/fixtures/base/maps/kp/",
            "landuse": f"{test_data_dir}/fixtures/base/maps/lulc/",
        },
        "FILENAME_PREFIXES": {
            "etp_prefix": "etp",
            "prec_prefix": "prec",
            "ndvi_prefix": "ndvi",
            "kp_prefix": "kp",
            "landuse_prefix": "cob",
        },
        "RASTERS": {
            "dem": f"{test_data_dir}/fixtures/base/maps/dem/dem.map",
            "clone": f"{test_data_dir}/fixtures/base/maps/clone/clone.map",
            "ndvi_max": f"{test_data_dir}/fixtures/base/maps/ndvi/ndvi_max.map",
            "ndvi_min": f"{test_data_dir}/fixtures/base/maps/ndvi/ndvi_min.map",
            "soil": f"{test_data_dir}/fixtures/base/maps/soil/soil.map",
            "samples": f"{test_data_dir}/fixtures/base/maps/samples/samples.map",
        },
        "TABLES": {
            "rainydays": f"{test_data_dir}/fixtures/base/txt/rainydays.txt",
            "a_i": f"{test_data_dir}/fixtures/base/txt/lulc/a_i.txt",
            "a_o": f"{test_data_dir}/fixtures/base/txt/lulc/a_o.txt",
            "a_s": f"{test_data_dir}/fixtures/base/txt/lulc/a_s.txt",
            "a_v": f"{test_data_dir}/fixtures/base/txt/lulc/a_v.txt",
            "manning": f"{test_data_dir}/fixtures/base/txt/lulc/manning.txt",
            "bulk_density": f"{test_data_dir}/fixtures/base/txt/soil/dg.txt",
            "k_sat": f"{test_data_dir}/fixtures/base/txt/soil/Tsat.txt",
            "t_fcap": f"{test_data_dir}/fixtures/base/txt/soil/Tcc.txt",
            "t_sat": f"{test_data_dir}/fixtures/base/txt/soil/Tsat.txt",
            "t_wp": f"{test_data_dir}/fixtures/base/txt/soil/Tw.txt",
            "rootzone_depth": f"{test_data_dir}/fixtures/base/txt/soil/Zr.txt",
            "k_c_min": f"{test_data_dir}/fixtures/base/txt/lulc/kcmin.txt",
            "k_c_max": f"{test_data_dir}/fixtures/base/txt/lulc/kcmax.txt",
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
            "arn": True,
            "tss": True,
        },
        "RASTER_FILE_FORMAT": {"map_raster_series": True, "tiff_raster_series": True},
    }

    @pytest.mark.integration
    def test_cli_app_help_ext(self):
        result = subprocess.check_output(["python", "rubem", "--help"])
        assert b"usage: rubem [-h] -c CONFIGFILE [-V] [-s]" in result

    @pytest.mark.integration
    def test_cli_app_help_short(self):
        result = subprocess.check_output(["python", "rubem", "-h"])
        assert b"usage: rubem [-h] -c CONFIGFILE [-V] [-s]" in result

    @pytest.mark.integration
    def test_cli_app_version_ext(self):
        result = subprocess.check_output(["python", "rubem", "--version"])
        assert b"RUBEM v" in result

    @pytest.mark.integration
    def test_cli_app_version_short(self):
        result = subprocess.check_output(["python", "rubem", "-V"])
        assert b"RUBEM v" in result

    @pytest.mark.integration
    def test_cli_app_no_args(self):
        with pytest.raises(subprocess.CalledProcessError):
            subprocess.check_output(["python", "rubem"])

    @pytest.mark.integration
    def test_cli_app_invalid_args(self):
        with pytest.raises(subprocess.CalledProcessError):
            subprocess.check_output(["python", "rubem", "-c", "invalid_path"])

    @pytest.mark.integration
    def test_cli_app_not_a_file_config(self):
        with pytest.raises(subprocess.CalledProcessError):
            subprocess.check_output(["python", "rubem", "-c", os.path.dirname(__file__)])

    @pytest.mark.integration
    def test_cli_app_invalid_extension_config_json_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(
                file=os.path.join(temp_dir, "bagheera.jaguar"), mode="w", encoding="utf8"
            ) as f:
                f.write(json.dumps(self.config))

            with pytest.raises(subprocess.CalledProcessError):
                subprocess.check_output(
                    ["python", "rubem", "-c", os.path.join(temp_dir, "bagheera.jaguar")]
                )

    @pytest.mark.integration
    def test_cli_app_invalid_config_json_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(file=os.path.join(temp_dir, "config.json"), mode="w", encoding="utf8") as f:
                f.write("invalid_json")

            with pytest.raises(subprocess.CalledProcessError):
                subprocess.check_output(
                    ["python", "rubem", "-c", os.path.join(temp_dir, "config.json")]
                )

    @pytest.mark.integration
    def test_cli_app_empty_config_json_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(file=os.path.join(temp_dir, "config.json"), mode="w", encoding="utf8") as f:
                f.write(json.dumps({}))

            with pytest.raises(subprocess.CalledProcessError):
                subprocess.check_output(
                    ["python", "rubem", "-c", os.path.join(temp_dir, "config.json")]
                )

    @pytest.mark.integration
    def test_cli_app_valid_config_json_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.config["DIRECTORIES"]["output"] = temp_dir
            with open(file=os.path.join(temp_dir, "config.json"), mode="w", encoding="utf8") as f:
                f.write(json.dumps(self.config))

            subprocess.check_output(
                ["python", "rubem", "-c", os.path.join(temp_dir, "config.json")]
            )

            assert os.path.exists(os.path.join(temp_dir, "itp00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "itp00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "itp00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "bfw00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "bfw00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "bfw00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "srn00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "srn00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "srn00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "eta00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "eta00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "eta00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "lfw00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "lfw00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "lfw00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "rec00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "rec00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "rec00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "smc00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "smc00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "smc00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "rnf00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "rnf00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "rnf00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "arn00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "arn00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "arn00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "tss_itp.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_bfw.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_srn.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_eta.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_lfw.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_rec.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_smc.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_rnf.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_arn.csv"))

    @pytest.mark.integration
    def test_cli_app_skip_input_data_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.config["DIRECTORIES"]["output"] = temp_dir
            with open(file=os.path.join(temp_dir, "config.json"), mode="w", encoding="utf8") as f:
                f.write(json.dumps(self.config))

            subprocess.check_output(
                ["python", "rubem", "-s", "-c", os.path.join(temp_dir, "config.json")]
            )

            assert os.path.exists(os.path.join(temp_dir, "itp00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "itp00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "itp00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "bfw00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "bfw00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "bfw00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "srn00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "srn00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "srn00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "eta00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "eta00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "eta00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "lfw00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "lfw00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "lfw00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "rec00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "rec00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "rec00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "smc00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "smc00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "smc00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "rnf00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "rnf00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "rnf00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "arn00000.001"))
            assert os.path.exists(os.path.join(temp_dir, "arn00000.002"))
            assert os.path.exists(os.path.join(temp_dir, "arn00000.003"))
            assert os.path.exists(os.path.join(temp_dir, "tss_itp.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_bfw.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_srn.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_eta.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_lfw.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_rec.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_smc.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_rnf.csv"))
            assert os.path.exists(os.path.join(temp_dir, "tss_arn.csv"))
