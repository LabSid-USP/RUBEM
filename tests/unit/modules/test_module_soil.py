import unittest

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


class SoilBalanceSoilModuleTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        pass

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
