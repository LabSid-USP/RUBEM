"""Conformity tests for the surface runoff formulation (Supplement S4 to S13).

Every expectation below is evaluated in float64 with :mod:`math` directly from
the formula printed in the journal supplement (PDF pages 6 and 7) and only then
compared with the value produced by :class:`rubem.hydrological_processes.SurfaceRunoff`.
PCRaster fields are Float32, so the comparisons use ``pytest.approx(rel=1e-5)``:
the relative rounding of a Float32 (about 6e-8) grows by at most a few tens of
ULPs over the two or three arithmetic steps of each formula.

Confirmed model rules that go beyond the printed formulas (saturation-excess
runoff, open water floor) are asserted as documented behaviour and cite
https://github.com/LabSid-USP/RUBEM/issues/331.
"""

import math

import pcraster as pcr
import pytest
from pcraster.framework import generalfunctions

from rubem.hydrological_processes import SurfaceRunoff

ISSUE_331 = "https://github.com/LabSid-USP/RUBEM/issues/331"


def _cell(field) -> float:
    """Return the value of the single cell of a 1x1 field as a Python float."""
    return float(generalfunctions.getCellValue(field, 0, 0))


class TestRunoffCoefPermeableAreas:
    """Supplement S9, PDF page 6: C_per = w1 (0.02/n) + w2 (θ_PM/(1 - θ_PM)) + w3 (S/(10 + S))."""

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("theta_pm", "dg", "zr", "slope", "manning", "w1", "w2", "w3"),
        [
            (0.12, 1.3, 40.0, 5.0, 0.16, 0.4, 0.3, 0.3),
            (0.25, 1.5, 100.0, 25.0, 0.045, 0.2, 0.5, 0.3),
            (0.18, 1.2, 60.0, 0.08, 0.20, 0.3, 0.4, 0.3),
        ],
    )
    def test_cper_matches_printed_formula(self, theta_pm, dg, zr, slope, manning, w1, w2, w3):
        """Supplement S9, PDF page 6.

        The printed formula uses the dimensionless wilting point θ_PM. The
        code receives the wilting point as a moisture content in mm
        (TU_w = θ_PM dg Zr 10, the same volumetric conversion as S11) and
        converts it back, so the argument is built from θ_PM here and the
        expectation uses θ_PM itself. S is passed as ``pcr.slope(dem)``
        returns it (rise over run); the unit question is open, since S9 calls S
        a percentage while the model feeds a dimensionless gradient, so both
        magnitudes are exercised.
        """
        # S9: C_per = w1 (0.02 / n) + w2 (θ_PM / (1 - θ_PM)) + w3 (S / (10 + S))
        expected = (
            w1 * (0.02 / manning)
            + w2 * (theta_pm / (1.0 - theta_pm))
            + w3 * (slope / (10.0 + slope))
        )
        tuw_mm = theta_pm * dg * zr * 10.0

        result = SurfaceRunoff.get_runoff_coef_permeable_areas(
            pcr.scalar(tuw_mm),
            pcr.scalar(dg),
            pcr.scalar(zr),
            pcr.scalar(slope),
            pcr.scalar(manning),
            w1,
            w2,
            w3,
        )

        # Float32 fields: rel=1e-5 covers the rounding of the three-term sum.
        assert _cell(result) == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(("dg", "zr"), [(1.1, 30.0), (1.6, 120.0)])
    def test_cper_converts_the_wilting_point_from_mm(self, dg, zr):
        """Supplement S9, PDF page 6: the mm wilting point is divided by dg Zr 10.

        The code receives TU_w = θ_PM dg Zr 10 (mm) and must divide it back by
        dg Zr 10 to recover the dimensionless θ_PM of the printed formula, so
        the same θ_PM has to give the same C_per whatever dg and Zr are.
        """
        theta_pm, slope, manning, w1, w2, w3 = 0.18, 0.05, 0.15, 0.4, 0.4, 0.2
        # S9: C_per = w1 (0.02 / n) + w2 (θ_PM / (1 - θ_PM)) + w3 (S / (10 + S))
        expected = (
            w1 * (0.02 / manning)
            + w2 * (theta_pm / (1.0 - theta_pm))
            + w3 * (slope / (10.0 + slope))
        )

        result = SurfaceRunoff.get_runoff_coef_permeable_areas(
            pcr.scalar(theta_pm * dg * zr * 10.0),
            pcr.scalar(dg),
            pcr.scalar(zr),
            pcr.scalar(slope),
            pcr.scalar(manning),
            w1,
            w2,
            w3,
        )

        # Float32 fields: rel=1e-5 covers the rounding of the mm conversion and the sum.
        assert _cell(result) == pytest.approx(expected, rel=1e-5)


