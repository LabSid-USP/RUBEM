import os
import tempfile
from configparser import ConfigParser
import unittest

from tests.utils import removeDirectory, parentDirUpdate

from rubem.validation._validators import *


class FilePathArgValidatorTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        self.tempDir = tempfile.mkdtemp()
        self.fakeFile = os.path.join(self.tempDir, "fake.ini")
        self.tmpFile = tempfile.NamedTemporaryFile(
            suffix=".ini", dir=self.tempDir
        )

    def tearDown(self):
        """Runs after each test."""
        removeDirectory(self.tempDir)

    def test_filePathArgValidator_file_path_not_exists(self):
        """"""
        with self.assertRaises(argparse.ArgumentTypeError) as cm:
            filePathArgValidator(self.fakeFile)
        self.assertEqual(
            f'model config file "{self.fakeFile}" does not exists',
            str(cm.exception),
        )

    def test_filePathArgValidator_dir_path_as_arg(self):
        """"""
        with self.assertRaises(argparse.ArgumentTypeError) as cm:
            filePathArgValidator(self.tempDir)
        self.assertEqual(
            f'model config file "{self.tempDir}" is not a valid file',
            str(cm.exception),
        )

    def test_filePathArgValidator_valid_path_arg(self):
        """"""
        result = filePathArgValidator(self.tmpFile.name)
        self.assertEqual(self.tmpFile.name, result)

    def test_filePathArgValidator_empty_path_arg(self):
        """"""
        with self.assertRaises(Exception) as cm:
            filePathArgValidator(None)
        self.assertIn(
            "path should be string, bytes, os.PathLike or integer, not"
            " NoneType",
            str(cm.exception),
        )


class DateValidatorTest(unittest.TestCase):
    """[summary]"""

    @unittest.expectedFailure
    def test_dateValidator(self):
        """"""
        config = ConfigParser()
        config["SIM_TIME"] = {"start": "01/01/2000", "end": "01/02/2000"}
        self.assertRaises(Exception, dateValidator, config)

    def test_dateValidator_other_date_format(self):
        """"""
        config = ConfigParser()
        config["SIM_TIME"] = {"start": "2000/01/01", "end": "2000/01/02"}
        with self.assertRaises(Exception) as cm:
            dateValidator(config)
        self.assertEqual(
            "Incorrect SIM_TIME:start date string format. It should be"
            " DD/MM/YYYY",
            str(cm.exception),
        )

    def test_dateValidator_empty_date(self):
        """"""
        config = ConfigParser()
        config["SIM_TIME"] = {"start": "01/01/2000", "end": ""}
        with self.assertRaises(Exception) as cm:
            dateValidator(config)
        self.assertEqual(
            "Incorrect SIM_TIME:end date string format. It should be"
            " DD/MM/YYYY",
            str(cm.exception),
        )


class FileSeriesNamesValidatorTest(unittest.TestCase):
    @unittest.expectedFailure
    def test_fileNamePrefixValidator_valid_input(self):
        """"""
        config = ConfigParser()
        config["FILENAME_PREFIXES"] = {
            "etp_prefix": "etp",
            "prec_prefix": "prec",
            "ndvi_prefix": "ndvi",
            "kp_prefix": "kp",
            "landuse_prefix": "cob",
        }
        self.assertRaises(Exception, fileNamePrefixValidator, config)

    def test_fileNamePrefixValidator_invalid_prec_prefix(self):
        """"""
        config = ConfigParser()
        config["FILENAME_PREFIXES"] = {
            "etp_prefix": "etp",
            "prec_prefix": "precprecprecprec",
            "ndvi_prefix": "ndvi",
            "kp_prefix": "kp",
            "landuse_prefix": "cob",
        }
        with self.assertRaises(Exception) as cm:
            fileNamePrefixValidator(config)
        self.assertEqual(
            "Invalid filename prefix length"
            " FILENAME_PREFIXES:prec_prefix:precprecprecprec",
            str(cm.exception),
        )

    def test_fileNamePrefixValidator_empty_prec_prefix(self):
        """"""
        config = ConfigParser()
        config["FILENAME_PREFIXES"] = {
            "etp_prefix": "etp",
            "prec_prefix": "",
            "ndvi_prefix": "ndvi",
            "kp_prefix": "kp",
            "landuse_prefix": "cob",
        }
        with self.assertRaises(Exception) as cm:
            fileNamePrefixValidator(config)
        self.assertEqual(
            "Invalid filename prefix length FILENAME_PREFIXES:prec_prefix:",
            str(cm.exception),
        )


