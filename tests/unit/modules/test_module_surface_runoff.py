import pytest

import pcraster as pcr
from pcraster.framework import generalfunctions

from rubem.modules import _surface_runoff


class SurfaceRunoffModuleTest:

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.unit
    def test_chCalc(self):
        TUr = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(1.0)
        Tsat = pcr.scalar(1.0)
        b = pcr.scalar(1.0)
        result = _surface_runoff.chCalc(TUr, dg, Zr, Tsat, b)
        expected = 0.1
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_chCalc_dg_eq_0(self):
        TUr = pcr.scalar(1.0)
        dg = pcr.scalar(0.0)
        Zr = pcr.scalar(1.0)
        Tsat = pcr.scalar(1.0)
        b = pcr.scalar(1.0)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _surface_runoff.chCalc(TUr, dg, Zr, Tsat, b)

    @pytest.mark.unit
    def test_chCalc_Zr_eq_0(self):
        TUr = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(0.0)
        Tsat = pcr.scalar(1.0)
        b = pcr.scalar(1.0)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _surface_runoff.chCalc(TUr, dg, Zr, Tsat, b)

    @pytest.mark.unit
    def test_chCalc_Tsat_eq_0(self):
        TUr = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(1.0)
        Tsat = pcr.scalar(0.0)
        b = pcr.scalar(1.0)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _surface_runoff.chCalc(TUr, dg, Zr, Tsat, b)

    @pytest.mark.unit
    def test_chCalc_None_values(self):
        with pytest.raises(TypeError):
            _surface_runoff.chCalc(None, None, None, None, None)

    @pytest.mark.unit
    def test_cperCalc(self):
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
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_cperCalc_dg_eq_0(self):
        TUw = pcr.scalar(1.0)
        dg = pcr.scalar(0.0)
        Zr = pcr.scalar(1.0)
        S = pcr.scalar(1.0)
        manning = pcr.scalar(1.0)
        w1 = 0.333
        w2 = 0.333
        w3 = 0.334
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _surface_runoff.cperCalc(TUw, dg, Zr, S, manning, w1, w2, w3)

    @pytest.mark.unit
    def test_cperCalc_Zr_eq_0(self):
        TUw = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(0.0)
        S = pcr.scalar(1.0)
        manning = pcr.scalar(1.0)
        w1 = 0.333
        w2 = 0.333
        w3 = 0.334
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _surface_runoff.cperCalc(TUw, dg, Zr, S, manning, w1, w2, w3)

    @pytest.mark.unit
    def test_cperCalc_manning_eq_0(self):
        TUw = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(1.0)
        S = pcr.scalar(1.0)
        manning = pcr.scalar(0.0)
        w1 = 0.333
        w2 = 0.333
        w3 = 0.334
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _surface_runoff.cperCalc(TUw, dg, Zr, S, manning, w1, w2, w3)

    @pytest.mark.unit
    def test_cperCalc_S_eq_minus_10(self):
        TUw = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(1.0)
        S = pcr.scalar(-10.0)
        manning = pcr.scalar(1.0)
        w1 = 0.333
        w2 = 0.333
        w3 = 0.334
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _surface_runoff.cperCalc(TUw, dg, Zr, S, manning, w1, w2, w3)

    @pytest.mark.unit
    def test_cperCalc_None_values(self):
        with pytest.raises(TypeError):
            _surface_runoff.cperCalc(None, None, None, None, None, None, None, None)

    @pytest.mark.unit
    def test_cimpCalc(self):
        ao = pcr.scalar(0.555)
        ai = pcr.scalar(0.255)
        field = _surface_runoff.cimpCalc(ao, ai)
        result = [
            generalfunctions.getCellValue(field[0], 0, 0),
            generalfunctions.getCellValue(field[1], 0, 0),
        ]
        expected = [0.8100000023841858, 0.6287978291511536]
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_cimpCalc_None_values(self):
        with pytest.raises(TypeError):
            _surface_runoff.cimpCalc(None, None)

    @pytest.mark.unit
    def test_cwpCalc(self):
        Aimp = pcr.scalar(1.0)
        Cper = pcr.scalar(1.0)
        Cimp = pcr.scalar(1.0)
        result = _surface_runoff.cwpCalc(Aimp, Cper, Cimp)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_cwpCalc_None_values(self):
        with pytest.raises(TypeError):
            _surface_runoff.cwpCalc(None, None, None)

    @pytest.mark.unit
    def test_csrCalc(self):
        Cwp = pcr.scalar(1.0)
        P_24 = pcr.scalar(1.0)
        RCD = pcr.scalar(1.0)
        result = _surface_runoff.csrCalc(Cwp, P_24, RCD)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_csrCalc_Cwp_P_24_RCD_eq_0(self):
        Cwp = pcr.scalar(0.0)
        P_24 = pcr.scalar(0.0)
        RCD = pcr.scalar(0.0)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _surface_runoff.csrCalc(Cwp, P_24, RCD)

    @pytest.mark.unit
    def test_csrCalc_None_values(self):
        with pytest.raises(TypeError):
            _surface_runoff.csrCalc(None, None, None)

    @pytest.mark.unit
    def test_sRunoffCalc_cond1_true_cond2_true_cond3_true(self):
        Ao = pcr.scalar(1.0)  # cond1 Ao == 1
        prec = pcr.scalar(2.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        Itp = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_sRunoffCalc_cond1_true_cond2_true_cond3_false(self):
        Ao = pcr.scalar(1.0)  # cond1 Ao == 1
        prec = pcr.scalar(2.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(1.5)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        Itp = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 2.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_sRunoffCalc_cond1_true_cond2_false_cond3_true(self):
        Ao = pcr.scalar(1.0)  # cond1 Ao == 1
        prec = pcr.scalar(1.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        Itp = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_sRunoffCalc_cond1_true_cond2_false_cond3_false(self):
        Ao = pcr.scalar(1.0)  # cond1 Ao == 1
        prec = pcr.scalar(1.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(2.0)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        Itp = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_sRunoffCalc_cond1_false_cond2_true_cond3_true(self):
        Ao = pcr.scalar(0.998)  # cond1 Ao == 1
        prec = pcr.scalar(2.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        Itp = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_sRunoffCalc_cond1_false_cond2_true_cond3_false(self):
        Ao = pcr.scalar(0.998)  # cond1 Ao == 1
        prec = pcr.scalar(2.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(2.0)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        Itp = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_sRunoffCalc_cond1_false_cond2_false_cond3_true(self):
        Ao = pcr.scalar(0.998)  # cond1 Ao == 1
        prec = pcr.scalar(1.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        Itp = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_sRunoffCalc_cond1_false_cond2_false_cond3_false(self):
        Ao = pcr.scalar(0.998)  # cond1 Ao == 1
        prec = pcr.scalar(1.0)  # cond2 (prec - ETao) > 0
        ETao = pcr.scalar(1.0)
        TUr = pcr.scalar(2.0)  # cond3 TUr == Tsat
        Tsat = pcr.scalar(1.0)
        Csr = pcr.scalar(1.0)
        Ch = pcr.scalar(1.0)
        Itp = pcr.scalar(1.0)
        field = _surface_runoff.sRunoffCalc(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_sRunoffCalc_None_values(self):
        with pytest.raises(TypeError):
            _surface_runoff.sRunoffCalc(None, None, None, None, None, None, None, None)
