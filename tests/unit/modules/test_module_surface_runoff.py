import unittest

from rubem.modules._surface_runoff import (
    chCalc,
    cperCalc,
    cimpCalc,
    cwpCalc,
    csrCalc,
    sRunoffCalc,
)


class SurfaceRunoffModuleTest(unittest.TestCase):
    """RUBEM Surface Runoff Module Tests"""

    def setUp(self):
        """Runs before each test."""
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_chCalc(self):
        """"""
        # chCalc(TUr, dg, Zr, Tsat, b)
        raise NotImplementedError

    def test_cperCalc(self):
        """"""
        # cperCalc(TUw, dg, Zr, S, manning, w1, w2, w3)
        raise NotImplementedError

    def test_cimpCalc(self):
        """"""
        # cimpCalc(ao, ai)
        raise NotImplementedError

    def test_cwpCalc(self):
        """"""
        # cwpCalc(Aimp, Cper, Cimp)
        raise NotImplementedError

    def test_csrCalc(self):
        """"""
        # csrCalc(Cwp, P_24, RCD)
        raise NotImplementedError

    def test_sRunoffCalc(self):
        """"""
        # sRunoffCalc(Csr, Ch, prec, I, Ao, ETao, TUr, Tsat)
        raise NotImplementedError


if __name__ == "__main__":
    suite = unittest.makeSuite(SurfaceRunoffModuleTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
