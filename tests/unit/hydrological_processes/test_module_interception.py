import math

import pcraster as pcr
import pytest
from pcraster.framework import generalfunctions

from rubem.hydrological_processes import Interception


def _interception_equation(alfa, leaf_area_index, precipitation, rainy_days, a_v):
    """Evaluate the interception equations of ``get_interception`` in float64.

    The rate and the vegetated-area interception follow the ``interception-r``
    and ``interception-v`` equations of ``doc/source/overview.rst``; the daily
    limit is evaluated as ``Interception.get_interception`` does. The
    zero-precipitation guard is left out, so the helper is only defined for
    positive precipitation.
    """
    partial_den = 1 + precipitation * (1 - math.exp(-0.463 * leaf_area_index)) / (
        alfa * leaf_area_index
    )
    daily_interception_limit = alfa * leaf_area_index * (1 - 1 / partial_den)
    interception_rate = 1 - math.exp(-daily_interception_limit * rainy_days / precipitation)
    return a_v * precipitation * interception_rate


class TestInterceptionModule:
    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 0, 1)

    @pytest.mark.unit
    def test_srCalc_NDVI_lt_1(self):
        value = 0.555
        ndvi = pcr.scalar(value)
        field = Interception.get_reflectances_simple_ratio(ndvi)
        result = generalfunctions.getCellValue(field, 1, 1)
        expected = 3.49438214302063
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_srCalc_NDVI_eq_1(self):
        value = 1.0
        ndvi = pcr.scalar(value)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            Interception.get_reflectances_simple_ratio(ndvi)

    @pytest.mark.unit
    def test_srCalc_None_values(self):
        with pytest.raises(TypeError):
            Interception.get_reflectances_simple_ratio(None)

    @pytest.mark.unit
    def test_the_old_spelling_warns_and_computes_the_same_value(self):
        ndvi = pcr.scalar(0.555)
        expected = generalfunctions.getCellValue(
            Interception.get_reflectances_simple_ratio(ndvi), 1, 1
        )

        with pytest.warns(DeprecationWarning, match="get_reflectances_simple_ration"):
            field = Interception.get_reflectances_simple_ration(ndvi)

        assert generalfunctions.getCellValue(field, 1, 1) == pytest.approx(expected)

    @pytest.mark.unit
    def test_kcCalc(self):
        ndvi = pcr.scalar(0.555)
        ndvi_min = pcr.scalar(0.111)
        ndvi_max = pcr.scalar(0.777)
        kc_min = pcr.scalar(0.466)
        kc_max = pcr.scalar(0.933)
        field = Interception.get_crop_coef(ndvi, ndvi_min, ndvi_max, kc_min, kc_max)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.7773333787918091
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_kcCalc_NDVImax_eq_NDVImin(self):
        ndvi = pcr.scalar(0.555)
        ndvi_min = pcr.scalar(0.333)
        ndvi_max = pcr.scalar(0.333)
        kc_min = pcr.scalar(0.466)
        kc_max = pcr.scalar(0.933)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            Interception.get_crop_coef(ndvi, ndvi_min, ndvi_max, kc_min, kc_max)

    @pytest.mark.unit
    def test_kcCalc_None_values(self):
        with pytest.raises(TypeError):
            Interception.get_crop_coef(None, None, None, None, None)

    @pytest.mark.unit
    def test_fparCalc(self):
        fpar_min = pcr.scalar(0.555)
        fpar_max = pcr.scalar(0.999)
        sr = pcr.scalar(1.0)
        sr_min = pcr.scalar(0.75)
        sr_max = pcr.scalar(1.5)
        field = Interception.get_fpar(fpar_min, fpar_max, sr, sr_min, sr_max)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.703000009059906
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_fparCalc_SRmax_eq_SRmin(self):
        fpar_min = pcr.scalar(0.555)
        fpar_max = pcr.scalar(0.999)
        sr = pcr.scalar(1.0)
        sr_min = pcr.scalar(1.5)
        sr_max = pcr.scalar(1.5)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            Interception.get_fpar(fpar_min, fpar_max, sr, sr_min, sr_max)

    @pytest.mark.unit
    def test_fparCalc_None_values(self):
        with pytest.raises(TypeError):
            Interception.get_fpar(None, None, None, None, None)

    @pytest.mark.unit
    def test_laiCalc_None_values(self):
        with pytest.raises(TypeError):
            Interception.get_leaf_area_index(None, None, None)

    @pytest.mark.unit
    def test_laiCalc(self):
        fpar = pcr.scalar(0.7)
        fpar_max = pcr.scalar(0.9)
        lai_max = pcr.scalar(1.0)
        field = Interception.get_leaf_area_index(fpar, fpar_max, lai_max)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 0.5228787660
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_laiCalc_FPAR_gt_1(self):
        fpar = pcr.scalar(1.7)
        fpar_max = pcr.scalar(0.9)
        lai_max = pcr.scalar(1.0)
        with pytest.raises(RuntimeError, match="log10: function log10: Domain Error"):
            Interception.get_leaf_area_index(fpar, fpar_max, lai_max)

    @pytest.mark.unit
    def test_laiCalc_FPAR_eq_1(self):
        fpar = pcr.scalar(1.0)
        fpar_max = pcr.scalar(0.9)
        lai_max = pcr.scalar(1.0)
        with pytest.raises(RuntimeError, match="log10: function log10: Domain Error"):
            Interception.get_leaf_area_index(fpar, fpar_max, lai_max)

    @pytest.mark.unit
    def test_laiCalc_FPARmax_gt_1(self):
        fpar = pcr.scalar(0.7)
        fpar_max = pcr.scalar(1.9)
        lai_max = pcr.scalar(1.0)
        with pytest.raises(RuntimeError, match="log10: function log10: Domain Error"):
            Interception.get_leaf_area_index(fpar, fpar_max, lai_max)

    @pytest.mark.unit
    def test_laiCalc_FPARmax_eq_1(self):
        fpar = pcr.scalar(0.7)
        fpar_max = pcr.scalar(1.0)
        lai_max = pcr.scalar(1.0)
        with pytest.raises(RuntimeError, match="log10: function log10: Domain Error"):
            Interception.get_leaf_area_index(fpar, fpar_max, lai_max)

    @pytest.mark.unit
    def test_interceptionCalc_cond1_true_cond2_false(self):
        alfa = pcr.scalar(10.0)
        lai = pcr.scalar(12.0)
        precipitation = pcr.scalar(125.93)
        rainy_days = pcr.scalar(15)
        a_v = pcr.scalar(0.255)
        field = Interception.get_interception(alfa, lai, precipitation, rainy_days, a_v)
        result = generalfunctions.getCellValue(field, 0, 0)
        expected = 32.090572357177734
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_interceptionCalc_cond1_false_cond2_true(self):
        alfa = pcr.scalar(10.0)
        lai = pcr.scalar(12.0)
        precipitation = pcr.scalar(0.0)
        rainy_days = pcr.scalar(15)
        a_v = pcr.scalar(0.255)
        field = Interception.get_interception(alfa, lai, precipitation, rainy_days, a_v)
        result = generalfunctions.getCellValue(field, 0, 0)
        # The guard keeps the division finite; no interception without precipitation
        assert math.isfinite(result)
        expected = 0.0
        assert result == pytest.approx(expected)

    @pytest.mark.unit
    def test_interceptionCalc_cond1_true_cond2_false_alfa_eq_0(self):
        alfa = pcr.scalar(0.0)
        lai = pcr.scalar(1.0)
        precipitation = pcr.scalar(125.93)
        rainy_days = pcr.scalar(15)
        a_v = pcr.scalar(0.255)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            Interception.get_interception(alfa, lai, precipitation, rainy_days, a_v)

    @pytest.mark.unit
    def test_interceptionCalc_cond1_true_cond2_false_LAI_eq_0(self):
        alfa = pcr.scalar(0.01)
        lai = pcr.scalar(0.0)
        precipitation = pcr.scalar(125.93)
        rainy_days = pcr.scalar(15)
        a_v = pcr.scalar(0.255)
        with pytest.raises(RuntimeError, match="pcrfdiv: operator /: Domain Error"):
            Interception.get_interception(alfa, lai, precipitation, rainy_days, a_v)

    @pytest.mark.unit
    def test_interceptionCalc_None_values(self):
        with pytest.raises(RuntimeError):
            Interception.get_interception(None, None, None, None, None)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("alfa", "lai", "precipitation", "rainy_days", "a_v"),
        [
            (10.0, 12.0, 125.93, 15, 0.255),
            (4.5, 3.0, 100.0, 12, 0.6),
        ],
    )
    def test_interceptionCalc_positive_precipitation_matches_the_equation(
        self, alfa, lai, precipitation, rainy_days, a_v
    ):
        expected = _interception_equation(alfa, lai, precipitation, rainy_days, a_v)
        field = Interception.get_interception(
            pcr.scalar(alfa),
            pcr.scalar(lai),
            pcr.scalar(precipitation),
            pcr.scalar(rainy_days),
            pcr.scalar(a_v),
        )
        result = generalfunctions.getCellValue(field, 0, 0)
        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.unit
    def test_interceptionCalc_small_positive_precipitation_keeps_denominator(self):
        """Guard issue #319: positive precipitation reaches the denominator unchanged.

        The zero-precipitation guard used to add 1e-5 to every precipitation
        value, so for P = 1e-4 the denominator of I_R became 1.1e-4 instead of
        1e-4. The equation gives I_R = 1 - exp(-I_D * 2 / 1e-4), about 0.5236,
        and I about 5.23e-5; the old guard gave about 4.90e-5, roughly 6 percent
        lower. Only a zero precipitation may be replaced by the small constant.

        PCRaster evaluates the fields in float32, and the cancellation in
        1 - 1 / partial_den (partial_den is within 4e-5 of 1 here) can move the
        result by up to about 0.2 percent of the float64 value depending on the
        platform's float32 rounding, so the tolerance must stay well above that
        and well below the 6 percent error of the old guard.
        """
        alfa, lai, precipitation, rainy_days, a_v = 1.0, 1.0, 1e-4, 2, 1.0
        expected = _interception_equation(alfa, lai, precipitation, rainy_days, a_v)
        field = Interception.get_interception(
            pcr.scalar(alfa),
            pcr.scalar(lai),
            pcr.scalar(precipitation),
            pcr.scalar(rainy_days),
            pcr.scalar(a_v),
        )
        result = generalfunctions.getCellValue(field, 0, 0)
        assert result == pytest.approx(expected, rel=1e-2)
