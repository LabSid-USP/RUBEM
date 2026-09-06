"""Conformity of the ``Soil`` class with the published model formulation.

Every expectation is computed in float64 from the formula printed in the
journal supplement (equations S1 to S3, S12 and S31 to S33). PCRaster scalar
fields are stored as Float32, so results are compared with an explicit
relative tolerance of 1e-5 (about seven significant digits, the precision of
a Float32 value after a one-step formula).

Rules that are not printed in the supplement but are confirmed model
behavior are cited by their issue: https://github.com/LabSid-USP/RUBEM/issues/331.
"""

import math

import pcraster as pcr
import pytest
from pcraster.framework import generalfunctions

from rubem.hydrological_processes import Soil

# Float32 field versus float64 expectation, one-step formulas.
FLOAT32_REL = 1e-5


def cell(field) -> float:
    return generalfunctions.getCellValue(field, 0, 0)


class TestLateralFlowS31:
    """Supplement S31, PDF page 11: LF = f * K_R * (TU_R / TU_SAT)^2."""

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("f", "kr", "tur", "tusat"),
        [
            (0.3, 120.0, 45.0, 180.0),
            (0.65, 75.5, 210.0, 260.0),
        ],
    )
    def test_lateral_flow_matches_s31(self, f, kr, tur, tusat):
        """Supplement S31, PDF page 11.

        LF = f * K_R * (TU_R / TU_SAT)^2, with TU_R and TU_SAT in mm and K_R
        in mm/month.
        """
        # LF = f * K_R * (TU_R / TU_SAT)^2
        expected = f * kr * (tur / tusat) ** 2

        field = Soil.get_lateral_flow(f, pcr.scalar(kr), pcr.scalar(tur), pcr.scalar(tusat))

        assert cell(field) == pytest.approx(expected, rel=FLOAT32_REL)

    @pytest.mark.paper
    @pytest.mark.unit
    def test_lateral_flow_is_quadratic_in_the_moisture_ratio(self):
        """Supplement S31, PDF page 11: halving TU_R divides LF by four."""
        f, kr, tusat = 0.4, 100.0, 200.0

        # LF(TU_R) / LF(TU_R / 2) = (TU_R / (TU_R / 2))^2 = 4
        full = cell(Soil.get_lateral_flow(f, pcr.scalar(kr), pcr.scalar(120.0), pcr.scalar(tusat)))
        half = cell(Soil.get_lateral_flow(f, pcr.scalar(kr), pcr.scalar(60.0), pcr.scalar(tusat)))

        assert full == pytest.approx(0.4 * 100.0 * (120.0 / 200.0) ** 2, rel=FLOAT32_REL)
        assert full / half == pytest.approx(4.0, rel=FLOAT32_REL)


class TestRechargeS32:
    """Supplement S32, PDF page 11: REC = (1 - f) * K_R * (TU_R / TU_SAT)^2."""

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("f", "kr", "tur", "tusat"),
        [
            (0.3, 120.0, 45.0, 180.0),
            (0.65, 75.5, 210.0, 260.0),
        ],
    )
    def test_recharge_matches_s32(self, f, kr, tur, tusat):
        """Supplement S32, PDF page 11.

        REC = (1 - f) * K_R * (TU_R / TU_SAT)^2, with TU_R and TU_SAT in mm
        and K_R in mm/month.
        """
        # REC = (1 - f) * K_R * (TU_R / TU_SAT)^2
        expected = (1.0 - f) * kr * (tur / tusat) ** 2

        field = Soil.get_recharge(f, pcr.scalar(kr), pcr.scalar(tur), pcr.scalar(tusat))

        assert cell(field) == pytest.approx(expected, rel=FLOAT32_REL)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("f", "kr", "tur", "tusat"),
        [
            (0.3, 120.0, 45.0, 180.0),
            (0.65, 75.5, 210.0, 260.0),
        ],
    )
    def test_lateral_flow_and_recharge_partition_the_percolation(self, f, kr, tur, tusat):
        """Supplement S31 and S32, PDF page 11.

        f partitions K_R * (TU_R / TU_SAT)^2 between the horizontal (LF) and
        vertical (REC) flows, so LF + REC = K_R * (TU_R / TU_SAT)^2 whatever f.
        """
        # LF + REC = (f + 1 - f) * K_R * (TU_R / TU_SAT)^2
        expected_total = kr * (tur / tusat) ** 2

        lateral_flow = cell(
            Soil.get_lateral_flow(f, pcr.scalar(kr), pcr.scalar(tur), pcr.scalar(tusat))
        )
        recharge = cell(Soil.get_recharge(f, pcr.scalar(kr), pcr.scalar(tur), pcr.scalar(tusat)))

        assert lateral_flow + recharge == pytest.approx(expected_total, rel=FLOAT32_REL)
        assert lateral_flow == pytest.approx(f * expected_total, rel=FLOAT32_REL)