class FilePathValidatorTest(unittest.TestCase):
    def setUp(self):
        """Runs before each test."""

        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        self.tempDir = tempfile.mkdtemp()
        self.templateBaseProject = os.path.join(
            self.currentDir, "fixtures/base4.template"
        )

        self.baseProjectFile = os.path.join(self.tempDir, "base.ini")
        if not os.path.exists(self.baseProjectFile):
            parentDirUpdate(
                template=self.templateBaseProject,
                tags=["{PARENT_DIR}", "{TEMP_DIR}"],
                target=self.baseProjectFile,
                dirs=[self.currentDir, self.tempDir],
            )

        self.baseProjectOutputDir = os.path.join(self.tempDir, "out")
        if not os.path.exists(self.baseProjectOutputDir):
            os.mkdir(self.baseProjectOutputDir)

        self.config = ConfigParser()
        self.config.read(self.baseProjectFile)

    def tearDown(self):
        """Runs after each test."""
        removeDirectory(self.tempDir)

    @unittest.expectedFailure
    def test_filePathValidator_valid_input(self):
        """"""
        self.assertRaises(Exception, filePathValidator, self.config)

    def test_filePathValidator_dem_file_not_exists(self):
        """"""
        demPath = os.path.join(
            self.currentDir, "fixtures/base/maps/dem/dem.mappp"
        )
        self.config["RASTERS"] = {"dem": demPath}
        with self.assertRaises(Exception) as cm:
            filePathValidator(self.config)
        self.assertEqual(
            f"RASTERS:dem:{demPath} does not exists", str(cm.exception)
        )

    def test_filePathValidator_rainydays_file_as_dir(self):
        """"""
        rainydaysPath = os.path.join(self.currentDir, "fixtures/base/txt")
        self.config["TABLES"] = {"rainydays": rainydaysPath}
        with self.assertRaises(Exception) as cm:
            filePathValidator(self.config)
        self.assertEqual(
            f"TABLES:rainydays:{rainydaysPath} is not a valid file",
            str(cm.exception),
        )


class DirectoryPathValidatorTest(unittest.TestCase):
    def setUp(self):
        """Runs before each test."""

        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        self.tempDir = tempfile.mkdtemp()
        self.templateBaseProject = os.path.join(
            self.currentDir, "fixtures/base5.template"
        )
        self.baseProjectFile = os.path.join(self.tempDir, "base.ini")
        if not os.path.exists(self.baseProjectFile):
            parentDirUpdate(
                template=self.templateBaseProject,
                tags=["{PARENT_DIR}", "{TEMP_DIR}"],
                target=self.baseProjectFile,
                dirs=[self.currentDir, self.tempDir],
            )

        self.baseProjectOutputDir = os.path.join(self.tempDir, "out")
        if not os.path.exists(self.baseProjectOutputDir):
            os.mkdir(self.baseProjectOutputDir)

        self.config = ConfigParser()
        self.config.read(self.baseProjectFile)

    def tearDown(self):
        """Runs after each test."""
        removeDirectory(self.tempDir)

    @unittest.expectedFailure
    def test_directoryPathValidator(self):
        """"""
        self.assertRaises(Exception, directoryPathValidator, self.config)

    def test_directoryPathValidator_invalid_kp_dir(self):
        kpPath = os.path.join(self.currentDir, "fixtures/base/maps/kpppppp")
        self.config["DIRECTORIES"] = {"kp": kpPath}
        with self.assertRaises(Exception) as cm:
            directoryPathValidator(self.config)
        self.assertEqual(
            f"DIRECTORIES:kp:{kpPath} does not exists", str(cm.exception)
        )

    def test_directoryPathValidator_etp_dir_as_file(self):
        etpPath = os.path.join(
            self.currentDir, "fixtures/base/maps/etp/etp00000.001"
        )
        self.config["DIRECTORIES"] = {"etp": etpPath}
        with self.assertRaises(Exception) as cm:
            directoryPathValidator(self.config)
        self.assertEqual(
            f"DIRECTORIES:etp:{etpPath} is not a valid directory",
            str(cm.exception),
        )


