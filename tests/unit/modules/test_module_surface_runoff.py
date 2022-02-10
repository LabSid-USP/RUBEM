import os
import unittest

import pcraster as pcr
from pcraster.framework import generalfunctions

from rubem.modules import _surface_runoff


class SurfaceRunoffModuleTest(unittest.TestCase):
    """RUBEM Surface Runoff Module Tests"""

    def setUp(self):
        """Runs before each test."""
        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        pcr.setclone(os.path.join(self.currentDir, "fixtures/clone1x1.map"))

    def test_chCalc(self):
        """"""
        TUr = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(1.0)
        Tsat = pcr.scalar(1.0)
        b = pcr.scalar(1.0)
        result = _surface_runoff.chCalc(TUr, dg, Zr, Tsat, b)
        expected = 0.1
        self.assertEqual(result, expected)

    def test_chCalc_dg_eq_0(self):
        """"""
        TUr = pcr.scalar(1.0)
        dg = pcr.scalar(0.0)
        Zr = pcr.scalar(1.0)
        Tsat = pcr.scalar(1.0)
        b = pcr.scalar(1.0)
        with self.assertRaises(RuntimeError) as cm:
            _surface_runoff.chCalc(TUr, dg, Zr, Tsat, b)
        self.assertIn("pcrfdiv: operator /: Domain Error", str(cm.exception))

    def test_chCalc_Zr_eq_0(self):
        """"""
        TUr = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(0.0)
        Tsat = pcr.scalar(1.0)
        b = pcr.scalar(1.0)
        with self.assertRaises(RuntimeError) as cm:
            _surface_runoff.chCalc(TUr, dg, Zr, Tsat, b)
        self.assertIn("pcrfdiv: operator /: Domain Error", str(cm.exception))

    def test_chCalc_Tsat_eq_0(self):
        """"""
        TUr = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(1.0)
        Tsat = pcr.scalar(0.0)
        b = pcr.scalar(1.0)
        with self.assertRaises(RuntimeError) as cm:
            _surface_runoff.chCalc(TUr, dg, Zr, Tsat, b)
        self.assertIn("pcrfdiv: operator /: Domain Error", str(cm.exception))

    def test_chCalc_None_values(self):
        """"""
        self.assertRaises(
            TypeError, _surface_runoff.chCalc, None, None, None, None, None
        )

    def test_cperCalc(self):
        """"""
        TUw = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(1.0)
        S = pcr.scalar(1.0)
        manning = pcr.scalar(1.0)
        w1 = 0.333
        w2 = 0.333
        w3 = 0.334
        field = _surface_runoff.cperCalc(TUw, dg, Zr, S, manning, w1, w2, w3)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.074023636
        self.assertAlmostEqual(result, expected)

    def test_cperCalc_dg_eq_0(self):
        """"""
        TUw = pcr.scalar(1.0)
        dg = pcr.scalar(0.0)
        Zr = pcr.scalar(1.0)
        S = pcr.scalar(1.0)
        manning = pcr.scalar(1.0)
        w1 = 0.333
        w2 = 0.333
        w3 = 0.334
        with self.assertRaises(RuntimeError) as cm:
            _surface_runoff.cperCalc(TUw, dg, Zr, S, manning, w1, w2, w3)
        self.assertIn("pcrfdiv: operator /: Domain Error", str(cm.exception))

    def test_cperCalc_Zr_eq_0(self):
        """"""
        TUw = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(0.0)
        S = pcr.scalar(1.0)
        manning = pcr.scalar(1.0)
        w1 = 0.333
        w2 = 0.333
        w3 = 0.334
        with self.assertRaises(RuntimeError) as cm:
            _surface_runoff.cperCalc(TUw, dg, Zr, S, manning, w1, w2, w3)
        self.assertIn("pcrfdiv: operator /: Domain Error", str(cm.exception))

    def test_cperCalc_manning_eq_0(self):
        """"""
        TUw = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(1.0)
        S = pcr.scalar(1.0)
        manning = pcr.scalar(0.0)
        w1 = 0.333
        w2 = 0.333
        w3 = 0.334
        with self.assertRaises(RuntimeError) as cm:
            _surface_runoff.cperCalc(TUw, dg, Zr, S, manning, w1, w2, w3)
        self.assertIn("pcrfdiv: operator /: Domain Error", str(cm.exception))

    def test_cperCalc_S_eq_minus_10(self):
        """"""
        TUw = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(1.0)
        S = pcr.scalar(-10.0)
        manning = pcr.scalar(1.0)
        w1 = 0.333
        w2 = 0.333
        w3 = 0.334
        with self.assertRaises(RuntimeError) as cm:
            _surface_runoff.cperCalc(TUw, dg, Zr, S, manning, w1, w2, w3)
        self.assertIn("pcrfdiv: operator /: Domain Error", str(cm.exception))

    @unittest.skip("Reassess need for testing var value range here")
    def test_cperCalc_weights_sum_gt_1(self):
        """"""
        TUw = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(1.0)
        S = pcr.scalar(1.0)
        manning = pcr.scalar(1.0)
        w1 = 0.555
        w2 = 0.555
        w3 = 0.555
        # TODO: Create ValidationError Exception
        with self.assertRaises(Exception) as cm:
            _surface_runoff.cperCalc(TUw, dg, Zr, S, manning, w1, w2, w3)
        self.assertEqual(
            "The sum of the weight factors Land Use (w1), Soil Moisture (w2) and Slope (w3) must equal 1.0",
            str(cm.exception),
        )

    @unittest.skip("Reassess need for testing var value range here")
    def test_cperCalc_weights_sum_lt_1(self):
        """"""
        TUw = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(1.0)
        S = pcr.scalar(1.0)
        manning = pcr.scalar(1.0)
        w1 = 0.333
        w2 = 0.333
        w3 = 0.111
        # TODO: Create ValidationError Exception
        with self.assertRaises(Exception) as cm:
            _surface_runoff.cperCalc(TUw, dg, Zr, S, manning, w1, w2, w3)
        self.assertEqual(
            "The sum of the weight factors Land Use (w1), Soil Moisture (w2) and Slope (w3) must equal 1.0",
            str(cm.exception),
        )

    def test_cperCalc_None_values(self):
        """"""
        self.assertRaises(
            TypeError,
            _surface_runoff.cperCalc,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )

    def test_cimpCalc(self):
        """"""
        ao = pcr.scalar(0.555)
        ai = pcr.scalar(0.255)
        field = _surface_runoff.cimpCalc(ao, ai)
        result = [
            generalfunctions.getCellValue(field[0], 0, 0),
            generalfunctions.getCellValue(field[1], 0, 0),
        ]
        expected = [0.8100000023841858, 0.6287978291511536]
        self.assertEqual(result, expected)

    @unittest.skip("Reassess need for testing var value range here")
    def test_cimpCalc_area_frac_sum_gt_1(self):
        """"""
        ao = pcr.scalar(0.555)
        ai = pcr.scalar(0.755)
        # TODO: Create ValidationError Exception
        with self.assertRaises(Exception) as cm:
            _surface_runoff.cimpCalc(ao, ai)
        self.assertEqual(
            "The sum of the area factors Open Water (ao), Impervious (ai), Vegetated (av) and Bare Soil (as) must equal 1.0",
            str(cm.exception),
        )

    def test_cimpCalc_None_values(self):
        """"""
        self.assertRaises(TypeError, _surface_runoff.cimpCalc, None, None)

    def test_cwpCalc(self):
        """"""
        Aimp = pcr.scalar(1.0)
        Cper = pcr.scalar(1.0)
        Cimp = pcr.scalar(1.0)
        result = _surface_runoff.cwpCalc(Aimp, Cper, Cimp)
        expected = 1.0
        self.assertEqual(result, expected)

    def test_cwpCalc_None_values(self):
        """"""
        self.assertRaises(TypeError, _surface_runoff.cwpCalc, None, None, None)

    def test_csrCalc(self):
        """"""
        Cwp = pcr.scalar(1.0)
        P_24 = pcr.scalar(1.0)
        RCD = pcr.scalar(1.0)
        result = _surface_runoff.csrCalc(Cwp, P_24, RCD)
        expected = 1.0
        self.assertEqual(result, expected)

    def test_csrCalc_Cwp_P_24_RCD_eq_0(self):
        """"""
        Cwp = pcr.scalar(0.0)
        P_24 = pcr.scalar(0.0)
        RCD = pcr.scalar(0.0)
        with self.assertRaises(RuntimeError) as cm:
            _surface_runoff.csrCalc(Cwp, P_24, RCD)
        self.assertIn("pcrfdiv: operator /: Domain Error", str(cm.exception))

    @unittest.skip("Reassess need for testing var value range here")
    def test_csrCalc_RCD_eq_0(self):
        """"""
        Cwp = pcr.scalar(1.0)
        P_24 = pcr.scalar(1.0)
        RCD = pcr.scalar(0.0)
        # TODO: Create ValidationError Exception
        with self.assertRaises(Exception) as cm:
            _surface_runoff.csrCalc(Cwp, P_24, RCD)
        self.assertEqual(
            "The Regional Consecutive Dryness (RCD) level must be in the value range [1.0, 10.0]",
            str(cm.exception),
        )

    def test_csrCalc_None_values(self):
        """"""
        self.assertRaises(TypeError, _surface_runoff.csrCalc, None, None, None)

    def test_sRunoffCalc_cond1_true_cond2_true_cond3_true(self):
        """"""
        Ao = pcr.scalar(1.0)  # cond1 Ao == 1
        prec = pcr.scalar(2.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        I = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, I, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        self.assertEqual(result, expected)

    def test_sRunoffCalc_cond1_true_cond2_true_cond3_false(self):
        """"""
        Ao = pcr.scalar(1.0)  # cond1 Ao == 1
        prec = pcr.scalar(2.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(1.5)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        I = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, I, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 2.0
        self.assertEqual(result, expected)

    def test_sRunoffCalc_cond1_true_cond2_false_cond3_true(self):
        """"""
        Ao = pcr.scalar(1.0)  # cond1 Ao == 1
        prec = pcr.scalar(1.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        I = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, I, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        self.assertEqual(result, expected)

    def test_sRunoffCalc_cond1_true_cond2_false_cond3_false(self):
        """"""
        Ao = pcr.scalar(1.0)  # cond1 Ao == 1
        prec = pcr.scalar(1.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(2.0)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        I = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, I, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        self.assertEqual(result, expected)

    def test_sRunoffCalc_cond1_false_cond2_true_cond3_true(self):
        """"""
        Ao = pcr.scalar(0.998)  # cond1 Ao == 1
        prec = pcr.scalar(2.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        I = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, I, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        self.assertEqual(result, expected)

    def test_sRunoffCalc_cond1_false_cond2_true_cond3_false(self):
        """"""
        Ao = pcr.scalar(0.998)  # cond1 Ao == 1
        prec = pcr.scalar(2.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(2.0)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        I = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, I, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        self.assertEqual(result, expected)

    def test_sRunoffCalc_cond1_false_cond2_false_cond3_true(self):
        """"""
        Ao = pcr.scalar(0.998)  # cond1 Ao == 1
        prec = pcr.scalar(1.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        I = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, I, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        self.assertEqual(result, expected)

    def test_sRunoffCalc_cond1_false_cond2_false_cond3_false(self):
        """"""
        Ao = pcr.scalar(0.998)  # cond1 Ao == 1
        prec = pcr.scalar(1.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(2.0)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        I = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, I, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        self.assertEqual(result, expected)

    def test_sRunoffCalc_None_values(self):
        """"""
        self.assertRaises(
            TypeError,
            _surface_runoff.sRunoffCalc,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )


if __name__ == "__main__":
    suite = unittest.makeSuite(SurfaceRunoffModuleTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
