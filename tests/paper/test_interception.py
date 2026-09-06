"""Conformity of the interception module with the published formulation.

Every expectation below is evaluated in float64 from the equation printed in the
journal supplement (equations S14 to S20, PDF page 8). PCRaster scalar fields are
Float32, so results are compared with ``pytest.approx(rel=1e-5)`` for one-step
formulas; a looser tolerance is used only where the Float32 evaluation is known
to lose digits, and the measured error that justifies it is stated in the test.
"""

import math

import pcraster as pcr
import pytest
from pcraster.framework import generalfunctions

from rubem.hydrological_processes import Interception

# Cap printed in S19 and the FPAR_max value stated in the supplement (PDF page 8).
FPAR_CAP = 0.95


def _cell(field) -> float:
    """Return the value of the single cell of a 1x1 field."""
    return generalfunctions.getCellValue(field, 0, 0)


@pytest.fixture(autouse=True)
def single_cell_clone():
    pcr.setclone(1, 1, 1, 1, 1)


class TestReflectancesSimpleRatioS20:
    """Supplement S20, PDF page 8: RS = (1 + NDVI) / (1 - NDVI)."""

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize("ndvi", [0.25, 0.62, -0.15])
    def test_simple_ratio(self, ndvi):
        """RS = (1 + NDVI) / (1 - NDVI) (Supplement S20, PDF page 8)."""
        # S20: RS = (1 + NDVI) / (1 - NDVI)
        expected = (1.0 + ndvi) / (1.0 - ndvi)

        result = _cell(Interception.get_reflectances_simple_ratio(pcr.scalar(ndvi)))

        assert result == pytest.approx(expected, rel=1e-5)


