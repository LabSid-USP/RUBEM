import unittest


class KrigingPreprocessingTest(unittest.TestCase):
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
    suite = unittest.makeSuite(KrigingPreprocessingTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
