import os
import unittest

import pcraster as pcr
from pcraster.framework import generalfunctions

from rubem.modules import _evapotranspiration


class EvapotranspirationModuleTest(unittest.TestCase):
    """RUBEM Evapotranspiration Module Tests"""

    def setUp(self):
        """Runs before each test."""

        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        pcr.setclone(os.path.join(self.currentDir, "fixtures/clone1x1.map"))

    def test_ksCalc_None_values(self):
        """"""
        self.assertRaises(
            TypeError, _evapotranspiration.ksCalc, None, None, None
        )

    def test_ksCalc_ks_cond_true(self):
        """"""
        TUr = pcr.scalar(2.0)
        TUw = pcr.scalar(1.0)
        TUcc = pcr.scalar(3.0)
        field = _evapotranspiration.ksCalc(TUr, TUw, TUcc)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.6309297680854797
        self.assertEqual(result, expected)

    def test_ksCalc_ks_cond_false(self):
        """"""
        TUr = pcr.scalar(1.0)
        TUw = pcr.scalar(2.0)
        TUcc = pcr.scalar(3.0)
        field = _evapotranspiration.ksCalc(TUr, TUw, TUcc)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        self.assertEqual(result, expected)

    @unittest.skip("This test has to use PCRaster types")
    def test_ksCalc_TUcc_minus_TUw_eq_neg_1(self):
        """"""
        TUr = pcr.scalar(3.0)
        TUw = pcr.scalar(2.0)
        TUcc = pcr.scalar(0.0)
        with self.assertRaises(RuntimeError) as cm:
            _evapotranspiration.ksCalc(TUr, TUw, TUcc)
        self.assertEqual("ln: function ln: Domain Error\n", str(cm.exception))

    @unittest.expectedFailure
    def test_ksCalc_TUr_minus_TUw_eq_neg_1(self):
        """"""
        TUr = pcr.scalar(1.0)
        TUw = pcr.scalar(2.0)
        TUcc = pcr.scalar(2.0)
        with self.assertRaises(RuntimeError) as cm:
            _evapotranspiration.ksCalc(TUr, TUw, TUcc)
        self.assertEqual("ln: function ln: Domain Error\n", str(cm.exception))

    def test_etavCalc_valid_values(self):
        """"""
        ETp = pcr.scalar(1.0)
        Kc = pcr.scalar(1.0)
        Ks = pcr.scalar(1.0)
        field = _evapotranspiration.etavCalc(ETp, Kc, Ks)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        self.assertEqual(result, expected)

    def test_etavCalc_None_values(self):
        """"""
        self.assertRaises(
            TypeError, _evapotranspiration.etavCalc, None, None, None
        )

    def test_kpCalc_B_eq_0(self):
        """"""
        B = 0.0
        U_2 = 1.0
        UR = 1.0
        with self.assertRaises(RuntimeError) as cm:
            _evapotranspiration.kpCalc(B, U_2, UR)
        self.assertEqual("ln: function ln: Domain Error\n", str(cm.exception))

    def test_kpCalc_valid_values(self):
        """"""
        B = 1.0
        U_2 = 1.0
        UR = 1.0
        field = _evapotranspiration.kpCalc(B, U_2, UR)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.4861240088939667
        self.assertEqual(result, expected)

    def test_kpCalc_None_values(self):
        """"""
        self.assertRaises(
            RuntimeError, _evapotranspiration.kpCalc, None, None, None
        )

    def test_etaoCalc_cond1_true_cond_2_true(self):
        """"""
        ETp = pcr.scalar(4.0)
        Kp = pcr.scalar(2.0)
        prec = pcr.scalar(1.0)
        Ao = pcr.scalar(1.0)
        field = _evapotranspiration.etaoCalc(ETp, Kp, prec, Ao)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        self.assertEqual(result, expected)

    def test_etaoCalc_cond1_false_cond_2_false(self):
        """"""
        ETp = pcr.scalar(2.0)
        Kp = pcr.scalar(2.0)
        prec = pcr.scalar(2.0)
        Ao = pcr.scalar(0.111)
        field = _evapotranspiration.etaoCalc(ETp, Kp, prec, Ao)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        self.assertEqual(result, expected)

    def test_etaoCalc_cond1_true_cond_2_false(self):
        """"""
        ETp = pcr.scalar(2.0)
        Kp = pcr.scalar(2.0)
        prec = pcr.scalar(2.0)
        Ao = pcr.scalar(1.0)
        field = _evapotranspiration.etaoCalc(ETp, Kp, prec, Ao)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        self.assertEqual(result, expected)

    def test_etaoCalc_cond1_false_cond_2_true(self):
        """"""
        ETp = pcr.scalar(4.0)
        Kp = pcr.scalar(2.0)
        prec = pcr.scalar(1.0)
        Ao = pcr.scalar(0.111)
        field = _evapotranspiration.etaoCalc(ETp, Kp, prec, Ao)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 2.0
        self.assertEqual(result, expected)

    def test_etaoCalc_None_values(self):
        """"""
        self.assertRaises(
            TypeError, _evapotranspiration.kpCalc, None, None, None, None
        )

    def test_etasCalc_cond_true_gt_0(self):
        """"""
        ETp = pcr.scalar(1.0)
        kc_min = pcr.scalar(1.0)
        Ks = pcr.scalar(1.0)
        field = _evapotranspiration.etasCalc(ETp, kc_min, Ks)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        self.assertEqual(result, expected)

    def test_etasCalc_cond_false_eq_0(self):
        """"""
        ETp = pcr.scalar(1.0)
        kc_min = pcr.scalar(1.0)
        Ks = pcr.scalar(0.0)
        field = _evapotranspiration.etasCalc(ETp, kc_min, Ks)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        self.assertEqual(result, expected)

    def test_etasCalc_cond_false_lt_0(self):
        """"""
        ETp = pcr.scalar(1.0)
        kc_min = pcr.scalar(1.0)
        Ks = pcr.scalar(-1.0)
        field = _evapotranspiration.etasCalc(ETp, kc_min, Ks)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = -1.0
        self.assertEqual(result, expected)

    def test_etasCalc_None_values(self):
        """"""
        self.assertRaises(
            TypeError, _evapotranspiration.etasCalc, None, None, None
        )


if __name__ == "__main__":
    suite = unittest.makeSuite(EvapotranspirationModuleTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
