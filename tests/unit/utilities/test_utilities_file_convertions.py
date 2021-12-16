import os
import io
import unittest

from rubem.utilities._file_convertions import tss2csv
from tests.utils import removeFile, removeDirectory


class FileConvertionsUtilitiesTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        self.baseTSS = os.path.join(self.currentDir, "fixtures/")
        self.obtainedCSV = os.path.join(self.currentDir, "fixtures/base.csv")
        self.expectedCSV = os.path.join(self.currentDir, "fixtures/base_cmp.csv")

    def tearDown(self):
        """Runs after each test."""
        removeFile(self.obtainedCSV)

    def test_tss2csv_valid_input(self):
        """"""
        tss2csv(self.baseTSS, ["1", "2", "3", "4", "5"], False)
        self.assertListEqual(
            list(io.open(self.obtainedCSV)), list(io.open(self.expectedCSV))
        )

    def test_tss2csv_less_colNames(self):
        """"""
        self.assertRaises(ValueError, tss2csv, self.baseTSS, ["1", "2", "3"], False)

    def test_tss2csv_more_colNames(self):
        """"""
        self.assertRaises(
            ValueError,
            tss2csv,
            self.baseTSS,
            ["1", "2", "3", "4", "5", "6", "7"],
            False,
        )

    def test_tss2csv_None_path(self):
        """"""
        self.assertRaises(
            TypeError, tss2csv, None, ["col1", "col2", "col3", "col4", "col5"]
        )

    def test_tss2csv_None_headers(self):
        """"""
        self.assertRaises(TypeError, tss2csv, self.baseTSS, None)


if __name__ == "__main__":
    suite = unittest.makeSuite(FileConvertionsUtilitiesTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
