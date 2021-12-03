import unittest

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
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_ksCalc_None_values(self):
        """"""
        TUr = None
        TUw = None
        TUcc = None
        self.assertRaises(TypeError, ksCalc, TUr, TUw, TUcc)

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
        raise NotImplementedError

    def test_kpCalc_valid_values(self):
        """"""
        # kpCalc(B, U_2, UR)
        raise NotImplementedError

    def test_kpCalc_None_values(self):
        """"""
        # kpCalc(B, U_2, UR)
        raise NotImplementedError

    def test_etaoCalc_valid_values(self):
        """"""
        # etaoCalc(ETp, Kp, prec, Ao)
        raise NotImplementedError

    def test_etaoCalc_None_values(self):
        """"""
        # etaoCalc(ETp, Kp, prec, Ao)
        raise NotImplementedError

    def test_etasCalc_valid_values(self):
        """"""
        # etasCalc(ETp, kc_min, Ks)
        raise NotImplementedError

    def test_etasCalc_None_values(self):
        """"""
        # etasCalc(ETp, kc_min, Ks)
        raise NotImplementedError


if __name__ == "__main__":
    suite = unittest.makeSuite(EvapotranspirationModuleTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