class TestFparS19:
    """Supplement S19, PDF page 8.

    FPAR = min((RS - RS_min) (FPAR_max - FPAR_min) / (RS_max - RS_min) + FPAR_min, 0.95).
    """

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("rs", "rs_min", "rs_max", "fpar_min"),
        [
            (3.0, 1.5, 6.0, 0.001),
            (2.2, 1.2, 4.8, 0.05),
        ],
    )
    def test_interpolation_below_cap(self, rs, rs_min, rs_max, fpar_min):
        """The linear interpolation applies while it stays below 0.95 (S19, PDF page 8)."""
        # S19: FPAR = (RS - RS_min) (FPAR_max - FPAR_min) / (RS_max - RS_min) + FPAR_min
        expected = (rs - rs_min) * (FPAR_CAP - fpar_min) / (rs_max - rs_min) + fpar_min
        assert expected < FPAR_CAP, "the parameter set must exercise the interpolation branch"

        result = _cell(
            Interception.get_fpar(
                fpar_min, FPAR_CAP, pcr.scalar(rs), pcr.scalar(rs_min), pcr.scalar(rs_max)
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("rs", "rs_min", "rs_max", "fpar_min"),
        [
            (9.0, 1.5, 6.0, 0.001),
            (5.0, 1.2, 4.8, 0.05),
        ],
    )
    def test_cap_at_0_95(self, rs, rs_min, rs_max, fpar_min):
        """Above RS_max the interpolation exceeds 0.95 and S19 caps FPAR at 0.95 (PDF page 8)."""
        # S19 interpolation term, exceeding the cap for these inputs
        uncapped = (rs - rs_min) * (FPAR_CAP - fpar_min) / (rs_max - rs_min) + fpar_min
        assert uncapped > FPAR_CAP, "the parameter set must exercise the cap"
        # S19: FPAR = min(uncapped, 0.95)
        expected = min(uncapped, FPAR_CAP)

        result = _cell(
            Interception.get_fpar(
                fpar_min, FPAR_CAP, pcr.scalar(rs), pcr.scalar(rs_min), pcr.scalar(rs_max)
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    def test_lower_end_returns_fpar_min(self):
        """At RS = RS_min the interpolation of S19 reduces to FPAR_min (PDF page 8)."""
        rs_min, rs_max, fpar_min = 1.5, 6.0, 0.001
        # S19 with RS = RS_min: FPAR = 0 * (...) + FPAR_min
        expected = fpar_min

        result = _cell(
            Interception.get_fpar(
                fpar_min, FPAR_CAP, pcr.scalar(rs_min), pcr.scalar(rs_min), pcr.scalar(rs_max)
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    def test_cap_is_the_fpar_max_argument(self):
        """The cap of S19 is FPAR_max, stated as 0.95 in the supplement (PDF page 8).

        S19 prints the literal 0.95 inside the min and the where-list gives 0.95
        as the value of FPAR_max, so for the published parameter set the two
        coincide; the model caps the interpolation at the FPAR_max it receives.
        This case uses FPAR_max = 0.90 to show which of the two the cap follows.
        """
        rs, rs_min, rs_max, fpar_min, fpar_max = 9.0, 1.5, 6.0, 0.001, 0.90
        # S19 interpolation term with FPAR_max = 0.90, above the cap
        uncapped = (rs - rs_min) * (fpar_max - fpar_min) / (rs_max - rs_min) + fpar_min
        assert uncapped > FPAR_CAP > fpar_max, "the case must separate 0.95 from FPAR_max"
        # S19: FPAR = min(uncapped, FPAR_max)
        expected = min(uncapped, fpar_max)

        result = _cell(
            Interception.get_fpar(
                fpar_min, fpar_max, pcr.scalar(rs), pcr.scalar(rs_min), pcr.scalar(rs_max)
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)


class TestLeafAreaIndexS18:
    """Supplement S18, PDF page 8: LAI = LAI_max log(1 - FPAR) / log(1 - FPAR_max)."""

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("fpar", "fpar_max", "lai_max"),
        [
            (0.40, 0.95, 12.0),
            (0.72, 0.95, 8.0),
            (0.10, 0.90, 6.0),
        ],
    )
    def test_leaf_area_index(self, fpar, fpar_max, lai_max):
        """LAI = LAI_max log(1 - FPAR) / log(1 - FPAR_max) (Supplement S18, PDF page 8).

        The quotient of two logarithms does not depend on the base, so the
        expectation uses the natural logarithm.
        """
        # S18: LAI = LAI_max * log(1 - FPAR) / log(1 - FPAR_max)
        expected = lai_max * math.log(1.0 - fpar) / math.log(1.0 - fpar_max)

        result = _cell(Interception.get_leaf_area_index(pcr.scalar(fpar), fpar_max, lai_max))

        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    def test_fpar_max_gives_lai_max(self):
        """At FPAR = FPAR_max the quotient of S18 is 1 and LAI = LAI_max (PDF page 8)."""
        fpar_max, lai_max = 0.95, 12.0
        # S18 with FPAR = FPAR_max: LAI = LAI_max * 1
        expected = lai_max

        result = _cell(Interception.get_leaf_area_index(pcr.scalar(fpar_max), fpar_max, lai_max))

        assert result == pytest.approx(expected, rel=1e-5)


def _supplement_interception(alfa, lai, p_m, d_p, a_v):
    """Evaluate S14 to S17 (PDF page 8) in float64 and return (I_D, I_R, I_V, I)."""
    # S17: I_D = alpha LAI (1 - 1 / (1 + P_m [1 - exp(-0.463 LAI)] / (alpha LAI)))
    i_d = alfa * lai * (1.0 - 1.0 / (1.0 + p_m * (1.0 - math.exp(-0.463 * lai)) / (alfa * lai)))
    # S16: I_R = 1 - exp(-I_D d_p / P_m)
    i_r = 1.0 - math.exp(-i_d * d_p / p_m)
    # S15: I_V = P_m I_R
    i_v = p_m * i_r
    # S14: I = alpha_V I_V
    i_total = a_v * i_v
    return i_d, i_r, i_v, i_total


class TestInterceptionS14ToS17:
    """Supplement S14 to S17, PDF page 8: canopy interception of the vegetated fraction."""

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("alfa", "lai", "p_m", "d_p", "a_v"),
        [
            (0.5, 3.0, 120.0, 12.0, 0.8),
            (2.0, 5.5, 45.0, 6.0, 1.0),
            (0.2, 1.2, 250.0, 20.0, 0.3),
        ],
    )
    def test_interception_positive_precipitation(self, alfa, lai, p_m, d_p, a_v):
        """I = alpha_V P_m (1 - exp(-I_D d_p / P_m)) with I_D from S17 (S14 to S17, PDF page 8)."""
        _, i_r, _, expected = _supplement_interception(alfa, lai, p_m, d_p, a_v)
        assert 0.0 < i_r < 1.0, "the parameter set must give a proper interception rate"

        result = _cell(
            Interception.get_interception(
                alfa, pcr.scalar(lai), pcr.scalar(p_m), pcr.scalar(d_p), pcr.scalar(a_v)
            )
        )

        assert result == pytest.approx(expected, rel=1e-5)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("alfa", "lai", "d_p", "a_v"),
        [
            (0.5, 3.0, 12.0, 0.8),
            (2.0, 5.5, 6.0, 1.0),
        ],
    )
    def test_zero_precipitation_gives_zero(self, alfa, lai, d_p, a_v):
        """With P_m = 0 there is nothing to intercept: I_V = P_m I_R = 0 (S15, PDF page 8).

        S16 divides by P_m; the model must return 0 instead of raising a
        division error or producing a missing value. The product with P_m = 0
        is exact in Float32, so no tolerance is needed.
        """
        # S15 with P_m = 0: I_V = 0 * I_R = 0, hence S14: I = alpha_V * 0 = 0
        expected = 0.0

        result = _cell(
            Interception.get_interception(
                alfa, pcr.scalar(lai), pcr.scalar(0.0), pcr.scalar(d_p), pcr.scalar(a_v)
            )
        )

        assert result == expected

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("alfa", "lai", "p_m", "d_p", "a_v", "rel_tol"),
        [
            (0.5, 0.5, 1e-4, 2.0, 0.8, 1e-3),
            (1.0, 0.8, 1e-3, 2.0, 1.0, 1e-4),
            (0.5, 0.5, 1e-3, 2.0, 0.8, 1e-4),
        ],
    )
    def test_small_positive_precipitation_divides_by_itself(
        self, alfa, lai, p_m, d_p, a_v, rel_tol
    ):
        """A small positive P_m is used as is in the S16 denominator (PDF page 8).

        S16 divides by P_m; the model replaces the denominator only when
        P_m = 0, so for P_m of 1e-4 or 1e-3 mm the rate is
        1 - exp(-I_D d_p / P_m) with the true P_m (correction of
        https://github.com/LabSid-USP/RUBEM/pull/323). Two denominators that
        would violate S16 are evaluated as well and must be separated from the
        result: P_m + 1e-5 (the additive guard used before the correction) and
        the constant 1e-5.

        Tolerance: for these small P_m the S17 factor 1 - 1/(1 + P_m k / (alpha
        LAI)) is a difference of two Float32 numbers close to 1 and loses
        significant digits; the measured relative error is 4.3e-4 for
        P_m = 1e-4 and below 6e-6 for P_m = 1e-3, hence rel=1e-3 and rel=1e-4
        respectively instead of the usual 1e-5. Both alternative denominators
        differ from the expectation by at least 0.7%, that is by more than
        seven times the tolerance in use.
        """
        _, i_r, _, expected = _supplement_interception(alfa, lai, p_m, d_p, a_v)
        assert 0.0 < i_r < 1.0, "the parameter set must give a proper interception rate"
        # S16 evaluated with the denominators that the model must not use
        i_d = alfa * lai * (1.0 - 1.0 / (1.0 + p_m * (1.0 - math.exp(-0.463 * lai)) / (alfa * lai)))
        additive_guard_total = a_v * p_m * (1.0 - math.exp(-i_d * d_p / (p_m + 1e-5)))
        constant_guard_total = a_v * p_m * (1.0 - math.exp(-i_d * d_p / 1e-5))
        for wrong in (additive_guard_total, constant_guard_total):
            assert abs(expected - wrong) > 7.0 * rel_tol * expected, (
                "the parameter set must separate the S16 denominator from the guard values"
            )

        result = _cell(
            Interception.get_interception(
                alfa, pcr.scalar(lai), pcr.scalar(p_m), pcr.scalar(d_p), pcr.scalar(a_v)
            )
        )

        assert result == pytest.approx(expected, rel=rel_tol)
        assert result != pytest.approx(additive_guard_total, rel=rel_tol)
        assert result != pytest.approx(constant_guard_total, rel=rel_tol)
