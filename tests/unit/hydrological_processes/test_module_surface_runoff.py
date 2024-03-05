import pytest

import pcraster as pcr
from pcraster.framework import generalfunctions

from rubem.hydrological_processes import SurfaceRunoff


class TestSurfaceRunoffModule:

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
        field = SurfaceRunoff.get_coef_soil_moist_conditions(TUr, dg, Zr, Tsat, b)
        result = generalfunctions.getCellValue(field, 0, 0)
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
            SurfaceRunoff.get_coef_soil_moist_conditions(TUr, dg, Zr, Tsat, b)

    @pytest.mark.unit
    def test_chCalc_Zr_eq_0(self):
        TUr = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(0.0)
        Tsat = pcr.scalar(1.0)
        b = pcr.scalar(1.0)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            SurfaceRunoff.get_coef_soil_moist_conditions(TUr, dg, Zr, Tsat, b)

    @pytest.mark.unit
    def test_chCalc_Tsat_eq_0(self):
        TUr = pcr.scalar(1.0)
        dg = pcr.scalar(1.0)
        Zr = pcr.scalar(1.0)
        Tsat = pcr.scalar(0.0)
        b = pcr.scalar(1.0)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            SurfaceRunoff.get_coef_soil_moist_conditions(TUr, dg, Zr, Tsat, b)

    @pytest.mark.unit
    def test_chCalc_None_values(self):
        with pytest.raises(TypeError):
            SurfaceRunoff.get_coef_soil_moist_conditions(None, None, None, None, None)

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
        field = SurfaceRunoff.get_runoff_coef_permeable_areas(TUw, dg, Zr, S, manning, w1, w2, w3)
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
            SurfaceRunoff.get_runoff_coef_permeable_areas(TUw, dg, Zr, S, manning, w1, w2, w3)

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
            SurfaceRunoff.get_runoff_coef_permeable_areas(TUw, dg, Zr, S, manning, w1, w2, w3)

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
            SurfaceRunoff.get_runoff_coef_permeable_areas(TUw, dg, Zr, S, manning, w1, w2, w3)

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
            SurfaceRunoff.get_runoff_coef_permeable_areas(TUw, dg, Zr, S, manning, w1, w2, w3)

    @pytest.mark.unit
    def test_cperCalc_None_values(self):
        with pytest.raises(TypeError):
            SurfaceRunoff.get_runoff_coef_permeable_areas(
                None, None, None, None, None, None, None, None
            )

    @pytest.mark.unit
    def test_aimpCalc(self):
        ao = pcr.scalar(0.555)
        ai = pcr.scalar(0.255)
        field = SurfaceRunoff.get_impervious_surface_percent_per_grid_cell(ao, ai)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.8100000023841858
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_cimpCalc(self):
        cimp = pcr.scalar(1.0)
        field = SurfaceRunoff.get_runoff_coef_impervious_area(cimp)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.9920859932899475
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_aimpCalc_None_values(self):
        with pytest.raises(TypeError):
            SurfaceRunoff.get_impervious_surface_percent_per_grid_cell(None, None)

    @pytest.mark.unit
    def test_cimpCalc_None_values(self):
        with pytest.raises(TypeError):
            SurfaceRunoff.get_runoff_coef_impervious_area(None)

    @pytest.mark.unit
    def test_cwpCalc(self):
        aimp = pcr.scalar(1.0)
        cper = pcr.scalar(1.0)
        cimp = pcr.scalar(1.0)
        field = SurfaceRunoff.get_weighted_pot_runoff_coef(aimp, cper, cimp)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_cwpCalc_None_values(self):
        with pytest.raises(TypeError):
            SurfaceRunoff.get_weighted_pot_runoff_coef(None, None, None)

    @pytest.mark.unit
    def test_csrCalc(self):
        cwp = pcr.scalar(1.0)
        p_24 = pcr.scalar(1.0)
        rcd = pcr.scalar(1.0)
        field = SurfaceRunoff.get_actual_runoff_coef(cwp, p_24, rcd)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 1.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_csrCalc_Cwp_P_24_RCD_eq_0(self):
        cwp = pcr.scalar(0.0)
        p_24 = pcr.scalar(0.0)
        rcd = pcr.scalar(0.0)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            SurfaceRunoff.get_actual_runoff_coef(cwp, p_24, rcd)

    @pytest.mark.unit
    def test_csrCalc_None_values(self):
        with pytest.raises(TypeError):
            SurfaceRunoff.get_actual_runoff_coef(None, None, None)

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
        field = SurfaceRunoff.get_surface_runoff(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
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
        field = SurfaceRunoff.get_surface_runoff(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
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
        field = SurfaceRunoff.get_surface_runoff(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
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
        field = SurfaceRunoff.get_surface_runoff(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
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
        field = SurfaceRunoff.get_surface_runoff(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
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
        field = SurfaceRunoff.get_surface_runoff(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
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
        field = SurfaceRunoff.get_surface_runoff(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
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
        field = SurfaceRunoff.get_surface_runoff(Csr, Ch, prec, Itp, Ao, ETao, TUr, Tsat)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_sRunoffCalc_None_values(self):
        with pytest.raises(TypeError):
            SurfaceRunoff.get_surface_runoff(None, None, None, None, None, None, None, None)
