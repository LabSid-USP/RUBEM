import pytest
import pcraster as pcr
from pcraster.framework import generalfunctions

from rubem.modules import _soil


class TestLateralFlowSoilModule:

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.unit
    def test_lfCalc(self):
        f = pcr.scalar(1.0)
        Kr = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)
        TUsat = pcr.scalar(1.0)
        field = _soil.lfCalc(f, Kr, TUr, TUsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_lfCalc_TUsat_eq_0(self):
        f = pcr.scalar(1.0)
        Kr = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)
        TUsat = pcr.scalar(0.0)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _soil.lfCalc(f, Kr, TUr, TUsat)

    @pytest.mark.unit
    def test_lfCalc_None_values(self):
        with pytest.raises(TypeError):
            _soil.lfCalc(None, None, None, None)


class TestRechargeSoilModule:

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.unit
    def test_recCalc(self):
        f = pcr.scalar(0.50)
        Kr = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)
        TUsat = pcr.scalar(1.0)
        field = _soil.recCalc(f, Kr, TUr, TUsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.5
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_recCalc_TUsat_eq_0(self):
        f = pcr.scalar(1.0)
        Kr = pcr.scalar(1.0)
        TUr = pcr.scalar(1.0)
        TUsat = pcr.scalar(0.0)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _soil.recCalc(f, Kr, TUr, TUsat)

    @pytest.mark.unit
    def test_recCalc_None_values(self):
        with pytest.raises(TypeError):
            _soil.recCalc(None, None, None, None)


class TestBaseFlowSoilModule:

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.unit
    def test_baseflowCalc_cond_true(self):
        EB_prev = pcr.scalar(1.0)
        alfaS = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        TUs = pcr.scalar(2.0)
        EB_lim = pcr.scalar(1.0)
        field = _soil.baseflowCalc(EB_prev, alfaS, REC, TUs, EB_lim)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_baseflowCalc_cond_false_TUs_eq_EBlim(self):
        EB_prev = pcr.scalar(1.0)
        alfaS = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        TUs = pcr.scalar(1.0)
        EB_lim = pcr.scalar(1.0)
        field = _soil.baseflowCalc(EB_prev, alfaS, REC, TUs, EB_lim)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_baseflowCalc_cond_false_TUs_lt_EBlim(self):
        EB_prev = pcr.scalar(1.0)
        alfaS = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        TUs = pcr.scalar(1.0)
        EB_lim = pcr.scalar(2.0)
        field = _soil.baseflowCalc(EB_prev, alfaS, REC, TUs, EB_lim)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_baseflowCalc_None_values(self):
        with pytest.raises(TypeError):
            _soil.baseflowCalc(None, None, None, None, None)


class TestSoilBalanceSoilModule:

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.unit
    def test_turCalc_condw1_true_cond_true_cond3_true(self):
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
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_condw1_true_cond_true_cond3_false(self):
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
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_condw1_true_cond_false_cond3_true(self):
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
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_condw1_true_cond_false_cond3_false(self):
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
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_condw1_false_cond_true_cond3_true(self):
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
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_condw1_false_cond_true_cond3_false(self):
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
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_condw1_false_cond_false_cond3_true(self):
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
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_condw1_false_cond_false_cond3_false(self):
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
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_tusCalc(self):
        TUsprev = pcr.scalar(1.0)
        REC = pcr.scalar(1.0)
        EB = pcr.scalar(1.0)
        field = _soil.tusCalc(TUsprev, REC, EB)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_None_values(self):
        with pytest.raises(TypeError):
            _soil.turCalc(None, None, None, None, None, None, None, None, None)

    @pytest.mark.unit
    def test_tusCalc_None_values(self):
        with pytest.raises(TypeError):
            _soil.tusCalc(None, None, None)
