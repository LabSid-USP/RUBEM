import pytest

import pcraster as pcr
from pcraster.framework import generalfunctions

from rubem.hydrological_processes import Evapotranspiration


class TestEvapotranspirationModule:

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.unit
    def test_get_water_stress_coef_None_values(self):
        with pytest.raises(TypeError):
            Evapotranspiration.get_water_stress_coef_et_vegeted_area(None, None, None)

    @pytest.mark.unit
    def test_get_water_stress_coef_ks_cond_true(self):
        TUr = pcr.scalar(2.0)
        TUw = pcr.scalar(1.0)
        TUcc = pcr.scalar(3.0)
        field = Evapotranspiration.get_water_stress_coef_et_vegeted_area(TUr, TUw, TUcc)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.6309297680854797
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_get_water_stress_coef_ks_cond_false(self):
        TUr = pcr.scalar(1.0)
        TUw = pcr.scalar(2.0)
        TUcc = pcr.scalar(3.0)
        field = Evapotranspiration.get_water_stress_coef_et_vegeted_area(TUr, TUw, TUcc)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_get_water_stress_coef_TUcc_minus_TUw_eq_neg_1(self):
        TUr = pcr.scalar(3.0)
        TUw = pcr.scalar(2.0)
        TUcc = pcr.scalar(0.0)
        with pytest.raises(RuntimeError, match="ln: function ln: Domain Error") as cm:
            Evapotranspiration.get_water_stress_coef_et_vegeted_area(TUr, TUw, TUcc)

    @pytest.mark.unit
    def test_get_water_stress_coef_TUr_minus_TUw_eq_neg_1(self):
        TUr = pcr.scalar(1.0)
        TUw = pcr.scalar(2.0)
        TUcc = pcr.scalar(2.0)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            Evapotranspiration.get_water_stress_coef_et_vegeted_area(TUr, TUw, TUcc)

    @pytest.mark.unit
    def test_etavCalc_valid_values(self):
        ETp = pcr.scalar(1.0)
        Kc = pcr.scalar(1.0)
        Ks = pcr.scalar(1.0)
        field = Evapotranspiration.get_et_vegetated_area(ETp, Kc, Ks)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etavCalc_None_values(self):
        with pytest.raises(TypeError):
            Evapotranspiration.get_et_vegetated_area(None, None, None)

    @pytest.mark.unit
    def test_kpCalc_B_eq_0(self):
        B = 0.0
        U_2 = 1.0
        UR = 1.0
        with pytest.raises(RuntimeError, match="ln: function ln: Domain Error") as cm:
            Evapotranspiration.get_pan_coef_et_open_water_area(B, U_2, UR)

    @pytest.mark.unit
    def test_kpCalc_valid_values(self):
        B = 1.0
        U_2 = 1.0
        UR = 1.0
        field = Evapotranspiration.get_pan_coef_et_open_water_area(B, U_2, UR)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.4861240088939667
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_kpCalc_None_values(self):
        with pytest.raises(RuntimeError):
            Evapotranspiration.get_pan_coef_et_open_water_area(None, None, None)

    @pytest.mark.unit
    def test_etaoCalc_cond1_true_cond_2_true(self):
        ETp = pcr.scalar(4.0)
        Kp = pcr.scalar(2.0)
        prec = pcr.scalar(1.0)
        Ao = pcr.scalar(1.0)
        field = Evapotranspiration.get_actual_et_open_water_area(ETp, Kp, prec, Ao)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etaoCalc_cond1_false_cond_2_false(self):
        ETp = pcr.scalar(2.0)
        Kp = pcr.scalar(2.0)
        prec = pcr.scalar(2.0)
        Ao = pcr.scalar(0.111)
        field = Evapotranspiration.get_actual_et_open_water_area(ETp, Kp, prec, Ao)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etaoCalc_cond1_true_cond_2_false(self):
        ETp = pcr.scalar(2.0)
        Kp = pcr.scalar(2.0)
        prec = pcr.scalar(2.0)
        Ao = pcr.scalar(1.0)
        field = Evapotranspiration.get_actual_et_open_water_area(ETp, Kp, prec, Ao)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etaoCalc_cond1_false_cond_2_true(self):
        ETp = pcr.scalar(4.0)
        Kp = pcr.scalar(2.0)
        prec = pcr.scalar(1.0)
        Ao = pcr.scalar(0.111)
        field = Evapotranspiration.get_actual_et_open_water_area(ETp, Kp, prec, Ao)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 2.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etaoCalc_None_values(self):
        with pytest.raises(TypeError):
            Evapotranspiration.get_pan_coef_et_open_water_area(None, None, None, None)

    @pytest.mark.unit
    def test_etasCalc_cond_true_gt_0(self):
        ETp = pcr.scalar(1.0)
        kc_min = pcr.scalar(1.0)
        Ks = pcr.scalar(1.0)
        field = Evapotranspiration.get_water_stress_coef_et_bare_soil_area(ETp, kc_min, Ks)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etasCalc_cond_false_eq_0(self):
        ETp = pcr.scalar(1.0)
        kc_min = pcr.scalar(1.0)
        Ks = pcr.scalar(0.0)
        field = Evapotranspiration.get_water_stress_coef_et_bare_soil_area(ETp, kc_min, Ks)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etasCalc_cond_false_lt_0(self):
        ETp = pcr.scalar(1.0)
        kc_min = pcr.scalar(1.0)
        Ks = pcr.scalar(-1.0)
        field = Evapotranspiration.get_water_stress_coef_et_bare_soil_area(ETp, kc_min, Ks)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = -1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etasCalc_None_values(self):
        with pytest.raises(TypeError):
            Evapotranspiration.get_water_stress_coef_et_bare_soil_area(None, None, None)
