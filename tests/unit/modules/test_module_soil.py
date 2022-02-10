import os
import unittest

import pcraster as pcr
from pcraster.framework import generalfunctions

from rubem.modules import _soil


class LateralFlowSoilModuleTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        pcr.setclone(os.path.join(self.currentDir, "fixtures/clone1x1.map"))

    def test_lfCalc(self):
        """"""
        f = pcr.scalar(1.0)
        Kr = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)
        TUsat = pcr.scalar(1.0)
        result = _soil.lfCalc(f, Kr, TUr, TUsat)
        expected = 1.0
        self.assertEqual(result, expected)

    def test_lfCalc_TUsat_eq_0(self):
        """"""
        f = pcr.scalar(1.0)
        Kr = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)
        TUsat = pcr.scalar(0.0)
        with self.assertRaises(RuntimeError) as cm:
            _soil.lfCalc(f, Kr, TUr, TUsat)
        self.assertIn("pcrfdiv: operator /: Domain Error", str(cm.exception))

    def test_lfCalc_None_values(self):
        """"""
        self.assertRaises(TypeError, _soil.lfCalc, None, None, None, None)


class RechargeSoilModuleTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        pcr.setclone(os.path.join(self.currentDir, "fixtures/clone1x1.map"))

    def test_recCalc(self):
        """"""
        f = pcr.scalar(0.50)
        Kr = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)
        TUsat = pcr.scalar(1.0)
        result = _soil.recCalc(f, Kr, TUr, TUsat)
        expected = 0.5
        self.assertEqual(result, expected)

    def test_recCalc_TUsat_eq_0(self):
        """"""
        f = pcr.scalar(1.0)
        Kr = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)
        TUsat = pcr.scalar(0.0)
        with self.assertRaises(RuntimeError) as cm:
            _soil.recCalc(f, Kr, TUr, TUsat)
        self.assertIn("pcrfdiv: operator /: Domain Error", str(cm.exception))

    def test_recCalc_None_values(self):
        """"""
        self.assertRaises(TypeError, _soil.recCalc, None, None, None, None)


class BaseFlowSoilModuleTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        pcr.setclone(os.path.join(self.currentDir, "fixtures/clone1x1.map"))

    def test_baseflowCalc_cond_true(self):
        """"""
        EB_prev = pcr.scalar(1.0)
        alfaS = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        TUs = pcr.scalar(2.0)
        EB_lim = pcr.scalar(1.0)
        field = _soil.baseflowCalc(EB_prev, alfaS, REC, TUs, EB_lim)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        self.assertEqual(result, expected)

    def test_baseflowCalc_cond_false_TUs_eq_EBlim(self):
        """"""
        EB_prev = pcr.scalar(1.0)
        alfaS = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        TUs = pcr.scalar(1.0)
        EB_lim = pcr.scalar(1.0)
        field = _soil.baseflowCalc(EB_prev, alfaS, REC, TUs, EB_lim)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        self.assertEqual(result, expected)

    def test_baseflowCalc_cond_false_TUs_lt_EBlim(self):
        """"""
        EB_prev = pcr.scalar(1.0)
        alfaS = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        TUs = pcr.scalar(1.0)
        EB_lim = pcr.scalar(2.0)
        field = _soil.baseflowCalc(EB_prev, alfaS, REC, TUs, EB_lim)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        self.assertEqual(result, expected)

    def test_baseflowCalc_None_values(self):
        """"""
        self.assertRaises(
            TypeError, _soil.baseflowCalc, None, None, None, None, None
        )


class SoilBalanceSoilModuleTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        pcr.setclone(os.path.join(self.currentDir, "fixtures/clone1x1.map"))

    def test_turCalc_condw1_true_cond_true_cond3_true(self):
        """"""
        TUrprev = pcr.scalar(5.0)
        P = pcr.scalar(5.0)
        Itp = pcr.scalar(1.0)
        ES = pcr.scalar(1.0)
        LF = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        ETr = pcr.scalar(1.0)
        Ao = pcr.scalar(1.1)
        Tsat = pcr.scalar(5.5)
        field = _soil.turCalc(TUrprev, P, Itp, ES, LF, REC, ETr, Ao, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 5.0
        self.assertEqual(result, expected)

    def test_turCalc_condw1_true_cond_true_cond3_false(self):
        """"""
        TUrprev = pcr.scalar(5.0)
        P = pcr.scalar(5.0)
        Itp = pcr.scalar(1.0)
        ES = pcr.scalar(1.0)
        LF = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        ETr = pcr.scalar(1.0)
        Ao = pcr.scalar(1.1)
        Tsat = pcr.scalar(4.5)
        field = _soil.turCalc(TUrprev, P, Itp, ES, LF, REC, ETr, Ao, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 4.5
        self.assertEqual(result, expected)

    def test_turCalc_condw1_true_cond_false_cond3_true(self):
        """"""
        TUrprev = pcr.scalar(1.0)
        P = pcr.scalar(2.0)
        Itp = pcr.scalar(1.0)
        ES = pcr.scalar(1.0)
        LF = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        ETr = pcr.scalar(1.0)
        Ao = pcr.scalar(1.1)
        Tsat = pcr.scalar(5.5)
        field = _soil.turCalc(TUrprev, P, Itp, ES, LF, REC, ETr, Ao, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        self.assertEqual(result, expected)

    def test_turCalc_condw1_true_cond_false_cond3_false(self):
        """"""
        TUrprev = pcr.scalar(1.0)
        P = pcr.scalar(2.0)
        Itp = pcr.scalar(1.0)
        ES = pcr.scalar(1.0)
        LF = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        ETr = pcr.scalar(1.0)
        Ao = pcr.scalar(1.1)
        Tsat = pcr.scalar(0.0)
        field = _soil.turCalc(TUrprev, P, Itp, ES, LF, REC, ETr, Ao, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        self.assertEqual(result, expected)

    def test_turCalc_condw1_false_cond_true_cond3_true(self):
        """"""
        TUrprev = pcr.scalar(5.0)
        P = pcr.scalar(5.0)
        Itp = pcr.scalar(1.0)
        ES = pcr.scalar(1.0)
        LF = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        ETr = pcr.scalar(1.0)
        Ao = pcr.scalar(1.0)
        Tsat = pcr.scalar(5.5)
        field = _soil.turCalc(TUrprev, P, Itp, ES, LF, REC, ETr, Ao, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 5.5
        self.assertEqual(result, expected)

    def test_turCalc_condw1_false_cond_true_cond3_false(self):
        """"""
        TUrprev = pcr.scalar(5.0)
        P = pcr.scalar(5.0)
        Itp = pcr.scalar(1.0)
        ES = pcr.scalar(1.0)
        LF = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        ETr = pcr.scalar(1.0)
        Ao = pcr.scalar(1.0)
        Tsat = pcr.scalar(4.5)
        field = _soil.turCalc(TUrprev, P, Itp, ES, LF, REC, ETr, Ao, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 4.5
        self.assertEqual(result, expected)

    def test_turCalc_condw1_false_cond_false_cond3_true(self):
        """"""
        TUrprev = pcr.scalar(1.0)
        P = pcr.scalar(2.0)
        Itp = pcr.scalar(1.0)
        ES = pcr.scalar(1.0)
        LF = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        ETr = pcr.scalar(1.0)
        Ao = pcr.scalar(1.0)
        Tsat = pcr.scalar(5.5)
        field = _soil.turCalc(TUrprev, P, Itp, ES, LF, REC, ETr, Ao, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 5.5
        self.assertEqual(result, expected)

    def test_turCalc_condw1_false_cond_false_cond3_false(self):
        """"""
        TUrprev = pcr.scalar(1.0)
        P = pcr.scalar(2.0)
        Itp = pcr.scalar(1.0)
        ES = pcr.scalar(1.0)
        LF = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        ETr = pcr.scalar(1.0)
        Ao = pcr.scalar(1.0)
        Tsat = pcr.scalar(0.0)
        field = _soil.turCalc(TUrprev, P, Itp, ES, LF, REC, ETr, Ao, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        self.assertEqual(result, expected)

    def test_tusCalc(self):
        """"""
        TUsprev = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        EB = pcr.scalar(1.0)
        result = _soil.tusCalc(TUsprev, REC, EB)
        expected = 1.0
        self.assertEqual(result, expected)

    def test_turCalc_None_values(self):
        """"""
        self.assertRaises(
            TypeError,
            _soil.turCalc,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )

    def test_tusCalc_None_values(self):
        """"""
        self.assertRaises(TypeError, _soil.tusCalc, None, None, None)


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