class TestBaseflowS33:
    """Supplement S33, PDF page 11.

    BF = 0                                                 if TU_S <= BF_thresh
    BF = BF_(t-1) * e^(-alpha_gw) + (1 - e^(-alpha_gw)) * REC  if TU_S > BF_thresh

    The corrected code (#325) additionally limits the recession value to the
    water available in the saturated zone, BF = min(recession, TU_S(t-1) + REC).
    That limit is not printed in the supplement.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @staticmethod
    def baseflow(previous_bf, alpha_gw, rec, tus, thresh) -> float:
        field = Soil.get_baseflow(
            pcr.scalar(previous_bf),
            alpha_gw,
            pcr.scalar(rec),
            pcr.scalar(tus),
            pcr.scalar(thresh),
        )
        return cell(field)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("previous_bf", "alpha_gw", "rec", "tus", "thresh"),
        [
            (12.0, 0.25, 8.0, 150.0, 90.0),
            (3.5, 0.8, 22.0, 410.0, 409.5),
        ],
    )
    def test_recession_branch_matches_s33(self, previous_bf, alpha_gw, rec, tus, thresh):
        """Supplement S33, PDF page 11, branch TU_S > BF_thresh.

        BF = BF_(t-1) * e^(-alpha_gw) + (1 - e^(-alpha_gw)) * REC. The stored
        water TU_S(t-1) + REC is far above the recession value, so the #325
        limit does not bind.
        """
        # BF = BF_(t-1) * e^(-alpha_gw) + (1 - e^(-alpha_gw)) * REC
        decay = math.exp(-alpha_gw)
        expected = previous_bf * decay + (1.0 - decay) * rec
        assert expected < tus + rec

        assert self.baseflow(previous_bf, alpha_gw, rec, tus, thresh) == pytest.approx(
            expected, rel=FLOAT32_REL
        )

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("previous_bf", "alpha_gw", "rec", "tus", "thresh"),
        [
            (12.0, 0.25, 40.0, 60.0, 90.0),
            (3.5, 0.8, 22.0, 409.5, 409.5),
            (6.0, 0.4, 50.0, 80.0, 100.0),
        ],
    )
    def test_zero_branch_matches_s33(self, previous_bf, alpha_gw, rec, tus, thresh):
        """Supplement S33, PDF page 11, branch TU_S <= BF_thresh: BF = 0.

        The second case has TU_S exactly equal to the threshold, which the
        printed condition (<=) assigns to the zero branch. Every case has
        TU_S + REC above the threshold, so they discriminate the printed test
        (on TU_S alone) from a test on the storage after recharge, which would
        select the recession branch and return a non-zero baseflow.
        """
        # BF = 0 if TU_S <= BF_thresh
        expected = 0.0
        assert tus <= thresh
        # the printed condition is on TU_S, not on TU_S + REC
        assert tus + rec > thresh

        assert self.baseflow(previous_bf, alpha_gw, rec, tus, thresh) == pytest.approx(expected)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("previous_bf", "alpha_gw", "rec", "tus", "thresh"),
        [
            (100.0, 0.1, 1.0, 5.0, 4.0),
            (40.0, 0.5, 2.5, 10.0, 9.0),
        ],
    )
    def test_baseflow_is_limited_to_the_available_water(
        self, previous_bf, alpha_gw, rec, tus, thresh
    ):
        """Correction #325 on top of Supplement S33, PDF page 11.

        BF = min(BF_(t-1) * e^(-alpha_gw) + (1 - e^(-alpha_gw)) * REC,
                 TU_S(t-1) + REC)
        so that the S3 balance of the saturated zone cannot become negative.
        The cases are chosen so that the recession value exceeds the water
        available and the limit binds.
        """
        # recession = BF_(t-1) * e^(-alpha_gw) + (1 - e^(-alpha_gw)) * REC
        decay = math.exp(-alpha_gw)
        recession = previous_bf * decay + (1.0 - decay) * rec
        # limit = TU_S(t-1) + REC
        expected = tus + rec
        assert tus > thresh
        assert recession > expected

        assert self.baseflow(previous_bf, alpha_gw, rec, tus, thresh) == pytest.approx(
            expected, rel=FLOAT32_REL
        )


class TestSaturatedZoneBalanceS3:
    """Supplement S3, PDF page 5: TU_S = TU_(S,t-1) - BF + REC."""

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("previous_tus", "rec", "bf"),
        [
            (150.0, 18.5, 9.25),
            (72.0, 4.0, 11.0),
        ],
    )
    def test_saturated_zone_balance_matches_s3(self, previous_tus, rec, bf):
        """Supplement S3, PDF page 5: TU_S = TU_(S,t-1) - BF + REC.

        The second case drains more than it recharges (BF > REC), so the
        storage decreases.
        """
        # TU_S = TU_(S,t-1) - BF + REC
        expected = previous_tus - bf + rec

        field = Soil.get_actual_water_cont_sat_zone(
            pcr.scalar(previous_tus), pcr.scalar(rec), pcr.scalar(bf)
        )

        assert cell(field) == pytest.approx(expected, rel=FLOAT32_REL)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("previous_bf", "alpha_gw", "rec", "tus", "thresh"),
        [
            (100.0, 0.1, 1.0, 5.0, 4.0),
            (40.0, 0.5, 2.5, 10.0, 9.0),
        ],
    )
    def test_binding_baseflow_limit_empties_the_saturated_zone(
        self, previous_bf, alpha_gw, rec, tus, thresh
    ):
        """Supplement S3, PDF page 5, with the correction #325 of S33, PDF page 11.

        The limit BF = min(recession, TU_S(t-1) + REC) exists so that the S3
        balance never becomes negative, a rule confirmed in
        https://github.com/LabSid-USP/RUBEM/issues/331. When the limit binds,
        S3 gives TU_S = TU_S(t-1) - (TU_S(t-1) + REC) + REC = 0 exactly.
        """
        # recession = BF_(t-1) * e^(-alpha_gw) + (1 - e^(-alpha_gw)) * REC
        decay = math.exp(-alpha_gw)
        recession = previous_bf * decay + (1.0 - decay) * rec
        assert tus > thresh
        # the #325 limit binds: BF = TU_S(t-1) + REC
        assert recession > tus + rec
        # TU_S = TU_(S,t-1) - BF + REC = TU_(S,t-1) - (TU_(S,t-1) + REC) + REC
        expected = 0.0

        baseflow = Soil.get_baseflow(
            pcr.scalar(previous_bf),
            alpha_gw,
            pcr.scalar(rec),
            pcr.scalar(tus),
            pcr.scalar(thresh),
        )
        field = Soil.get_actual_water_cont_sat_zone(pcr.scalar(tus), pcr.scalar(rec), baseflow)

        # TU_S(t-1) + REC is exact in Float32 for these inputs (6 and 12.5) and
        # the subtraction cancels it, so the emptied storage is exactly zero.
        assert cell(field) == expected


class TestRootZoneBalanceS1:
    """Supplement S1, S2 (PDF page 5) and S12 (PDF page 7).

    TU_R = TU_(R,t-1) + P_E - SR - LF - REC - ET_REAL, with P_E = P_m - I.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        pcr.setclone(1, 1, 1, 1, 1)

    @staticmethod
    def root_zone(previous_tur, p, i, sr, lf, rec, et, a_o, tusat) -> float:
        field = Soil.get_actual_soil_moist_cont(
            pcr.scalar(previous_tur),
            pcr.scalar(p),
            pcr.scalar(i),
            pcr.scalar(sr),
            pcr.scalar(lf),
            pcr.scalar(rec),
            pcr.scalar(et),
            pcr.scalar(a_o),
            pcr.scalar(tusat),
        )
        return cell(field)

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("previous_tur", "p", "i", "sr", "lf", "rec", "et", "a_o", "tusat"),
        [
            (120.0, 180.0, 22.5, 41.0, 6.5, 15.0, 88.0, 0.0, 300.0),
            (65.0, 95.0, 8.0, 12.5, 3.0, 7.0, 54.0, 0.3, 250.0),
        ],
    )
    def test_balance_inside_the_storage_range_matches_s1(
        self, previous_tur, p, i, sr, lf, rec, et, a_o, tusat
    ):
        """Supplement S1 and S2, PDF page 5.

        TU_R = TU_(R,t-1) + (P_m - I) - SR - LF - REC - ET_REAL when the
        result lies strictly inside (0, TU_SAT). The second case has a
        partial water fraction (a_o = 0.3 != 1), which must not alter the
        balance.
        """
        # P_E = P_m - I
        effective_precipitation = p - i
        # TU_R = TU_(R,t-1) + P_E - SR - LF - REC - ET_REAL
        expected = previous_tur + effective_precipitation - sr - lf - rec - et
        assert 0.0 < expected < tusat

        assert self.root_zone(previous_tur, p, i, sr, lf, rec, et, a_o, tusat) == pytest.approx(
            expected, rel=FLOAT32_REL
        )

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("previous_tur", "p", "i", "sr", "lf", "rec", "et", "a_o", "tusat"),
        [
            (250.0, 320.0, 30.0, 60.0, 10.0, 20.0, 70.0, 0.0, 300.0),
            (190.0, 210.0, 15.0, 25.0, 4.0, 9.0, 40.0, 0.5, 200.0),
        ],
    )
    def test_balance_above_saturation_is_clamped_to_tusat(
        self, previous_tur, p, i, sr, lf, rec, et, a_o, tusat
    ):
        """Supplement S12, PDF page 7: if theta_TUR > theta_POR then theta_TUR = theta_POR.

        S12 is printed in volumetric terms; theta_TUR = TU_R / (dg * Zr * 10)
        (S11) and theta_POR = TU_SAT / (dg * Zr * 10) share the divisor, so the
        clamp is TU_R = TU_SAT in mm.
        """
        # balance = TU_(R,t-1) + (P_m - I) - SR - LF - REC - ET_REAL
        balance = previous_tur + (p - i) - sr - lf - rec - et
        assert balance > tusat
        # theta_TUR > theta_POR -> theta_TUR = theta_POR, i.e. TU_R = TU_SAT
        expected = tusat

        assert self.root_zone(previous_tur, p, i, sr, lf, rec, et, a_o, tusat) == pytest.approx(
            expected, rel=FLOAT32_REL
        )

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("previous_tur", "p", "i", "sr", "lf", "rec", "et", "a_o", "tusat"),
        [
            (40.0, 20.0, 5.0, 3.0, 8.0, 12.0, 60.0, 0.0, 300.0),
            (10.0, 0.0, 0.0, 0.0, 2.0, 4.0, 30.0, 0.2, 150.0),
        ],
    )
    def test_negative_balance_is_floored_at_zero(
        self, previous_tur, p, i, sr, lf, rec, et, a_o, tusat
    ):
        """Confirmed rule, issue #331 on top of Supplement S1, PDF page 5.

        The supplement prints no lower bound for TU_R. The model floors a
        negative balance at 0 mm (the root zone cannot hold negative water),
        confirmed as intentional in https://github.com/LabSid-USP/RUBEM/issues/331.
        """
        # balance = TU_(R,t-1) + (P_m - I) - SR - LF - REC - ET_REAL
        balance = previous_tur + (p - i) - sr - lf - rec - et
        assert balance < 0.0
        # balance < 0 -> TU_R = 0
        expected = 0.0

        assert self.root_zone(previous_tur, p, i, sr, lf, rec, et, a_o, tusat) == pytest.approx(
            expected
        )

    @pytest.mark.paper
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("previous_tur", "p", "i", "sr", "lf", "rec", "et", "tusat"),
        [
            (120.0, 180.0, 22.5, 41.0, 6.5, 15.0, 88.0, 300.0),
            (5.0, 10.0, 0.0, 9.0, 1.0, 2.0, 30.0, 175.0),
        ],
    )
    def test_open_water_cell_is_kept_saturated(self, previous_tur, p, i, sr, lf, rec, et, tusat):
        """Confirmed rule, issue #331, and Supplement page 5 text.

        The supplement states that a cell fully covered by the water fraction
        is considered saturated ("if alpha_W = 1 then TU_R = TU_S", PDF page
        5). The model implements it as TU_R = TU_SAT regardless of the S1
        balance, confirmed in https://github.com/LabSid-USP/RUBEM/issues/331.
        The first case has a balance inside (0, TU_SAT) and the second a
        negative one; both must yield TU_SAT.
        """
        # alpha_W = 1 -> TU_R = TU_SAT
        expected = tusat

        assert self.root_zone(previous_tur, p, i, sr, lf, rec, et, 1.0, tusat) == pytest.approx(
            expected, rel=FLOAT32_REL
        )
