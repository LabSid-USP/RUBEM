import os
import unittest

from pcraster import setclone

from rubem.modules._evapotranspiration import (
    ksCalc,
    etavCalc,
    kpCalc,
    etaoCalc,
    etasCalc,
)


class EvapotranspirationModuleTest(unittest.TestCase):
    """RUBEM Evapotranspiration Module Tests"""

    def setUp(self):
        """Runs before each test."""

        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        setclone(os.path.join(self.currentDir, "fixtures/dem.map"))

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_ksCalc_None_values(self):
        """"""
        self.assertRaises(TypeError, ksCalc, None, None, None)

    def test_ksCalc_valid_values(self):
        """"""
        # # PCRaster first specify clone or area map, use setclone()
        # TUr = 1.0
        # TUw = 1.0
        # TUcc = 1.0
        # result = ksCalc(TUr, TUw, TUcc)
        # expected = 2.0
        # self.assertEqual(result, expected)
        raise NotImplementedError

    def test_etavCalc_valid_values(self):
        """"""
        # etavCalc(ETp, Kc, Ks)
        raise NotImplementedError

    def test_etavCalc_None_values(self):
        """"""
        # etavCalc(ETp, Kc, Ks)
        self.assertRaises(TypeError, etavCalc, None, None, None)

    def test_kpCalc_valid_values(self):
        """"""
        # kpCalc(B, U_2, UR)
        raise NotImplementedError

    def test_kpCalc_None_values(self):
        """"""
        # kpCalc(B, U_2, UR)
        self.assertRaises(RuntimeError, kpCalc, None, None, None)

    def test_etaoCalc_valid_values(self):
        """"""
        # etaoCalc(ETp, Kp, prec, Ao)
        raise NotImplementedError

    def test_etaoCalc_None_values(self):
        """"""
        # etaoCalc(ETp, Kp, prec, Ao)
        self.assertRaises(TypeError, kpCalc, None, None, None, None)

    def test_etasCalc_valid_values(self):
        """"""
        # etasCalc(ETp, kc_min, Ks)
        raise NotImplementedError

    def test_etasCalc_None_values(self):
        """"""
        # etasCalc(ETp, kc_min, Ks)
        self.assertRaises(TypeError, etasCalc, None, None, None)


if __name__ == "__main__":
    suite = unittest.makeSuite(EvapotranspirationModuleTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
