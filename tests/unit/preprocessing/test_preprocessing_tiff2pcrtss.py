import unittest


class TIFF2PCRasterTSSPreprocessingTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    @unittest.skip("Refactor the code of the test target class")
    def test_empty_config_list(self):
        """"""
        raise NotImplementedError


if __name__ == "__main__":
    suite = unittest.makeSuite(TIFF2PCRasterTSSPreprocessingTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
