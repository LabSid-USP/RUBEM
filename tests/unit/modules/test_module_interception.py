import pytest

import pcraster as pcr
from pcraster.framework import generalfunctions

from rubem.modules import _interception


class TestInterceptionModule:

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 0, 1)

    @pytest.mark.unit
    def test_srCalc_NDVI_lt_1(self):
        value = 0.555
        NDVI = pcr.scalar(value)
        field = _interception.srCalc(NDVI)
        result = generalfunctions.getCellValue(field, 1, 1)
        expected = 3.49438214302063
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_srCalc_NDVI_eq_1(self):
        value = 1.0
        NDVI = pcr.scalar(value)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _interception.srCalc(NDVI)

    @pytest.mark.unit
    def test_srCalc_None_values(self):
        with pytest.raises(TypeError):
            _interception.srCalc(None)

    @pytest.mark.unit
    def test_kcCalc(self):
        NDVI = pcr.scalar(0.555)
        ndvi_min = pcr.scalar(0.111)
        ndvi_max = pcr.scalar(0.777)
        kc_min = pcr.scalar(0.466)
        kc_max = pcr.scalar(0.933)
        field = _interception.kcCalc(NDVI, ndvi_min, ndvi_max, kc_min, kc_max)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.7773333787918091
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_kcCalc_NDVImax_eq_NDVImin(self):
        NDVI = pcr.scalar(0.555)
        ndvi_min = pcr.scalar(0.333)
        ndvi_max = pcr.scalar(0.333)
        kc_min = pcr.scalar(0.466)
        kc_max = pcr.scalar(0.933)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _interception.kcCalc(NDVI, ndvi_min, ndvi_max, kc_min, kc_max)

    @pytest.mark.unit
    def test_kcCalc_None_values(self):
        with pytest.raises(TypeError):
            _interception.kcCalc(None, None, None, None, None)

    @pytest.mark.unit
    def test_fparCalc(self):
        fpar_min = pcr.scalar(0.555)
        fpar_max = pcr.scalar(0.999)
        SR = pcr.scalar(1.0)
        sr_min = pcr.scalar(0.75)
        sr_max = pcr.scalar(1.5)
        field = _interception.fparCalc(fpar_min, fpar_max, SR, sr_min, sr_max)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.703000009059906
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_fparCalc_SRmax_eq_SRmin(self):
        fpar_min = pcr.scalar(0.555)
        fpar_max = pcr.scalar(0.999)
        SR = pcr.scalar(1.0)
        sr_min = pcr.scalar(1.5)
        sr_max = pcr.scalar(1.5)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _interception.fparCalc(fpar_min, fpar_max, SR, sr_min, sr_max)

    @pytest.mark.unit
    def test_fparCalc_None_values(self):
        with pytest.raises(TypeError):
            _interception.fparCalc(None, None, None, None, None)

    @pytest.mark.unit
    def test_laiCalc_None_values(self):
        with pytest.raises(TypeError):
            _interception.laiCalc(None, None, None)

    @pytest.mark.unit
    def test_laiCalc(self):
        FPAR = pcr.scalar(0.7)
        fpar_max = pcr.scalar(0.9)
        lai_max = pcr.scalar(1.0)
        field = _interception.laiCalc(FPAR, fpar_max, lai_max)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.5228787660
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_laiCalc_FPAR_gt_1(self):
        FPAR = pcr.scalar(1.7)
        fpar_max = pcr.scalar(0.9)
        lai_max = pcr.scalar(1.0)
        with pytest.raises(RuntimeError, match="log10: function log10: Domain Error"):
            _interception.laiCalc(FPAR, fpar_max, lai_max)

    @pytest.mark.unit
    def test_laiCalc_FPAR_eq_1(self):
        FPAR = pcr.scalar(1.0)
        fpar_max = pcr.scalar(0.9)
        lai_max = pcr.scalar(1.0)
        with pytest.raises(RuntimeError, match="log10: function log10: Domain Error"):
            _interception.laiCalc(FPAR, fpar_max, lai_max)

    @pytest.mark.unit
    def test_laiCalc_FPARmax_gt_1(self):
        FPAR = pcr.scalar(0.7)
        fpar_max = pcr.scalar(1.9)
        lai_max = pcr.scalar(1.0)
        with pytest.raises(RuntimeError, match="log10: function log10: Domain Error"):
            _interception.laiCalc(FPAR, fpar_max, lai_max)

    @pytest.mark.unit
    def test_laiCalc_FPARmax_eq_1(self):
        FPAR = pcr.scalar(0.7)
        fpar_max = pcr.scalar(1.0)
        lai_max = pcr.scalar(1.0)
        with pytest.raises(RuntimeError, match="log10: function log10: Domain Error"):
            _interception.laiCalc(FPAR, fpar_max, lai_max)

    @pytest.mark.unit
    def test_interceptionCalc_cond1_true_cond2_false(self):
        alfa = pcr.scalar(10.0)
        LAI = pcr.scalar(12.0)
        precipitation = pcr.scalar(125.93)
        rainy_days = pcr.scalar(15)
        a_v = pcr.scalar(0.255)
        field_tuple = _interception.interceptionCalc(alfa, LAI, precipitation, rainy_days, a_v)
        result_list = [generalfunctions.getCellValue(field, 0, 0) for field in field_tuple]
        expected_list = [
            61.33066177368164,
            0.999328076839447,
            125.84538269042969,
            32.090572357177734,
        ]
        assert result_list == pytest.approx(expected_list)

    @pytest.mark.unit
    def test_interceptionCalc_cond1_false_cond2_true(self):
        alfa = pcr.scalar(10.0)
        LAI = pcr.scalar(12.0)
        precipitation = pcr.scalar(0.0)
        rainy_days = pcr.scalar(15)
        a_v = pcr.scalar(0.255)
        field_tuple = _interception.interceptionCalc(alfa, LAI, precipitation, rainy_days, a_v)
        result_list = [generalfunctions.getCellValue(field, 0, 0) for field in field_tuple]
        expected_list = [0.0, 0.0, 0.0, 0.0]
        assert result_list == pytest.approx(expected_list)

    @pytest.mark.unit
    def test_interceptionCalc_cond1_true_cond2_false_alfa_eq_0(self):
        alfa = pcr.scalar(0.0)
        LAI = pcr.scalar(1.0)
        precipitation = pcr.scalar(125.93)
        rainy_days = pcr.scalar(15)
        a_v = pcr.scalar(0.255)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _interception.interceptionCalc(alfa, LAI, precipitation, rainy_days, a_v)

    @pytest.mark.unit
    def test_interceptionCalc_cond1_true_cond2_false_LAI_eq_0(self):
        alfa = pcr.scalar(0.01)
        LAI = pcr.scalar(0.0)
        precipitation = pcr.scalar(125.93)
        rainy_days = pcr.scalar(15)
        a_v = pcr.scalar(0.255)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            _interception.interceptionCalc(alfa, LAI, precipitation, rainy_days, a_v)

    @pytest.mark.unit
    def test_interceptionCalc_None_values(self):
        with pytest.raises(RuntimeError):
            _interception.interceptionCalc(None, None, None, None, None)
