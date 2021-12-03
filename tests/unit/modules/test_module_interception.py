import unittest

from rubem.modules._interception import (
    srCalc,
    kcCalc,
    fparCalc,
    laiCalc,
    interceptionCalc,
)


class InterceptionModuleTest(unittest.TestCase):
    """RUBEM Interception Module Tests"""

    def setUp(self):
        """Runs before each test."""
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_srCalc(self):
        """"""
        # srCalc(NDVI)
        raise NotImplementedError

    def test_kcCalc(self):
        """"""
        # kcCalc(NDVI, ndvi_min, ndvi_max, kc_min, kc_max)
        raise NotImplementedError

    def test_fparCalc(self):
        """"""
        # fparCalc(fpar_min, fpar_max, SR, sr_min, sr_max)
        raise NotImplementedError

    def test_laiCalc(self):
        """"""
        # laiCalc(FPAR, fpar_max, lai_max)
        raise NotImplementedError

    def test_interceptionCalc(self):
        """"""
        # interceptionCalc(alfa, LAI, precipitation, rainy_days, a_v)
        raise NotImplementedError


if __name__ == "__main__":
    suite = unittest.makeSuite(InterceptionModuleTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
