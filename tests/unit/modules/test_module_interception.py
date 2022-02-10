import os
import unittest

import pcraster as pcr
from pcraster.framework import generalfunctions

from rubem.modules import _interception


class InterceptionModuleTest(unittest.TestCase):
    """RUBEM Interception Module Tests"""

    def setUp(self):
        """Runs before each test."""

        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        pcr.setclone(os.path.join(self.currentDir, "fixtures/clone2x2.map"))

    def test_srCalc_NDVI_lt_1(self):
        """"""
        value = 0.555
        NDVI = pcr.spatial(pcr.scalar(value))
        field = _interception.srCalc(NDVI)
        result = generalfunctions.getCellValue(field, 1, 1)
        expected = 3.49438214302063
        self.assertEqual(result, expected)

    @unittest.skip("Reassess need for testing var value range here")
    def test_srCalc_NDVI_gt_1(self):
        """"""
        value = 2.0
        NDVI = pcr.spatial(pcr.scalar(value))
        with self.assertRaises(Exception) as cm:
            _interception.srCalc(NDVI)
        self.assertEqual(
            f"NDVI must be in the value range [-1.0, 1.0], value range was [{value}, {value}]",
            str(cm.exception),
        )

    @unittest.skip("This test has to use PCRaster types/exceptions")
    def test_srCalc_NDVI_eq_1(self):
        """"""
        value = 1.0
        NDVI = pcr.spatial(pcr.scalar(value))
        with self.assertRaises(ZeroDivisionError) as cm:
            _interception.srCalc(NDVI)
        self.assertEqual("float division by zero", str(cm.exception))

    def test_srCalc_None_values(self):
        """"""
        self.assertRaises(TypeError, _interception.srCalc, None)

    def test_kcCalc(self):
        """"""
        NDVI = pcr.scalar(0.555)
        ndvi_min = pcr.scalar(0.111)
        ndvi_max = pcr.scalar(0.777)
        kc_min = pcr.scalar(0.466)
        kc_max = pcr.scalar(0.933)
        field = _interception.kcCalc(NDVI, ndvi_min, ndvi_max, kc_min, kc_max)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.7773333787918091
        self.assertEqual(result, expected)

    def test_kcCalc_NDVImax_eq_NDVImin(self):
        """"""
        NDVI = pcr.scalar(0.555)
        ndvi_min = pcr.scalar(0.333)
        ndvi_max = pcr.scalar(0.333)
        kc_min = pcr.scalar(0.466)
        kc_max = pcr.scalar(0.933)
        with self.assertRaises(RuntimeError) as cm:
            _interception.kcCalc(NDVI, ndvi_min, ndvi_max, kc_min, kc_max)
        self.assertEqual("pcrfdiv: operator /: Domain Error\n", str(cm.exception))

    def test_kcCalc_None_values(self):
        """"""
        self.assertRaises(TypeError, _interception.kcCalc, None, None, None, None, None)

    def test_fparCalc(self):
        """"""
        fpar_min = pcr.scalar(0.555)
        fpar_max = pcr.scalar(0.999)
        SR = pcr.scalar(1.0)
        sr_min = pcr.scalar(0.75)
        sr_max = pcr.scalar(1.5)
        field = _interception.fparCalc(fpar_min, fpar_max, SR, sr_min, sr_max)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.703000009059906
        self.assertEqual(result, expected)

    def test_fparCalc_SRmax_eq_SRmin(self):
        """"""
        fpar_min = pcr.scalar(0.555)
        fpar_max = pcr.scalar(0.999)
        SR = pcr.scalar(1.0)
        sr_min = pcr.scalar(1.5)
        sr_max = pcr.scalar(1.5)
        with self.assertRaises(RuntimeError) as cm:
            _interception.fparCalc(fpar_min, fpar_max, SR, sr_min, sr_max)
        self.assertIn("pcrfdiv: operator /: Domain Error", str(cm.exception))

    def test_fparCalc_None_values(self):
        """"""
        self.assertRaises(
            TypeError, _interception.fparCalc, None, None, None, None, None
        )

    def test_laiCalc_None_values(self):
        """"""
        self.assertRaises(TypeError, _interception.laiCalc, None, None, None)

    def test_laiCalc(self):
        """"""
        FPAR = pcr.scalar(0.7)
        fpar_max = pcr.scalar(0.9)
        lai_max = pcr.scalar(1.0)
        field = _interception.laiCalc(FPAR, fpar_max, lai_max)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.5228787660
        self.assertAlmostEqual(result, expected)

    def test_laiCalc_FPAR_gt_1(self):
        """"""
        FPAR = pcr.scalar(1.7)
        fpar_max = pcr.scalar(0.9)
        lai_max = pcr.scalar(1.0)
        with self.assertRaises(RuntimeError) as cm:
            _interception.laiCalc(FPAR, fpar_max, lai_max)
        self.assertEqual("log10: function log10: Domain Error\n", str(cm.exception))

    def test_laiCalc_FPAR_eq_1(self):
        """"""
        FPAR = pcr.scalar(1.0)
        fpar_max = pcr.scalar(0.9)
        lai_max = pcr.scalar(1.0)
        with self.assertRaises(RuntimeError) as cm:
            _interception.laiCalc(FPAR, fpar_max, lai_max)
        self.assertEqual("log10: function log10: Domain Error\n", str(cm.exception))

    def test_laiCalc_FPARmax_gt_1(self):
        """"""
        FPAR = pcr.scalar(0.7)
        fpar_max = pcr.scalar(1.9)
        lai_max = pcr.scalar(1.0)
        with self.assertRaises(RuntimeError) as cm:
            _interception.laiCalc(FPAR, fpar_max, lai_max)
        self.assertEqual("log10: function log10: Domain Error\n", str(cm.exception))

    def test_laiCalc_FPARmax_eq_1(self):
        """"""
        FPAR = pcr.scalar(0.7)
        fpar_max = pcr.scalar(1.0)
        lai_max = pcr.scalar(1.0)
        with self.assertRaises(RuntimeError) as cm:
            _interception.laiCalc(FPAR, fpar_max, lai_max)
        self.assertEqual("log10: function log10: Domain Error\n", str(cm.exception))

    def test_interceptionCalc_cond1_true_cond2_false(self):
        """"""
        alfa = pcr.scalar(10.0)
        LAI = pcr.scalar(12.0)
        precipitation = pcr.scalar(125.93)
        rainy_days = pcr.scalar(15)
        a_v = pcr.scalar(0.255)
        field_tuple = _interception.interceptionCalc(
            alfa, LAI, precipitation, rainy_days, a_v
        )
        result_list = [
            generalfunctions.getCellValue(field, 0, 0) for field in field_tuple
        ]
        expected_list = [
            61.33066177368164,
            0.999328076839447,
            125.84538269042969,
            32.090572357177734,
        ]
        self.assertEqual(result_list, expected_list)

    def test_interceptionCalc_cond1_false_cond2_true(self):
        """"""
        alfa = pcr.scalar(10.0)
        LAI = pcr.scalar(12.0)
        precipitation = pcr.scalar(0.0)
        rainy_days = pcr.scalar(15)
        a_v = pcr.scalar(0.255)
        field_tuple = _interception.interceptionCalc(
            alfa, LAI, precipitation, rainy_days, a_v
        )
        result_list = [
            generalfunctions.getCellValue(field, 0, 0) for field in field_tuple
        ]
        expected_list = [0.0, 0.0, 0.0, 0.0]
        self.assertEqual(result_list, expected_list)

    def test_interceptionCalc_cond1_true_cond2_false_alfa_eq_0(self):
        """"""
        alfa = pcr.scalar(0.0)
        LAI = pcr.scalar(1.0)
        precipitation = pcr.scalar(125.93)
        rainy_days = pcr.scalar(15)
        a_v = pcr.scalar(0.255)
        with self.assertRaises(RuntimeError) as cm:
            _interception.interceptionCalc(alfa, LAI, precipitation, rainy_days, a_v)
        self.assertEqual("pcrfdiv: operator /: Domain Error\n", str(cm.exception))

    def test_interceptionCalc_cond1_true_cond2_false_LAI_eq_0(self):
        """"""
        alfa = pcr.scalar(0.01)
        LAI = pcr.scalar(0.0)
        precipitation = pcr.scalar(125.93)
        rainy_days = pcr.scalar(15)
        a_v = pcr.scalar(0.255)
        with self.assertRaises(RuntimeError) as cm:
            _interception.interceptionCalc(alfa, LAI, precipitation, rainy_days, a_v)
        self.assertEqual("pcrfdiv: operator /: Domain Error\n", str(cm.exception))

    def test_interceptionCalc_None_values(self):
        """"""
        self.assertRaises(
            RuntimeError, _interception.interceptionCalc, None, None, None, None, None
        )


if __name__ == "__main__":
    suite = unittest.makeSuite(InterceptionModuleTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
