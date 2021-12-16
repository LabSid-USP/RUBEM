import os
import unittest

from pcraster import setclone

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

        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        setclone(os.path.join(self.currentDir, "fixtures/dem.map"))

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_srCalc(self):
        """"""
        # srCalc(NDVI)
        raise NotImplementedError

    def test_srCalc_None_values(self):
        """"""
        # srCalc(NDVI)
        self.assertRaises(TypeError, srCalc, None)

    def test_kcCalc(self):
        """"""
        # kcCalc(NDVI, ndvi_min, ndvi_max, kc_min, kc_max)
        raise NotImplementedError

    def test_kcCalc_None_values(self):
        """"""
        # kcCalc(NDVI, ndvi_min, ndvi_max, kc_min, kc_max)
        self.assertRaises(TypeError, kcCalc, None, None, None, None, None)

    def test_fparCalc(self):
        """"""
        # fparCalc(fpar_min, fpar_max, SR, sr_min, sr_max)
        raise NotImplementedError

    def test_fparCalc_None_values(self):
        """"""
        # fparCalc(fpar_min, fpar_max, SR, sr_min, sr_max)
        self.assertRaises(TypeError, fparCalc, None, None, None, None, None)

    def test_laiCalc_None_values(self):
        """"""
        # laiCalc(FPAR, fpar_max, lai_max)
        self.assertRaises(TypeError, laiCalc, None, None, None)

    def test_laiCalc(self):
        """"""
        # laiCalc(FPAR, fpar_max, lai_max)
        raise NotImplementedError

    def test_interceptionCalc(self):
        """"""
        # interceptionCalc(alfa, LAI, precipitation, rainy_days, a_v)
        raise NotImplementedError

    def test_interceptionCalc_None_values(self):
        """"""
        # interceptionCalc(alfa, LAI, precipitation, rainy_days, a_v)
        self.assertRaises(RuntimeError, interceptionCalc, None, None, None, None, None)


if __name__ == "__main__":
    suite = unittest.makeSuite(InterceptionModuleTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
