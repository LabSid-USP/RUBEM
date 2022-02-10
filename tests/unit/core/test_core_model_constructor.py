from configparser import ConfigParser
import os
import tempfile
import unittest

from tests.utils import parentDirUpdate, removeFile, removeDirectory
from rubem.core import Model


class ModelConstructorTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_non_existent_config_ini_file(self):
        """Test we can't read a non existent model configuration file"""
        self.assertRaises(
            FileNotFoundError, Model.load, tempfile.mkdtemp() + "/fake.ini"
        )

    def test_empty_config_dict(self):
        """Test we can't read an empty model configuration dictionary"""
        with self.assertRaises(Exception) as cm:
            Model.load({})
        self.assertEqual("Empty model configuration dictionay", str(cm.exception))

    def test_empty_config_list(self):
        """Test we can't read an empty model configuration list"""
        with self.assertRaises(Exception) as cm:
            Model.load([])
        self.assertEqual(
            "('Unsupported model configuration format', <class 'list'>)",
            str(cm.exception),
        )

    def test_int_config_arg_type(self):
        with self.assertRaises(Exception) as cm:
            Model(42)
        self.assertEqual(
            "The model constructor expected an argument type like ConfigParser, but got <class 'int'>",
            str(cm.exception),
        )

    def test_empty_config_arg_type(self):
        with self.assertRaises(Exception) as cm:
            Model({})
        self.assertEqual(
            "The model constructor expected an argument type like ConfigParser, but got <class 'dict'>",
            str(cm.exception),
        )


class ModelConstructorFileDictTest(unittest.TestCase):
    """Test model constructor"""

    def setUp(self):
        """Runs before each test."""

        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        self.tempDir = tempfile.mkdtemp()
        self.templateBaseProject = os.path.join(
            self.currentDir, "fixtures/base.template"
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

        parser = ConfigParser()
        parser.read(self.baseProjectFile)
        self.configDict = {
            section: dict(parser.items(section)) for section in parser.sections()
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
        removeDirectory(self.tempDir)

    def test_config_ini_file(self):
        """Test we can read a model configuration file"""
        model = Model.load(self.baseProjectFile)
        self.assertListEqual(model.config.sections(), self.validConfigSections)

    def test_config_dict(self):
        """Test we can read a model configuration dictionary"""
        model = Model.load(self.configDict)
        self.assertListEqual(model.config.sections(), self.validConfigSections)


def suite():
    """
    Gather all the tests from this module in a test suite.
    """
    testSuite = unittest.TestSuite()
    testSuite.addTest(unittest.makeSuite(ModelConstructorTest))
    testSuite.addTest(unittest.makeSuite(ModelConstructorFileDictTest))
    return testSuite


if __name__ == "__main__":
    testSuite = suite()
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(testSuite)
