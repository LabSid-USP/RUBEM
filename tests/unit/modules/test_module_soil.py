import os
import unittest

from pcraster import setclone

from rubem.modules._soil import lfCalc, recCalc, baseflowCalc, turCalc, tusCalc


class LateralFlowSoilModuleTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_lfCalc(self):
        """"""
        # lfCalc(f, Kr, TUr, TUsat)
        raise NotImplementedError

    def test_lfCalc_None_values(self):
        """"""
        # lfCalc(f, Kr, TUr, TUsat)
        self.assertRaises(TypeError, lfCalc, None, None, None, None)


class RechargeSoilModuleTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_recCalc(self):
        """"""
        # recCalc(f, Kr, TUr, TUsat)
        raise NotImplementedError

    def test_recCalc_None_values(self):
        """"""
        # recCalc(f, Kr, TUr, TUsat)
        self.assertRaises(TypeError, recCalc, None, None, None, None)


class BaseFlowSoilModuleTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_baseflowCalc(self):
        """"""
        # baseflowCalc(EB_prev, alfaS, REC, TUs, EB_lim)
        raise NotImplementedError

    def test_baseflowCalc_None_values(self):
        """"""
        # baseflowCalc(EB_prev, alfaS, REC, TUs, EB_lim)
        self.assertRaises(TypeError, baseflowCalc, None, None, None, None, None)


class SoilBalanceSoilModuleTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        setclone(os.path.join(self.currentDir, "fixtures/dem.map"))

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_turCalc(self):
        """"""
        # turCalc(TUrprev, P, I, ES, LF, REC, ETr, Ao, Tsat)
        raise NotImplementedError

    def test_tusCalc(self):
        """"""
        # tusCalc(TUsprev, REC, EB)
        raise NotImplementedError

    def test_turCalc_None_values(self):
        """"""
        # turCalc(TUrprev, P, I, ES, LF, REC, ETr, Ao, Tsat)
        self.assertRaises(
            TypeError, turCalc, None, None, None, None, None, None, None, None, None
        )

    def test_tusCalc_None_values(self):
        """"""
        # tusCalc(TUsprev, REC, EB)
        self.assertRaises(TypeError, tusCalc, None, None, None)


def suite():
    """
    Gather all the tests from this module in a test suite.
    """
    testSuite = unittest.TestSuite()
    testSuite.addTest(unittest.makeSuite(LateralFlowSoilModuleTest))
    testSuite.addTest(unittest.makeSuite(RechargeSoilModuleTest))
    testSuite.addTest(unittest.makeSuite(BaseFlowSoilModuleTest))
    testSuite.addTest(unittest.makeSuite(SoilBalanceSoilModuleTest))
    return testSuite


if __name__ == "__main__":
    testSuite = suite()
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(testSuite)
