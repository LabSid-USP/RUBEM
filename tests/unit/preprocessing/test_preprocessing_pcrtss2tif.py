import unittest


class PCRasterTSS2TIFFPreprocessingTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_empty_config_list(self):
        """"""
        raise NotImplementedError


if __name__ == "__main__":
    suite = unittest.makeSuite(PCRasterTSS2TIFFPreprocessingTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
