import unittest

from rubem.file import _file_generators


class FileGeneratorsUtilitiesTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_getRefInfo_none_arg(self):
        self.assertRaises(RuntimeError, _file_generators.getRefInfo, None)

    @unittest.skip("Collect more information")
    def test_getRefInfo_valid_arg(self):
        raise NotImplementedError

    @unittest.skip("It causes segmentation fault")
    def test_reportTIFFSeries_none_arg(self):
        self.assertRaises(
            ValueError,
            _file_generators.reportTIFFSeries,
            None,
            None,
            None,
            None,
            None,
            None,
        )

    @unittest.skip("Collect more information")
    def test_reportTIFFSeries_valid_arg(self):
        raise NotImplementedError


if __name__ == "__main__":
    suite = unittest.makeSuite(FileGeneratorsUtilitiesTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