class TestRunoffCoefImperviousArea:
    """Supplement S7, PDF page 6: C_imp = 0.09 exp(2.4 A_imp)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize("a_imp", [0.15, 0.5, 1.0])
    def test_cimp_matches_printed_formula(self, a_imp):
        """Supplement S7, PDF page 6."""
        # S7: C_imp = 0.09 exp(2.4 A_imp)
        expected = 0.09 * math.exp(2.4 * a_imp)

        result = SurfaceRunoff.get_runoff_coef_impervious_area(pcr.scalar(a_imp))

        # Float32 fields: rel=1e-5 covers the rounding of exp and the product.
        assert _cell(result) == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    def test_cimp_of_fully_pervious_cell_is_the_intercept(self):
        """Supplement S7, PDF page 6: A_imp = 0 gives exactly 0.09."""
        # S7 with A_imp = 0: C_imp = 0.09 exp(0) = 0.09
        expected = 0.09

        result = SurfaceRunoff.get_runoff_coef_impervious_area(pcr.scalar(0.0))

        # Float32 fields: 0.09 is not exactly representable in Float32.
        assert _cell(result) == pytest.approx(expected, rel=1e-5)


class TestImperviousSurfaceFraction:
    """Supplement S8, PDF page 6: A_imp = α_0 + α_I."""

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(("alpha_w", "alpha_i"), [(0.0, 0.5), (0.25, 0.35), (1.0, 0.0)])
    def test_aimp_is_the_sum_of_water_and_impervious_fractions(self, alpha_w, alpha_i):
        """Supplement S8, PDF page 6 (α_0 is the open water fraction α_W of Table S1)."""
        # S8: A_imp = α_0 + α_I
        expected = alpha_w + alpha_i

        result = SurfaceRunoff.get_impervious_surface_percent_per_grid_cell(
            pcr.scalar(alpha_w), pcr.scalar(alpha_i)
        )

        # Float32 fields: rel=1e-5 covers the rounding of the two operands.
        assert _cell(result) == pytest.approx(expected, rel=1e-5)


class TestWeightedPotRunoffCoef:
    """Supplement S6, PDF page 6: C_wp = (1 - A_imp) C_per + A_imp C_imp."""

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("a_imp", "c_per", "c_imp"),
        [
            (0.2, 0.31, 0.1455),
            (0.65, 0.48, 0.4288),
        ],
    )
    def test_cwp_matches_printed_formula(self, a_imp, c_per, c_imp):
        """Supplement S6, PDF page 6."""
        # S6: C_wp = (1 - A_imp) C_per + A_imp C_imp
        expected = (1.0 - a_imp) * c_per + a_imp * c_imp

        result = SurfaceRunoff.get_weighted_pot_runoff_coef(
            pcr.scalar(a_imp), pcr.scalar(c_per), pcr.scalar(c_imp)
        )

        # Float32 fields: rel=1e-5 covers the rounding of the two products.
        assert _cell(result) == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(("a_imp", "c_per", "c_imp"), [(0.0, 0.37, 0.9), (1.0, 0.37, 0.9)])
    def test_cwp_reduces_to_a_single_coefficient_at_the_extremes(self, a_imp, c_per, c_imp):
        """Supplement S6, PDF page 6: A_imp = 0 gives C_per, A_imp = 1 gives C_imp."""
        # S6 with A_imp in {0, 1}: C_wp = C_per when A_imp = 0, C_wp = C_imp when A_imp = 1
        expected = c_per if a_imp == 0.0 else c_imp

        result = SurfaceRunoff.get_weighted_pot_runoff_coef(
            pcr.scalar(a_imp), pcr.scalar(c_per), pcr.scalar(c_imp)
        )

        # Float32 fields: the inputs themselves are rounded to Float32.
        assert _cell(result) == pytest.approx(expected, rel=1e-5)


class TestActualRunoffCoef:
    """Supplement S5, PDF page 6: C_SR = C_wp P_MD / (C_wp P_MD - RCD C_wp + RCD)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("c_wp", "p_md", "rcd"),
        [
            (0.32, 12.5, 4.0),
            (0.71, 3.2, 8.5),
        ],
    )
    def test_csr_matches_printed_formula(self, c_wp, p_md, rcd):
        """Supplement S5, PDF page 6."""
        # S5: C_SR = C_wp P_MD / (C_wp P_MD - RCD C_wp + RCD)
        expected = (c_wp * p_md) / (c_wp * p_md - rcd * c_wp + rcd)

        result = SurfaceRunoff.get_actual_runoff_coef(pcr.scalar(c_wp), pcr.scalar(p_md), rcd)

        # Float32 fields: rel=1e-5 covers the rounding of the products and the division.
        assert _cell(result) == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(("c_wp", "p_md", "rcd"), [(0.32, 12.5, 4.0), (0.71, 3.2, 8.5)])
    def test_csr_denominator_is_the_mixing_form(self, c_wp, p_md, rcd):
        """Supplement S5, PDF page 6: the denominator equals C_wp P_MD + RCD (1 - C_wp).

        The rearrangement follows from the printed denominator by factoring RCD,
        so the two forms must agree to float64 rounding; the code is compared
        with the rearranged form here.
        """
        # S5 rearranged: C_SR = C_wp P_MD / (C_wp P_MD + RCD (1 - C_wp))
        expected = (c_wp * p_md) / (c_wp * p_md + rcd * (1.0 - c_wp))
        # Cross-check of the algebra itself, in float64 with the printed denominator.
        assert expected == pytest.approx(
            (c_wp * p_md) / (c_wp * p_md - rcd * c_wp + rcd), rel=1e-12
        )

        result = SurfaceRunoff.get_actual_runoff_coef(pcr.scalar(c_wp), pcr.scalar(p_md), rcd)

        # Float32 fields: rel=1e-5 covers the rounding of the products and the division.
        assert _cell(result) == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(("c_wp", "rcd"), [(0.3, 4.0), (0.85, 6.5)])
    def test_csr_equals_cwp_when_daily_rain_equals_rcd(self, c_wp, rcd):
        """Supplement S5, PDF page 6: with P_MD = RCD the denominator collapses to RCD.

        C_wp RCD / (C_wp RCD - RCD C_wp + RCD) = C_wp RCD / RCD = C_wp, so the
        actual coefficient equals the potential one (it does not become 1).
        """
        # S5 with P_MD = RCD: C_SR = C_wp
        expected = c_wp

        result = SurfaceRunoff.get_actual_runoff_coef(pcr.scalar(c_wp), pcr.scalar(rcd), rcd)

        # Float32 fields: rel=1e-5 covers the rounding of the products and the division.
        assert _cell(result) == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(("p_md", "rcd"), [(7.5, 3.0), (2.0, 9.0)])
    def test_csr_is_one_when_cwp_is_one(self, p_md, rcd):
        """Supplement S5, PDF page 6: with C_wp = 1 the RCD terms cancel.

        P_MD / (P_MD - RCD + RCD) = 1 for any P_MD > 0.
        """
        # S5 with C_wp = 1: C_SR = P_MD / P_MD = 1
        expected = 1.0

        result = SurfaceRunoff.get_actual_runoff_coef(pcr.scalar(1.0), pcr.scalar(p_md), rcd)

        # Float32 fields: rel=1e-5 covers the rounding of the products and the division.
        assert _cell(result) == pytest.approx(expected, rel=1e-5)


