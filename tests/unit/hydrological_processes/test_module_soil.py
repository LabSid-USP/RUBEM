import math

import pcraster as pcr
import pytest
from pcraster.framework import generalfunctions

from rubem.hydrological_processes import Soil


class TestLateralFlowSoilModule:
    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.unit
    def test_lfCalc(self):
        f = pcr.scalar(1.0)
        kr = pcr.scalar(1.0)
        tur = pcr.scalar(1.0)
        tusat = pcr.scalar(1.0)
        field = Soil.get_lateral_flow(f, kr, tur, tusat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_lfCalc_TUsat_eq_0(self):
        f = pcr.scalar(1.0)
        kr = pcr.scalar(1.0)
        tur = pcr.scalar(1.0)
        tusat = pcr.scalar(0.0)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            Soil.get_lateral_flow(f, kr, tur, tusat)

    @pytest.mark.unit
    def test_lfCalc_None_values(self):
        with pytest.raises(TypeError):
            Soil.get_lateral_flow(None, None, None, None)


class TestRechargeSoilModule:
    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.unit
    def test_recCalc(self):
        f = pcr.scalar(0.50)
        kr = pcr.scalar(1.0)
        tur = pcr.scalar(1.0)
        tusat = pcr.scalar(1.0)
        field = Soil.get_recharge(f, kr, tur, tusat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.5
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_recCalc_TUsat_eq_0(self):
        f = pcr.scalar(1.0)
        kr = pcr.scalar(1.0)
        tur = pcr.scalar(1.0)
        tusat = pcr.scalar(0.0)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            Soil.get_recharge(f, kr, tur, tusat)

    @pytest.mark.unit
    def test_recCalc_None_values(self):
        with pytest.raises(TypeError):
            Soil.get_recharge(None, None, None, None)


class TestBaseFlowSoilModule:
    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.unit
    def test_baseflowCalc_cond_true(self):
        eb_prev = pcr.scalar(1.0)
        alpha = pcr.scalar(1.0)
        rec = pcr.scalar(1.0)
        tus = pcr.scalar(2.0)
        eb_lim = pcr.scalar(1.0)
        field = Soil.get_baseflow(eb_prev, alpha, rec, tus, eb_lim)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_baseflowCalc_cond_false_TUs_eq_EBlim(self):
        eb_prev = pcr.scalar(1.0)
        alpha = pcr.scalar(1.0)
        rec = pcr.scalar(1.0)
        tus = pcr.scalar(1.0)
        eb_lim = pcr.scalar(1.0)
        field = Soil.get_baseflow(eb_prev, alpha, rec, tus, eb_lim)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_baseflowCalc_cond_false_TUs_lt_EBlim(self):
        eb_prev = pcr.scalar(1.0)
        alpha = pcr.scalar(1.0)
        rec = pcr.scalar(1.0)
        tus = pcr.scalar(1.0)
        eb_lim = pcr.scalar(2.0)
        field = Soil.get_baseflow(eb_prev, alpha, rec, tus, eb_lim)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_baseflowCalc_capped_by_available_water(self):
        """Baseflow is limited to the water available in the saturated zone (issue #322)."""
        eb_prev = pcr.scalar(10.0)
        alpha = pcr.scalar(1.0)
        rec = pcr.scalar(0.5)
        tus = pcr.scalar(2.0)
        eb_lim = pcr.scalar(1.0)
        field = Soil.get_baseflow(eb_prev, alpha, rec, tus, eb_lim)
        result = generalfunctions.getCellValue(field, 0, 0)
        # Recession value (about 3.995) exceeds the available water (2.0 + 0.5)
        expected = 2.5
        assert result == pytest.approx(expected)
        # The saturated-zone balance ends at zero instead of going negative
        balance = Soil.get_actual_water_cont_sat_zone(tus, rec, field)
        balance_result = generalfunctions.getCellValue(balance, 0, 0)
        assert balance_result == pytest.approx(0.0, abs=1e-6)

    @pytest.mark.unit
    def test_baseflowCalc_not_capped_below_available_water(self):
        eb_prev = pcr.scalar(2.0)
        alpha = pcr.scalar(1.0)
        rec = pcr.scalar(1.0)
        tus = pcr.scalar(5.0)
        eb_lim = pcr.scalar(1.0)
        field = Soil.get_baseflow(eb_prev, alpha, rec, tus, eb_lim)
        result = generalfunctions.getCellValue(field, 0, 0)
        # Recession value (about 1.368) is below the available water (5.0 + 1.0),
        # so it is returned unchanged
        expected = 2.0 * math.exp(-1.0) + (1.0 - math.exp(-1.0)) * 1.0
        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.unit
    def test_baseflowCalc_cond_false_water_available(self):
        eb_prev = pcr.scalar(10.0)
        alpha = pcr.scalar(1.0)
        rec = pcr.scalar(0.5)
        tus = pcr.scalar(0.5)
        eb_lim = pcr.scalar(1.0)
        field = Soil.get_baseflow(eb_prev, alpha, rec, tus, eb_lim)
        result = generalfunctions.getCellValue(field, 0, 0)
        # Below the threshold no baseflow occurs even though water is available
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_baseflowCalc_None_values(self):
        with pytest.raises(TypeError):
            Soil.get_baseflow(None, None, None, None, None)


class TestSoilBalanceSoilModule:
    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.unit
    def test_turCalc_condw1_true_cond_true_cond3_true(self):
        tur_prev = pcr.scalar(5.0)
        prec = pcr.scalar(5.0)
        itp = pcr.scalar(1.0)
        es = pcr.scalar(1.0)
        lf = pcr.scalar(1.0)
        rec = pcr.scalar(1.0)
        etr = pcr.scalar(1.0)
        ao = pcr.scalar(1.1)
        tsat = pcr.scalar(5.5)
        field = Soil.get_actual_soil_moist_cont(tur_prev, prec, itp, es, lf, rec, etr, ao, tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 5.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_condw1_true_cond_true_cond3_false(self):
        tur_prev = pcr.scalar(5.0)
        prec = pcr.scalar(5.0)
        itp = pcr.scalar(1.0)
        es = pcr.scalar(1.0)
        lf = pcr.scalar(1.0)
        rec = pcr.scalar(1.0)
        etr = pcr.scalar(1.0)
        ao = pcr.scalar(1.1)
        tsat = pcr.scalar(4.5)
        field = Soil.get_actual_soil_moist_cont(tur_prev, prec, itp, es, lf, rec, etr, ao, tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 4.5
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_condw1_true_cond_false_cond3_true(self):
        tur_prev = pcr.scalar(1.0)
        prec = pcr.scalar(2.0)
        itp = pcr.scalar(1.0)
        es = pcr.scalar(1.0)
        lf = pcr.scalar(1.0)
        rec = pcr.scalar(1.0)
        etr = pcr.scalar(1.0)
        ao = pcr.scalar(1.1)
        tsat = pcr.scalar(5.5)
        field = Soil.get_actual_soil_moist_cont(tur_prev, prec, itp, es, lf, rec, etr, ao, tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_condw1_true_cond_false_cond3_false(self):
        tur_prev = pcr.scalar(1.0)
        prec = pcr.scalar(2.0)
        itp = pcr.scalar(1.0)
        es = pcr.scalar(1.0)
        lf = pcr.scalar(1.0)
        rec = pcr.scalar(1.0)
        etr = pcr.scalar(1.0)
        ao = pcr.scalar(1.1)
        tsat = pcr.scalar(0.0)
        field = Soil.get_actual_soil_moist_cont(tur_prev, prec, itp, es, lf, rec, etr, ao, tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_condw1_false_cond_true_cond3_true(self):
        tur_prev = pcr.scalar(5.0)
        prec = pcr.scalar(5.0)
        itp = pcr.scalar(1.0)
        es = pcr.scalar(1.0)
        lf = pcr.scalar(1.0)
        rec = pcr.scalar(1.0)
        etr = pcr.scalar(1.0)
        ao = pcr.scalar(1.0)
        tsat = pcr.scalar(5.5)
        field = Soil.get_actual_soil_moist_cont(tur_prev, prec, itp, es, lf, rec, etr, ao, tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 5.5
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_condw1_false_cond_true_cond3_false(self):
        tur_prev = pcr.scalar(5.0)
        prec = pcr.scalar(5.0)
        itp = pcr.scalar(1.0)
        es = pcr.scalar(1.0)
        lf = pcr.scalar(1.0)
        rec = pcr.scalar(1.0)
        etr = pcr.scalar(1.0)
        ao = pcr.scalar(1.0)
        tsat = pcr.scalar(4.5)
        field = Soil.get_actual_soil_moist_cont(tur_prev, prec, itp, es, lf, rec, etr, ao, tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 4.5
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_condw1_false_cond_false_cond3_true(self):
        tur_prev = pcr.scalar(1.0)
        prec = pcr.scalar(2.0)
        itp = pcr.scalar(1.0)
        es = pcr.scalar(1.0)
        lf = pcr.scalar(1.0)
        rec = pcr.scalar(1.0)
        etr = pcr.scalar(1.0)
        ao = pcr.scalar(1.0)
        tsat = pcr.scalar(5.5)
        field = Soil.get_actual_soil_moist_cont(tur_prev, prec, itp, es, lf, rec, etr, ao, tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 5.5
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_condw1_false_cond_false_cond3_false(self):
        tur_prev = pcr.scalar(1.0)
        prec = pcr.scalar(2.0)
        itp = pcr.scalar(1.0)
        es = pcr.scalar(1.0)
        lf = pcr.scalar(1.0)
        rec = pcr.scalar(1.0)
        etr = pcr.scalar(1.0)
        ao = pcr.scalar(1.0)
        tsat = pcr.scalar(0.0)
        field = Soil.get_actual_soil_moist_cont(tur_prev, prec, itp, es, lf, rec, etr, ao, tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_tusCalc(self):
        tus_prev = pcr.scalar(1.0)
        rec = pcr.scalar(1.0)
        eb = pcr.scalar(1.0)
        field = Soil.get_actual_water_cont_sat_zone(tus_prev, rec, eb)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_turCalc_None_values(self):
        with pytest.raises(TypeError):
            Soil.get_actual_soil_moist_cont(None, None, None, None, None, None, None, None, None)

    @pytest.mark.unit
    def test_tusCalc_None_values(self):
        with pytest.raises(TypeError):
            Soil.get_actual_water_cont_sat_zone(None, None, None)