class DataTypeValidatorTest(unittest.TestCase):
    def setUp(self):
        self.config = ConfigParser()
        self.config.read_dict(
            {
                "GRID": {"grid": "500.00"},
                "CALIBRATION": {
                    "alpha": "4.500",
                    "b": "0.500",
                    "w_1": "0.333",
                    "w_2": "0.333",
                    "w_3": "0.334",
                    "rcd": "5.000",
                    "f": "0.500",
                    "alpha_gw": "0.500",
                    "x": "0.500",
                },
                "INITIAL_SOIL_CONDITIONS": {
                    "T_ini": "1.000",
                    "bfw_ini": "0.100",
                    "bfw_lim": "1.000",
                    "S_sat_ini": "1.000",
                },
                "CONSTANTS": {
                    "fpar_max": "0.950",
                    "fpar_min": "0.001",
                    "lai_max": "12.000",
                    "i_imp": "2.500",
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
                    "tss": "False",
                },
                "RASTER_FILE_FORMAT": {
                    "map_raster_series": "True",
                    "tiff_raster_series": "True",
                },
            }
        )

    @unittest.expectedFailure
    def test_floatTypeValidator(self):
        """"""
        self.assertRaises(Exception, floatTypeValidator, self.config)

    def test_floatTypeValidator_validator_grid_empty(self):
        self.config["GRID"] = {"grid": ""}
        with self.assertRaises(ValidationException) as cm:
            floatTypeValidator(self.config)
        self.assertEqual(
            "GRID:grid does not contain a valid float value",
            str(cm.exception),
        )

    def test_floatTypeValidator_grid_alphanumeric_str(self):
        self.config["GRID"] = {"grid": "efg500.00abcd"}
        with self.assertRaises(ValidationException) as cm:
            floatTypeValidator(self.config)
        self.assertEqual(
            "GRID:grid does not contain a valid float value",
            str(cm.exception),
        )

    @unittest.expectedFailure
    def test_booleanTypeValidator(self):
        """"""
        self.assertRaises(Exception, booleanTypeValidator, self.config)

    def test_booleanTypeValidator_generatefile_empty_itp(self):
        self.config["GENERATE_FILE"] = {"itp": ""}
        with self.assertRaises(ValidationException) as cm:
            booleanTypeValidator(self.config)
        self.assertEqual(
            "GENERATE_FILE:itp does not contain a valid boolean value",
            str(cm.exception),
        )

    def test_booleanTypeValidator_generatefile_int_itp(self):
        self.config["GENERATE_FILE"] = {"itp": "42"}
        with self.assertRaises(ValidationException) as cm:
            booleanTypeValidator(self.config)
        self.assertEqual(
            "GENERATE_FILE:itp does not contain a valid boolean value",
            str(cm.exception),
        )


