import os
import unittest

from tests.utils import parentDirUpdate, removeFile, removeDirectory
from rubem.core import Model


class ModelConstructorTest(unittest.TestCase):
    """Test model constructor"""

    def setUp(self):
        """Runs before each test."""

        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        self.templateBaseProject = os.path.join(
            self.currentDir, "fixtures/base.template"
        )
        self.baseProjectFile = os.path.join(self.currentDir, "fixtures/base.ini")
        if not os.path.exists(self.baseProjectFile):
            parentDirUpdate(
                template=self.templateBaseProject,
                tag="{PARENT_DIR}",
                target=self.baseProjectFile,
                currentDir=self.currentDir,
            )

        self.baseProjectOutputDir = os.path.join(self.currentDir, "fixtures/base/out")
        if not os.path.exists(self.baseProjectOutputDir):
            os.mkdir(self.baseProjectOutputDir)

        self.configDict = {
            "SIM_TIME": {"start": "01/01/2000", "end": "01/02/2000"},
            "DIRECTORIES": {
                "input": self.currentDir + "/fixtures/base/",
                "output": self.currentDir + "/fixtures/base/out/",
                "etp": self.currentDir + "/fixtures/base/maps/etp/",
                "prec": self.currentDir + "/fixtures/base/maps/rain/",
                "ndvi": self.currentDir + "/fixtures/base/maps/ndvi/",
                "kp": self.currentDir + "/fixtures/base/maps/kp/",
                "landuse": self.currentDir + "/fixtures/base/maps/ldcover/",
            },
            "FILENAME_PREFIXES": {
                "etp_prefix": "etp",
                "prec_prefix": "prec",
                "ndvi_prefix": "ndvi",
                "kp_prefix": "kp",
                "landuse_prefix": "cob",
            },
            "RASTERS": {
                "dem": self.currentDir + "/fixtures/base/maps/dem/dem.map",
                "demtif": self.currentDir + "/fixtures/base/maps/dem/dem.tif",
                "clone": self.currentDir + "/fixtures/base/maps/clone/clone.map",
                "ndvi_max": self.currentDir + "/fixtures/base/maps/ndvi/ndvi_max.map",
                "ndvi_min": self.currentDir + "/fixtures/base/maps/ndvi/ndvi_min.map",
                "soil": self.currentDir + "/fixtures/base/maps/soil/soil.map",
                "samples": self.currentDir + "/fixtures/base/maps/samples/samples.map",
            },
            "TABLES": {
                "rainydays": self.currentDir + "/fixtures/base/txt/rainydays.txt",
                "a_i": self.currentDir + "/fixtures/base/txt/ldcover/a_i.txt",
                "a_o": self.currentDir + "/fixtures/base/txt/ldcover/a_o.txt",
                "a_s": self.currentDir + "/fixtures/base/txt/ldcover/a_s.txt",
                "a_v": self.currentDir + "/fixtures/base/txt/ldcover/a_v.txt",
                "manning": self.currentDir + "/fixtures/base/txt/ldcover/manning.txt",
                "bulk_density": self.currentDir + "/fixtures/base/txt/soil/dg.txt",
                "k_sat": self.currentDir + "/fixtures/base/txt/soil/Kr.txt",
                "t_fcap": self.currentDir + "/fixtures/base/txt/soil/Tcc.txt",
                "t_sat": self.currentDir + "/fixtures/base/txt/soil/Tsat.txt",
                "t_wp": self.currentDir + "/fixtures/base/txt/soil/Tw.txt",
                "rootzone_depth": self.currentDir + "/fixtures/base/txt/soil/Zr.txt",
                "k_c_min": self.currentDir + "/fixtures/base/txt/ldcover/kcmin.txt",
                "k_c_max": self.currentDir + "/fixtures/base/txt/ldcover/kcmax.txt",
                "t_por": self.currentDir + "/fixtures/base/txt/soil/Tpor.txt",
            },
            "GRID": {"grid": "500.0"},
            "CALIBRATION": {
                "alpha": "4.5",
                "b": "0.5",
                "w_1": "0.333",
                "w_2": "0.333",
                "w_3": "0.334",
                "rcd": "5.0",
                "f": "0.5",
                "alpha_gw": "0.5",
                "x": "0.5",
            },
            "INITIAL_SOIL_CONDITIONS": {
                "t_ini": "1.0",
                "bfw_ini": "0.1",
                "bfw_lim": "1.0",
                "s_sat_ini": "1.0",
            },
            "CONSTANTS": {
                "fpar_max": "0.95",
                "fpar_min": "0.001",
                "lai_max": "12.0",
                "i_imp": "2.5",
            },
            "GENERATE_FILE": {
                "itp": "True",
                "bfw": "True",
                "srn": "True",
                "eta": "True",
                "lfw": "True",
                "rec": "True",
                "smc": "True",
                "rnf": "True",
                "tss": "True",
            },
            "RASTER_FILE_FORMAT": {
                "map_raster_series": "True",
                "tiff_raster_series": "True",
            },
        }
        self.validConfigSections = [
            "SIM_TIME",
            "DIRECTORIES",
            "FILENAME_PREFIXES",
            "RASTERS",
            "TABLES",
            "GRID",
            "CALIBRATION",
            "INITIAL_SOIL_CONDITIONS",
            "CONSTANTS",
            "GENERATE_FILE",
            "RASTER_FILE_FORMAT",
        ]

    def tearDown(self):
        """Runs after each test."""
        removeFile(self.baseProjectFile)
        removeDirectory(self.baseProjectOutputDir)

    def test_config_ini_file(self):
        """Test we can read a model configuration file"""
        model = Model.load(self.baseProjectFile)
        self.assertListEqual(model.config.sections(), self.validConfigSections)

    def test_non_existent_config_ini_file(self):
        """Test we can't read a non existent model configuration file"""
        self.assertRaises(FileNotFoundError, Model.load, self.currentDir + "/fake.ini")

    def test_config_dict(self):
        """Test we can read a model configuration dictionary"""
        model = Model.load(self.configDict)
        self.assertListEqual(model.config.sections(), self.validConfigSections)

    def test_empty_config_dict(self):
        """Test we can't read an empty model configuration dictionary"""
        self.assertRaises(ValueError, Model.load, {})

    def test_empty_config_list(self):
        """Test we can't read an empty model configuration list"""
        self.assertRaises(Exception, Model.load, [])


if __name__ == "__main__":
    suite = unittest.makeSuite(ModelConstructorTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