class TestCoefSoilMoistureConditions:
    """Supplement S10 and S11, PDF page 7: C_h = (θ_TUR / θ_POR)^b with θ = TU / (dg Zr 10)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("tu_r_mm", "tu_sat_mm", "dg", "zr", "b"),
        [
            (95.0, 260.0, 1.3, 40.0, 0.5),
            (410.0, 525.0, 1.5, 100.0, 0.8),
        ],
    )
    def test_ch_matches_printed_formula_in_mm(self, tu_r_mm, tu_sat_mm, dg, zr, b):
        """Supplement S10 and S11, PDF page 7.

        S11 converts the root zone moisture TU_R (mm) to the volumetric content
        θ_TUR = TU_R / (dg Zr 10); the porosity θ_POR is the same conversion of
        the saturation content TU_sat, which the model keeps in mm (TU_sat =
        θ_POR dg Zr 10). Both conversions share the factor dg Zr 10, so
        C_h = (TU_R / TU_sat)^b with both quantities in mm. After #321 the code
        follows that ratio and no longer reads its dg and Zr arguments; they
        are still passed here with realistic values to document the signature.
        """
        # S11: θ_TUR = TU_R / (dg Zr 10); θ_POR = TU_sat / (dg Zr 10)
        theta_tur = tu_r_mm / (dg * zr * 10.0)
        theta_por = tu_sat_mm / (dg * zr * 10.0)
        # S10: C_h = (θ_TUR / θ_POR)^b
        expected = (theta_tur / theta_por) ** b

        result = SurfaceRunoff.get_coef_soil_moist_conditions(
            pcr.scalar(tu_r_mm), pcr.scalar(dg), pcr.scalar(zr), pcr.scalar(tu_sat_mm), b
        )

        # Float32 fields: rel=1e-5 covers the rounding of the ratio and the power.
        assert _cell(result) == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(("dg", "zr"), [(0.9, 25.0), (1.7, 150.0)])
    def test_ch_does_not_depend_on_dg_and_zr(self, dg, zr):
        """Supplement S10 and S11, PDF page 7: the S11 factor dg Zr 10 cancels in the S10 ratio.

        The same TU_R and TU_sat in mm must give the same C_h whatever dg and Zr
        are, which is the property that makes the mm/mm ratio equal to the
        printed volumetric ratio (#321).
        """
        tu_r_mm, tu_sat_mm, b = 180.0, 300.0, 0.6
        # S10/S11: C_h = ((TU_R / (dg Zr 10)) / (TU_sat / (dg Zr 10)))^b = (TU_R / TU_sat)^b
        expected = (tu_r_mm / tu_sat_mm) ** b

        result = SurfaceRunoff.get_coef_soil_moist_conditions(
            pcr.scalar(tu_r_mm), pcr.scalar(dg), pcr.scalar(zr), pcr.scalar(tu_sat_mm), b
        )

        # Float32 fields: rel=1e-5 covers the rounding of the ratio and the power.
        assert _cell(result) == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize("b", [0.3, 1.0])
    def test_ch_is_one_at_saturation(self, b):
        """Supplement S10, PDF page 7: θ_TUR = θ_POR gives C_h = 1 for any b."""
        tu_sat_mm = 275.0
        # S10 with θ_TUR = θ_POR: C_h = 1^b = 1
        expected = 1.0

        result = SurfaceRunoff.get_coef_soil_moist_conditions(
            pcr.scalar(tu_sat_mm), pcr.scalar(1.2), pcr.scalar(50.0), pcr.scalar(tu_sat_mm), b
        )

        # Float32 fields: rel=1e-5 covers the rounding of the ratio and the power.
        assert _cell(result) == pytest.approx(expected, rel=1e-5)


class TestSurfaceRunoff:
    """Supplement S4 and S13, PDF pages 6 and 7, plus the confirmed rules of issue #331."""

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @staticmethod
    def _runoff(c_sr, c_h, p, i, alpha_w, et_rw, tu_r, tu_sat) -> float:
        field = SurfaceRunoff.get_surface_runoff(
            pcr.scalar(c_sr),
            pcr.scalar(c_h),
            pcr.scalar(p),
            pcr.scalar(i),
            pcr.scalar(alpha_w),
            pcr.scalar(et_rw),
            pcr.scalar(tu_r),
            pcr.scalar(tu_sat),
        )
        return _cell(field)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("c_sr", "c_h", "p", "i", "alpha_w", "et_rw", "tu_r", "tu_sat"),
        [
            (0.42, 0.55, 150.0, 12.0, 0.0, 35.0, 120.0, 260.0),
            (0.18, 0.93, 62.5, 4.5, 0.3, 80.0, 500.0, 525.0),
        ],
    )
    def test_sr_on_pervious_unsaturated_cell(self, c_sr, c_h, p, i, alpha_w, et_rw, tu_r, tu_sat):
        """Supplement S4, PDF page 6: SR = C_SR C_h (P_m - I) when α_W < 1 and TU_R < TU_sat.

        A nonzero open water evapotranspiration is passed to show that it does
        not enter the pervious branch.
        """
        # S4: SR = C_SR C_h (P_m - I)
        expected = c_sr * c_h * (p - i)

        result = self._runoff(c_sr, c_h, p, i, alpha_w, et_rw, tu_r, tu_sat)

        # Float32 fields: rel=1e-5 covers the rounding of the two products and the subtraction.
        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("c_sr", "c_h", "p", "i", "alpha_w", "et_rw", "tu_sat"),
        [
            (0.42, 0.55, 150.0, 12.0, 0.0, 35.0, 260.0),
            (0.18, 0.93, 62.5, 4.5, 0.3, 80.0, 525.0),
        ],
    )
    def test_sr_is_effective_rainfall_when_root_zone_is_saturated(
        self, c_sr, c_h, p, i, alpha_w, et_rw, tu_sat
    ):
        """Supplement S4 and S12, PDF pages 6 and 7, with the confirmed saturation rule.

        When TU_R equals TU_sat exactly the model turns all effective rainfall
        into surface runoff, SR = P_m - I, bypassing C_SR and C_h (documented
        in https://github.com/LabSid-USP/RUBEM/issues/331). The same Python
        float is passed as TU_R and TU_sat so the Float32 equality is exact.
        """
        # Confirmed rule (issue #331): SR = P_m - I when TU_R = TU_sat
        expected = p - i
        # The regular S4 value is different, so a pass proves the rule is applied.
        assert expected != pytest.approx(c_sr * c_h * (p - i), rel=1e-5)

        result = self._runoff(c_sr, c_h, p, i, alpha_w, et_rw, tu_sat, tu_sat)

        # Float32 fields: rel=1e-5 covers the rounding of the subtraction.
        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("c_sr", "c_h", "p", "i", "et_rw", "tu_sat"),
        [
            (0.42, 0.55, 120.0, 9.0, 40.0, 260.0),
            (0.18, 0.93, 210.0, 15.0, 95.5, 525.0),
        ],
    )
    def test_sr_on_open_water_cell_is_rainfall_minus_evaporation(
        self, c_sr, c_h, p, i, et_rw, tu_sat
    ):
        """Supplement S13, PDF page 7: if α_A = 1 then SR = P_m - ET_R,A.

        The printed symbols α_A and ET_R,A are read as the open water fraction
        α_W and the open water evapotranspiration ET_R,W (Supplement S28), as
        the code and https://github.com/LabSid-USP/RUBEM/issues/331 do. The
        cell keeps TU_R = TU_sat (confirmed rule 2) and nonzero C_SR, C_h and
        I are passed to show that none of them enters the water branch.
        """
        # S13: SR = P_m - ET_R,W (positive here, so the floor does not act)
        expected = p - et_rw
        assert expected > 0.0

        result = self._runoff(c_sr, c_h, p, i, 1.0, et_rw, tu_sat, tu_sat)

        # Float32 fields: rel=1e-5 covers the rounding of the subtraction.
        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("c_sr", "c_h", "p", "i", "et_rw", "tu_sat"),
        [
            (0.42, 0.55, 30.0, 2.0, 45.0, 260.0),
            (0.18, 0.93, 0.0, 0.0, 88.0, 525.0),
        ],
    )
    def test_sr_on_open_water_cell_is_floored_at_zero(self, c_sr, c_h, p, i, et_rw, tu_sat):
        """Supplement S13, PDF page 7, with the confirmed floor of issue #331.

        When evaporation exceeds rainfall on an open water cell the model
        returns SR = max(P_m - ET_R,W, 0) = 0 instead of a negative runoff
        (https://github.com/LabSid-USP/RUBEM/issues/331, rule 4).
        """
        # Confirmed rule (issue #331): SR = max(P_m - ET_R,W, 0)
        expected = max(p - et_rw, 0.0)
        assert p - et_rw < 0.0

        result = self._runoff(c_sr, c_h, p, i, 1.0, et_rw, tu_sat, tu_sat)

        # Exact: the floored value is zero, which Float32 represents exactly.
        assert result == expected

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(("p", "tu_sat"), [(120.0, 260.0), (88.0, 525.0)])
    def test_sr_on_open_water_cell_is_zero_when_rain_equals_evaporation(self, p, tu_sat):
        """Supplement S13, PDF page 7, at the boundary of the floor of issue #331.

        With ET_R,W = P_m the printed difference is exactly zero and the floor
        of rule 4, SR = max(P_m - ET_R,W, 0), returns the same zero
        (https://github.com/LabSid-USP/RUBEM/issues/331). The same Python float
        is passed as P_m and ET_R,W so the Float32 difference is exactly zero.
        """
        # S13 with ET_R,W = P_m: SR = P_m - ET_R,W = 0, and the floor keeps max(0, 0) = 0
        expected = 0.0

        result = self._runoff(0.42, 0.55, p, 9.0, 1.0, p, tu_sat, tu_sat)

        # Exact: zero is represented exactly in Float32.
        assert result == expected
