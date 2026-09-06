"""Conformity of the evapotranspiration module with the published formulation.

Every expectation below is evaluated in float64 from the equation printed in the
journal supplement (equations S21 to S30, PDF page 9). PCRaster scalar fields are
Float32, so results are compared with ``pytest.approx(rel=1e-5)``; exact
comparisons are used only where the formula yields an exact 0.
"""

import math

import pcraster as pcr
import pytest
from pcraster.framework import generalfunctions

from rubem.hydrological_processes import Evapotranspiration, Interception

# Confirmed model rule for open water cells (alpha_W = 1): ET_R,W is capped at P_m.
OPEN_WATER_RULE_ISSUE = "https://github.com/LabSid-USP/RUBEM/issues/331"


def _cell(field) -> float:
    """Return the value of the single cell of a 1x1 field."""
    return generalfunctions.getCellValue(field, 0, 0)


@pytest.fixture(autouse=True)
def single_cell_clone():
    pcr.setclone(1, 1, 1, 1, 1)


class TestCropCoefS23:
    """Supplement S23, PDF page 9.

    kc = kc_min + (kc_max - kc_min) (NDVI - NDVI_min) / (NDVI_max - NDVI_min).
    """

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("ndvi", "ndvi_min", "ndvi_max", "kc_min", "kc_max"),
        [
            (0.55, 0.20, 0.80, 0.40, 1.20),
            (0.30, 0.10, 0.90, 0.60, 0.95),
            (0.71, 0.35, 0.75, 0.30, 1.05),
        ],
    )
    def test_interpolation(self, ndvi, ndvi_min, ndvi_max, kc_min, kc_max):
        """Linear interpolation of kc between kc_min and kc_max (S23, PDF page 9)."""
        assert ndvi > 1.1 * ndvi_min, "S24 must not apply to the interpolation cases"
        # S23: kc = kc_min + (kc_max - kc_min) * (NDVI - NDVI_min) / (NDVI_max - NDVI_min)
        expected = kc_min + (kc_max - kc_min) * (ndvi - ndvi_min) / (ndvi_max - ndvi_min)

        result = _cell(
            Interception.get_crop_coef(
                pcr.scalar(ndvi),
                pcr.scalar(ndvi_min),
                pcr.scalar(ndvi_max),
                pcr.scalar(kc_min),
                pcr.scalar(kc_max),
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    def test_ndvi_max_gives_kc_max(self):
        """At NDVI = NDVI_max the interpolation of S23 returns kc_max (PDF page 9)."""
        ndvi_min, ndvi_max, kc_min, kc_max = 0.20, 0.80, 0.40, 1.20
        # S23 with NDVI = NDVI_max: kc = kc_min + (kc_max - kc_min) * 1
        expected = kc_max

        result = _cell(
            Interception.get_crop_coef(
                pcr.scalar(ndvi_max),
                pcr.scalar(ndvi_min),
                pcr.scalar(ndvi_max),
                pcr.scalar(kc_min),
                pcr.scalar(kc_max),
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)


class TestWaterStressCoefS26S27:
    """Supplement S26 and S27, PDF page 9.

    ks = ln(TU_R - TU_PM + 1) / ln(TU_CC - TU_PM + 1); if TU_R < TU_PM then ks = 0.
    """

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("tu_r", "tu_pm", "tu_cc"),
        [
            (80.0, 40.0, 150.0),
            (25.5, 12.0, 60.0),
            (300.0, 90.0, 320.0),
        ],
    )
    def test_ks_between_wilting_point_and_field_capacity(self, tu_r, tu_pm, tu_cc):
        """ks = ln(TU_R - TU_PM + 1) / ln(TU_CC - TU_PM + 1) (S26, PDF page 9), all in mm."""
        assert tu_pm < tu_r <= tu_cc
        # S26: ks = ln(TU_R - TU_PM + 1) / ln(TU_CC - TU_PM + 1)
        expected = math.log(tu_r - tu_pm + 1.0) / math.log(tu_cc - tu_pm + 1.0)

        result = _cell(
            Evapotranspiration.get_water_stress_coef_et_vegetated_area(
                pcr.scalar(tu_r), pcr.scalar(tu_pm), pcr.scalar(tu_cc)
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    def test_ks_is_one_at_field_capacity(self):
        """At TU_R = TU_CC the numerator and denominator of S26 coincide: ks = 1 (PDF page 9)."""
        tu_pm, tu_cc = 40.0, 150.0
        # S26 with TU_R = TU_CC: ks = ln(TU_CC - TU_PM + 1) / ln(TU_CC - TU_PM + 1) = 1
        expected = 1.0

        result = _cell(
            Evapotranspiration.get_water_stress_coef_et_vegetated_area(
                pcr.scalar(tu_cc), pcr.scalar(tu_pm), pcr.scalar(tu_cc)
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("tu_r", "tu_pm", "tu_cc"),
        [
            (30.0, 40.0, 150.0),
            (0.0, 12.0, 60.0),
        ],
    )
    def test_ks_is_zero_below_wilting_point(self, tu_r, tu_pm, tu_cc):
        """If TU_R < TU_PM then ks = 0 (S27, PDF page 9).

        The model reaches 0 through ln(1) = 0, which is exact in Float32, so the
        comparison is exact.
        """
        assert tu_r < tu_pm
        # S27: ks = 0
        expected = 0.0

        result = _cell(
            Evapotranspiration.get_water_stress_coef_et_vegetated_area(
                pcr.scalar(tu_r), pcr.scalar(tu_pm), pcr.scalar(tu_cc)
            )
        )

        assert result == expected

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(("tu_pm", "tu_cc"), [(40.0, 150.0), (12.0, 60.0)])
    def test_ks_is_zero_at_the_wilting_point(self, tu_pm, tu_cc):
        """At TU_R = TU_PM both S26 and S27 give ks = 0 (PDF page 9).

        S26 reduces to ln(1) / ln(TU_CC - TU_PM + 1) = 0 and S27 applies only
        below TU_PM, so the two branches agree on the boundary. ln(1) = 0 is
        exact in Float32, so the comparison is exact.
        """
        # S26 with TU_R = TU_PM: ks = ln(1) / ln(TU_CC - TU_PM + 1) = 0
        expected = 0.0

        result = _cell(
            Evapotranspiration.get_water_stress_coef_et_vegetated_area(
                pcr.scalar(tu_pm), pcr.scalar(tu_pm), pcr.scalar(tu_cc)
            )
        )

        assert result == expected


class TestEtVegetatedAreaS22:
    """Supplement S22, PDF page 9: ET_R,V = ET_P kc ks."""

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("et_p", "kc", "ks"),
        [
            (120.0, 0.85, 0.65),
            (95.5, 1.10, 0.92),
            (140.0, 0.40, 0.0),
        ],
    )
    def test_et_vegetated_area(self, et_p, kc, ks):
        """ET_R,V = ET_P kc ks (S22, PDF page 9)."""
        # S22: ET_R,V = ET_P * kc * ks
        expected = et_p * kc * ks

        result = _cell(
            Evapotranspiration.get_et_vegetated_area(
                pcr.scalar(et_p), pcr.scalar(kc), pcr.scalar(ks)
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)


class TestEtBareSoilAreaS25:
    """Supplement S25, PDF page 9: ET_R,S = ET_P kc_min ks."""

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("et_p", "kc_min", "ks"),
        [
            (120.0, 0.40, 0.65),
            (95.5, 0.60, 0.92),
        ],
    )
    def test_et_bare_soil_area(self, et_p, kc_min, ks):
        """ET_R,S = ET_P kc_min ks (S25, PDF page 9)."""
        # S25: ET_R,S = ET_P * kc_min * ks
        expected = et_p * kc_min * ks

        result = _cell(
            Evapotranspiration.get_water_stress_coef_et_bare_soil_area(
                pcr.scalar(et_p), pcr.scalar(kc_min), pcr.scalar(ks)
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    def test_et_bare_soil_area_zero_when_ks_is_zero(self):
        """With ks = 0 (S27) the product of S25 is exactly 0 (PDF page 9)."""
        et_p, kc_min = 120.0, 0.40
        # S25 with ks = 0: ET_R,S = ET_P * kc_min * 0 = 0
        expected = 0.0

        result = _cell(
            Evapotranspiration.get_water_stress_coef_et_bare_soil_area(
                pcr.scalar(et_p), pcr.scalar(kc_min), pcr.scalar(0.0)
            )
        )

        assert result == expected


class TestEtOpenWaterAreaS28:
    """Supplement S28, PDF page 9: ET_R,W = ET_P / kp.

    On cells fully covered by water (alpha_W = 1) the model also caps ET_R,W at
    P_m, a confirmed rule documented in
    https://github.com/LabSid-USP/RUBEM/issues/331.
    """

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("et_p", "kp", "p_m", "a_w"),
        [
            (130.0, 0.80, 40.0, 0.0),
            (130.0, 0.80, 40.0, 0.35),
            (90.0, 0.75, 200.0, 0.6),
        ],
    )
    def test_plain_quotient_on_non_water_cell(self, et_p, kp, p_m, a_w):
        """ET_R,W = ET_P / kp whatever P_m is when alpha_W != 1 (S28, PDF page 9)."""
        # S28: ET_R,W = ET_P / kp
        expected = et_p / kp

        result = _cell(
            Evapotranspiration.get_actual_et_open_water_area(
                pcr.scalar(et_p), pcr.scalar(kp), pcr.scalar(p_m), pcr.scalar(a_w)
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("et_p", "kp", "p_m"),
        [
            (130.0, 0.80, 40.0),
            (60.0, 0.70, 85.0),
        ],
    )
    def test_water_cell_capped_at_precipitation(self, et_p, kp, p_m):
        """On a water cell ET_R,W = min(ET_P / kp, P_m) and the cap binds (S28 plus issue #331).

        Confirmed rule: https://github.com/LabSid-USP/RUBEM/issues/331.
        """
        assert et_p / kp > p_m, "the parameter set must make the cap bind"
        # S28 quotient capped at P_m: ET_R,W = min(ET_P / kp, P_m) = P_m
        expected = min(et_p / kp, p_m)

        result = _cell(
            Evapotranspiration.get_actual_et_open_water_area(
                pcr.scalar(et_p), pcr.scalar(kp), pcr.scalar(p_m), pcr.scalar(1.0)
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("et_p", "kp", "p_m"),
        [
            (90.0, 0.75, 200.0),
            (45.0, 0.90, 51.0),
        ],
    )
    def test_water_cell_uncapped(self, et_p, kp, p_m):
        """On a water cell with ET_P / kp <= P_m the S28 quotient is returned (PDF page 9).

        Confirmed rule: https://github.com/LabSid-USP/RUBEM/issues/331.
        """
        assert et_p / kp <= p_m, "the parameter set must leave the cap inactive"
        # S28 quotient capped at P_m: ET_R,W = min(ET_P / kp, P_m) = ET_P / kp
        expected = min(et_p / kp, p_m)

        result = _cell(
            Evapotranspiration.get_actual_et_open_water_area(
                pcr.scalar(et_p), pcr.scalar(kp), pcr.scalar(p_m), pcr.scalar(1.0)
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)


class TestPanCoefS29:
    """Supplement S29, PDF page 9: kp = 0.482 + 0.024 ln(B) - 0.000376 U_2 + 0.0045 UR.

    The model reads kp from an input series; the helper is kept for
    preprocessing (https://github.com/LabSid-USP/RUBEM/issues/330), so this is a
    formula-only check.
    """

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("fetch_distance", "wind_speed", "relative_humidity"),
        [
            (25, 2.0, 70.0),
            (20, 3.5, 55.0),
            (30, 1.2, 85.0),
        ],
    )
    def test_pan_coef(self, fetch_distance, wind_speed, relative_humidity):
        """kp = 0.482 + 0.024 ln(B) - 0.000376 U_2 + 0.0045 UR (S29, PDF page 9)."""
        # S29: kp = 0.482 + 0.024 * ln(B) - 0.000376 * U_2 + 0.0045 * UR
        expected = (
            0.482
            + 0.024 * math.log(fetch_distance)
            - 0.000376 * wind_speed
            + 0.0045 * relative_humidity
        )

        result = _cell(
            Evapotranspiration.get_pan_coef_et_open_water_area(
                fetch_distance, wind_speed, relative_humidity
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)