class ValueRangeValidatorTest(unittest.TestCase):
    def setUp(self):
        self.config = ConfigParser()
        self.config.read_dict(
            {
                "GRID": {"grid": "500.00"},
                "CALIBRATION": {
                    "alpha": "4.500",
                    "b": "0.500",
                    "w_1": "0.333",
                    "w_2": "0.333",
                    "w_3": "0.334",
                    "rcd": "5.000",
                    "f": "0.500",
                    "alpha_gw": "0.500",
                    "x": "0.500",
                },
                "INITIAL_SOIL_CONDITIONS": {
                    "T_ini": "1.000",
                    "bfw_ini": "0.100",
                    "bfw_lim": "1.000",
                    "S_sat_ini": "1.000",
                },
                "CONSTANTS": {
                    "fpar_max": "0.950",
                    "fpar_min": "0.001",
                    "lai_max": "12.000",
                    "i_imp": "2.500",
                },
            }
        )

    def test_value_range_validator_calibration_alpha_gt_max_value(self):
        self.config["CALIBRATION"] = {"alpha": "10.942"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Interception Parameter (alpha) value must be in the value"
            " range [0.01, 10.0]",
            str(cm.exception),
        )

    def test_value_range_validator_calibration_alpha_lt_min_value(self):
        self.config["CALIBRATION"] = {"alpha": "0.000001"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Interception Parameter (alpha) value must be in the value"
            " range [0.01, 10.0]",
            str(cm.exception),
        )

    def test_value_range_validator_calibration_b_gt_max_value(self):
        self.config["CALIBRATION"] = {"b": "1.555"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Rainfall Intensity Coefficient (b) value must be in the value"
            " range [0.01, 1.0]",
            str(cm.exception),
        )

    def test_value_range_validator_calibration_b_lt_min_value(self):
        self.config["CALIBRATION"] = {"b": "0.0000001"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Rainfall Intensity Coefficient (b) value must be in the value"
            " range [0.01, 1.0]",
            str(cm.exception),
        )

    def test_value_range_validator_calibration_RCD_gt_max_value(self):
        self.config["CALIBRATION"] = {"rcd": "10.333"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Regional Consecutive Dryness Level (rcd) value must be in the"
            " value range [1.0, 10.0]",
            str(cm.exception),
        )

    def test_value_range_validator_calibration_RCD_lt_min_value(self):
        self.config["CALIBRATION"] = {"rcd": "0.9955"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Regional Consecutive Dryness Level (rcd) value must be in the"
            " value range [1.0, 10.0]",
            str(cm.exception),
        )

    def test_value_range_validator_calibration_f_gt_max_value(self):
        self.config["CALIBRATION"] = {"f": "1.133"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Flow Direction Factor (f) value must be in the value range"
            " [0.01, 1.0]",
            str(cm.exception),
        )

    def test_value_range_validator_calibration_f_lt_min_value(self):
        self.config["CALIBRATION"] = {"f": "0.0000001"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Flow Direction Factor (f) value must be in the value range"
            " [0.01, 1.0]",
            str(cm.exception),
        )

    def test_value_range_validator_calibration_alphagw_gt_max_value(self):
        self.config["CALIBRATION"] = {"alpha_gw": "1.122"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Baseflow Recession Coefficient (alpha_gw) value must be in"
            " the value range [0.01, 1.0]",
            str(cm.exception),
        )

    def test_value_range_validator_calibration_alphagw_lt_min_value(self):
        self.config["CALIBRATION"] = {"alpha_gw": "0.000001"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Baseflow Recession Coefficient (alpha_gw) value must be in"
            " the value range [0.01, 1.0]",
            str(cm.exception),
        )

    def test_value_range_validator_calibration_x_gt_max_value(self):
        self.config["CALIBRATION"] = {"x": "1.111"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Flow Recession Coefficient (x) value must be in the value"
            " range [0.0, 1.0]",
            str(cm.exception),
        )

    def test_value_range_validator_calibration_x_lt_min_value(self):
        self.config["CALIBRATION"] = {"x": "-0.01"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Flow Recession Coefficient (x) value must be in the value"
            " range [0.0, 1.0]",
            str(cm.exception),
        )

    def test_value_range_validator_constants_laimax_gt_max_value(self):
        self.config["CONSTANTS"] = {"lai_max": "12.56565"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Maximum Leaf Area Index (lai_max) value must be in the value"
            " range [1.0, 12.0]",
            str(cm.exception),
        )

    def test_value_range_validator_constants_laimax_lt_min_value(self):
        self.config["CONSTANTS"] = {"lai_max": "0.9242"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Maximum Leaf Area Index (lai_max) value must be in the value"
            " range [1.0, 12.0]",
            str(cm.exception),
        )

    def test_value_range_validator_constants_impervint_gt_max_value(self):
        self.config["CONSTANTS"] = {"i_imp": "3.7897"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Impervious Area Interception (i_imp) value must be in the"
            " value range [1.0, 3.0]",
            str(cm.exception),
        )

    def test_value_range_validator_constants_impervint_lt_min_value(self):
        self.config["CONSTANTS"] = {"i_imp": "0.9242"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Impervious Area Interception (i_imp) value must be in the"
            " value range [1.0, 3.0]",
            str(cm.exception),
        )

    def test_value_range_validator_constants_fparmax_gt_max_value(self):
        self.config["CONSTANTS"] = {"fpar_max": "1.0112"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Maximum Fraction Photosynthetically Active Radiation"
            " (fpar_max) value must be in the value range [0.0, 1.0]",
            str(cm.exception),
        )

    def test_value_range_validator_constants_fparmax_lt_min_value(self):
        self.config["CONSTANTS"] = {"fpar_max": "-0.01"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Maximum Fraction Photosynthetically Active Radiation"
            " (fpar_max) value must be in the value range [0.0, 1.0]",
            str(cm.exception),
        )

    def test_value_range_validator_constants_fparmin_gt_max_value(self):
        self.config["CONSTANTS"] = {"fpar_min": "1.1102"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Minimum Fraction Photosynthetically Active Radiation"
            " (fpar_min) value must be in the value range [0.0, 1.0]",
            str(cm.exception),
        )

    def test_value_range_validator_constants_fparmin_lt_min_value(self):
        self.config["CONSTANTS"] = {"fpar_min": "-0.01"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual(
            "The Minimum Fraction Photosynthetically Active Radiation"
            " (fpar_min) value must be in the value range [0.0, 1.0]",
            str(cm.exception),
        )

    @unittest.skip("Pending collection of valid value range info")
    def test_value_range_validator_initialsoilcond_ssatini_gt_max_value(self):
        self.config["INITIAL_SOIL_CONDITIONS"] = {"s_sat_ini": "1.112"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual("", str(cm.exception))

    @unittest.skip("Pending collection of valid value range info")
    def test_value_range_validator_initialsoilcond_ssatini_lt_min_value(self):
        self.config["INITIAL_SOIL_CONDITIONS"] = {"s_sat_ini": "-0.01"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual("", str(cm.exception))

    @unittest.skip("Pending collection of valid value range info")
    def test_value_range_validator_initialsoilcond_bfw_ini_gt_max_value(self):
        self.config["INITIAL_SOIL_CONDITIONS"] = {"bfw_ini": "1.112"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual("", str(cm.exception))

    @unittest.skip("Pending collection of valid value range info")
    def test_value_range_validator_initialsoilcond_bfw_ini_lt_min_value(self):
        self.config["INITIAL_SOIL_CONDITIONS"] = {"bfw_ini": "-0.01"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual("", str(cm.exception))

    @unittest.skip("Pending collection of valid value range info")
    def test_value_range_validator_initialsoilcond_bfw_lim_gt_max_value(self):
        self.config["INITIAL_SOIL_CONDITIONS"] = {"bfw_lim": "1.112"}
        with self.assertRaises(ValidationException) as cm:
            value_range_validator(self.config)
        self.assertEqual("", str(cm.exception))


class DomainValidatorTest(unittest.TestCase):
    def setUp(self):
        self.config = ConfigParser()
        self.config.read_dict(
            {
                "GRID": {"grid": "500.00"},
                "CALIBRATION": {
                    "alpha": "4.500",
                    "b": "0.500",
                    "w_1": "0.333",
                    "w_2": "0.333",
                    "w_3": "0.334",
                    "rcd": "5.000",
                    "f": "0.500",
                    "alpha_gw": "0.500",
                    "x": "0.500",
                },
                "INITIAL_SOIL_CONDITIONS": {
                    "T_ini": "1.000",
                    "bfw_ini": "0.100",
                    "bfw_lim": "1.000",
                    "s_sat_ini": "1.001",
                },
                "CONSTANTS": {
                    "fpar_max": "0.950",
                    "fpar_min": "0.001",
                    "lai_max": "12.000",
                    "i_imp": "2.500",
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
                    "tss": "False",
                },
                "RASTER_FILE_FORMAT": {
                    "map_raster_series": "True",
                    "tiff_raster_series": "True",
                },
            }
        )

    def test_domain_validator_rasterfileformat_all_false(self):
        self.config.set("RASTER_FILE_FORMAT", "map_raster_series", "False")
        self.config.set("RASTER_FILE_FORMAT", "tiff_raster_series", "False")
        with self.assertRaises(ValidationException) as cm:
            domain_validator(self.config)
        self.assertEqual(
            "An output file format must be selected", str(cm.exception)
        )

    def test_domain_validator_generatefile_all_false(self):
        self.config.set("GENERATE_FILE", "itp", "False")
        self.config.set("GENERATE_FILE", "bfw", "False")
        self.config.set("GENERATE_FILE", "srn", "False")
        self.config.set("GENERATE_FILE", "eta", "False")
        self.config.set("GENERATE_FILE", "lfw", "False")
        self.config.set("GENERATE_FILE", "rec", "False")
        self.config.set("GENERATE_FILE", "smc", "False")
        self.config.set("GENERATE_FILE", "rnf", "False")
        with self.assertRaises(ValidationException) as cm:
            domain_validator(self.config)
        self.assertEqual(
            "At least one output variable must be selected", str(cm.exception)
        )

    def test_domain_validator_constants_fparmin_gt_fparmax(self):
        self.config.set("CONSTANTS", "fpar_max", "0.01")
        self.config.set("CONSTANTS", "fpar_min", "0.2")
        with self.assertRaises(ValidationException) as cm:
            domain_validator(self.config)
        self.assertEqual(
            "fpar_max must be greater than fpar_min", str(cm.exception)
        )

    @unittest.skip("It might be a warning instead of an exception")
    def test_domain_validator_initialsoilcond_ssatini_lt_bfw_lim(self):
        self.config.set("INITIAL_SOIL_CONDITIONS", "s_sat_ini", "0.5")
        self.config.set("INITIAL_SOIL_CONDITIONS", "bfw_lim", "0.9")
        with self.assertRaises(ValidationException) as cm:
            domain_validator(self.config)
        self.assertEqual(
            "To generate baseflow at initial step Initial Saturated Zone"
            " Storage (s_sat_ini) must be greater than Baseflow Threshold"
            " (bfw_lim)",
            str(cm.exception),
        )

    def test_domain_validator_initialsoilcond_bfw_ini_gt_bfw_lim(self):
        self.config.set("INITIAL_SOIL_CONDITIONS", "bfw_ini", "0.5")
        self.config.set("INITIAL_SOIL_CONDITIONS", "bfw_lim", "0.1")
        with self.assertRaises(ValidationException) as cm:
            domain_validator(self.config)
        self.assertEqual(
            "Baseflow threshold (bfw_lim) must be greater than zero and"
            " Initial Baseflow (bfw_ini)",
            str(cm.exception),
        )

    def test_domain_validator_calibration_weights_sum_value_gt_1(self):
        self.config.set("CALIBRATION", "w_1", "0.555")
        self.config.set("CALIBRATION", "w_2", "0.555")
        self.config.set("CALIBRATION", "w_3", "0.555")
        with self.assertRaises(ValidationException) as cm:
            domain_validator(self.config)
        self.assertEqual(
            "The sum of the weight factors Land Use (w1), Soil Moisture (w2)"
            " and Slope (w3) must equal 1.0",
            str(cm.exception),
        )


class ConfigSchemaValidatorTest(unittest.TestCase):
    def test_schemaValidator_no_sim_time_start_option(self):
        """"""
        config = ConfigParser()
        config["SIM_TIME"] = {"end": "01/01/2000"}
        with self.assertRaises(Exception) as cm:
            schemaValidator(config)
        self.assertEqual(
            "Missing value for 'start' under section SIM_TIME in the config"
            " file",
            str(cm.exception),
        )

    def test_schemaValidator_no_sim_time_end_option(self):
        """"""
        config = ConfigParser()
        config["SIM_TIME"] = {"start": "01/01/2000"}
        with self.assertRaises(Exception) as cm:
            schemaValidator(config)
        self.assertEqual(
            "Missing value for 'end' under section SIM_TIME in the config"
            " file",
            str(cm.exception),
        )

    def test_schemaValidator_no_sim_time_section(self):
        """"""
        config = ConfigParser()
        config["DEFAULT"] = {}
        with self.assertRaises(Exception) as cm:
            schemaValidator(config)
        self.assertEqual(
            "Missing section 'SIM_TIME' in the configuration file",
            str(cm.exception),
        )


def suite():
    """
    Gather all the tests from this module in a test suite.
    """
    testSuite = unittest.TestSuite()
    testSuite.addTest(unittest.makeSuite(FilePathArgValidatorTest))
    testSuite.addTest(unittest.makeSuite(DateValidatorTest))
    testSuite.addTest(unittest.makeSuite(DataTypeValidatorTest))
    testSuite.addTest(unittest.makeSuite(DirectoryPathValidatorTest))
    testSuite.addTest(unittest.makeSuite(FilePathValidatorTest))
    testSuite.addTest(unittest.makeSuite(FileSeriesNamesValidatorTest))
    testSuite.addTest(unittest.makeSuite(ConfigSchemaValidatorTest))
    testSuite.addTest(unittest.makeSuite(ValueRangeValidatorTest))

    return testSuite


if __name__ == "__main__":
    testSuite = suite()
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(testSuite)
