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
        tur = pcr.scalar(2.0)
        tuw = pcr.scalar(1.0)
        tucc = pcr.scalar(3.0)
        field = Evapotranspiration.get_water_stress_coef_et_vegeted_area(tur, tuw, tucc)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.6309297680854797
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_get_water_stress_coef_ks_cond_false(self):
        tur = pcr.scalar(1.0)
        tuw = pcr.scalar(2.0)
        tucc = pcr.scalar(3.0)
        field = Evapotranspiration.get_water_stress_coef_et_vegeted_area(tur, tuw, tucc)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_get_water_stress_coef_TUcc_minus_TUw_eq_neg_1(self):
        tur = pcr.scalar(3.0)
        tuw = pcr.scalar(2.0)
        tucc = pcr.scalar(0.0)
        with pytest.raises(RuntimeError, match="ln: function ln: Domain Error") as cm:
            Evapotranspiration.get_water_stress_coef_et_vegeted_area(tur, tuw, tucc)

    @pytest.mark.unit
    def test_get_water_stress_coef_TUr_minus_TUw_eq_neg_1(self):
        tur = pcr.scalar(1.0)
        tuw = pcr.scalar(2.0)
        tucc = pcr.scalar(2.0)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            Evapotranspiration.get_water_stress_coef_et_vegeted_area(tur, tuw, tucc)

    @pytest.mark.unit
    def test_etavCalc_valid_values(self):
        etp = pcr.scalar(1.0)
        kc = pcr.scalar(1.0)
        ks = pcr.scalar(1.0)
        field = Evapotranspiration.get_et_vegetated_area(etp, kc, ks)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etavCalc_None_values(self):
        with pytest.raises(TypeError):
            Evapotranspiration.get_et_vegetated_area(None, None, None)

    @pytest.mark.unit
    def test_kpCalc_B_eq_0(self):
        fetch_dist = 0
        wind = 1.0
        relat_humidity = 1.0
        with pytest.raises(RuntimeError, match="ln: function ln: Domain Error") as cm:
            Evapotranspiration.get_pan_coef_et_open_water_area(fetch_dist, wind, relat_humidity)

    @pytest.mark.unit
    def test_kpCalc_valid_values(self):
        fetch_dist = 1
        wind = 1.0
        relat_humidity = 1.0
        field = Evapotranspiration.get_pan_coef_et_open_water_area(fetch_dist, wind, relat_humidity)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.4861240088939667
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_kpCalc_None_values(self):
        with pytest.raises(RuntimeError):
            Evapotranspiration.get_pan_coef_et_open_water_area(None, None, None)

    @pytest.mark.unit
    def test_etaoCalc_cond1_true_cond_2_true(self):
        etp = pcr.scalar(4.0)
        kp = pcr.scalar(2.0)
        prec = pcr.scalar(1.0)
        ao = pcr.scalar(1.0)
        field = Evapotranspiration.get_actual_et_open_water_area(etp, kp, prec, ao)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etaoCalc_cond1_false_cond_2_false(self):
        etp = pcr.scalar(2.0)
        kp = pcr.scalar(2.0)
        prec = pcr.scalar(2.0)
        ao = pcr.scalar(0.111)
        field = Evapotranspiration.get_actual_et_open_water_area(etp, kp, prec, ao)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etaoCalc_cond1_true_cond_2_false(self):
        etp = pcr.scalar(2.0)
        kp = pcr.scalar(2.0)
        prec = pcr.scalar(2.0)
        ao = pcr.scalar(1.0)
        field = Evapotranspiration.get_actual_et_open_water_area(etp, kp, prec, ao)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etaoCalc_cond1_false_cond_2_true(self):
        etp = pcr.scalar(4.0)
        kp = pcr.scalar(2.0)
        prec = pcr.scalar(1.0)
        ao = pcr.scalar(0.111)
        field = Evapotranspiration.get_actual_et_open_water_area(etp, kp, prec, ao)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 2.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etaoCalc_None_values(self):
        with pytest.raises(TypeError):
            Evapotranspiration.get_pan_coef_et_open_water_area(None, None, None, None)

    @pytest.mark.unit
    def test_etasCalc_cond_true_gt_0(self):
        etp = pcr.scalar(1.0)
        kc_min = pcr.scalar(1.0)
        ks = pcr.scalar(1.0)
        field = Evapotranspiration.get_water_stress_coef_et_bare_soil_area(etp, kc_min, ks)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etasCalc_cond_false_eq_0(self):
        etp = pcr.scalar(1.0)
        kc_min = pcr.scalar(1.0)
        ks = pcr.scalar(0.0)
        field = Evapotranspiration.get_water_stress_coef_et_bare_soil_area(etp, kc_min, ks)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etasCalc_cond_false_lt_0(self):
        etp = pcr.scalar(1.0)
        kc_min = pcr.scalar(1.0)
        ks = pcr.scalar(-1.0)
        field = Evapotranspiration.get_water_stress_coef_et_bare_soil_area(etp, kc_min, ks)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = -1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_etasCalc_None_values(self):
        with pytest.raises(TypeError):
            Evapotranspiration.get_water_stress_coef_et_bare_soil_area(None, None, None)
