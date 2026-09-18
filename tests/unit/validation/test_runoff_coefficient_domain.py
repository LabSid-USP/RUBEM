"""Domain of the weighted runoff coefficient C_wp read from the lookup tables.

Supplement S5-S9, PDF page 6:

    C_SR = C_wp P_MD / (C_wp P_MD - RCD C_wp + RCD)                     (S5)
    C_wp = (1 - A_imp) C_per + A_imp C_imp                              (S6)
    C_imp = 0.09 exp(2.4 A_imp)                                         (S7)
    A_imp = a_o + a_i                                                   (S8)
    C_per = w1 (0.02 / n) + w2 (theta_PM / (1 - theta_PM)) + w3 (S / (10 + S))  (S9)

The slope term of S9 lies in [0, 1), so the slope-free part of C_wp is

    B = (1 - A) (w1 0.02 / n + w2 T_w / (1 - T_w)) + A 0.09 exp(2.4 A)

and C_wp lies in [B, B + (1 - A) w3).
"""

import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from rubem.configuration.input_table_files import InputTableFiles
from rubem.validation.lookup_tables import check_runoff_coefficient_domain
from tests.helpers.synthetic import write_synthetic_dataset


def write_table(path: Path, values: dict[int, float]) -> Path:
    path.write_text("".join(f"{key} {value}\n" for key, value in values.items()), encoding="utf8")
    return path


def tables(tmp_path, manning, a_i, a_o, t_wp):
    """A minimal stand-in for :class:`InputTableFiles` with the four tables of the check."""
    return SimpleNamespace(
        manning=write_table(tmp_path / "manning.txt", manning),
        a_i=write_table(tmp_path / "a_i.txt", a_i),
        a_o=write_table(tmp_path / "a_o.txt", a_o),
        t_wp=write_table(tmp_path / "Tw.txt", t_wp),
    )


def reported_numbers(reason: str) -> list[float]:
    """The decimal numbers a problem reason quotes, in order."""
    return [float(match) for match in re.findall(r"\d+\.\d+", reason)]


def assert_quotes(reason: str, value: float) -> None:
    """Assert the reason quotes ``value``.

    The reasons round to four decimals, so a quoted number may differ from the
    float64 value by up to 5e-5 in absolute value and by no more than that.
    """
    numbers = reported_numbers(reason)
    assert any(number == pytest.approx(value, abs=5e-5) for number in numbers), (
        f"{value} not among {numbers} in {reason!r}"
    )


def c_wp(area, roughness, t_w, slope, w1, w2, w3):
    """C_wp of S6-S9 (PDF page 6) evaluated in float64, independently of the check."""
    c_per = w1 * (0.02 / roughness) + w2 * (t_w / (1 - t_w)) + w3 * (slope / (10 + slope))
    return (1 - area) * c_per + area * 0.09 * math.exp(2.4 * area)


def synthetic_tables(config):
    t = config["TABLES"]
    return InputTableFiles(
        rainy_days=t["rainydays"],
        a_i=t["a_i"],
        a_o=t["a_o"],
        a_s=t["a_s"],
        a_v=t["a_v"],
        manning=t["manning"],
        bulk_density=t["bulk_density"],
        k_sat=t["k_sat"],
        t_fcap=t["t_fcap"],
        t_sat=t["t_sat"],
        t_wp=t["t_wp"],
        rootzone_depth=t["rootzone_depth"],
        kc_min=t["k_c_min"],
        kc_max=t["k_c_max"],
    )


class TestCheckRunoffCoefficientDomain:
    @pytest.mark.unit
    def test_the_synthetic_tables_stay_inside_the_domain(self, tmp_path):
        """Supplement S5-S9, PDF page 6: C_wp <= 1 for every pair of the synthetic dataset.

        Class 3 (A = 0, n = 0.16) and class 4 (A = 0.1, n = 0.05) with T_w = 0.12
        and w1 = w2 = w3 = 1/3 give bounds well below 1 (about 0.42 and 0.47).
        """
        # B + (1 - A) w3, the supremum of C_wp over the slope, for both classes.
        third = 1 / 3
        bound_3 = c_wp(0.0, 0.16, 0.12, 0.0, third, third, third) + 1.0 * third
        bound_4 = c_wp(0.1, 0.05, 0.12, 0.0, third, third, third) + 0.9 * third
        assert bound_3 == pytest.approx(0.4204545, abs=5e-7)
        assert bound_4 == pytest.approx(0.4723503, abs=5e-7)

        config = write_synthetic_dataset(str(tmp_path))

        problems = check_runoff_coefficient_domain(synthetic_tables(config), 1 / 3, 1 / 3, 1 / 3)

        assert problems == []

    @pytest.mark.unit
    def test_a_slope_free_part_above_one_blocks(self, tmp_path):
        """Supplement S9, PDF page 6: w1 0.02 / n with n = 0.005 and w1 = 1 gives B = 4."""
        # B = (1 - 0) (1 * 0.02 / 0.005 + 0 * 0.12 / (1 - 0.12) + 0 * 0 / 10) + 0 * C_imp = 4.0
        expected = c_wp(0.0, 0.005, 0.12, 0.0, 1.0, 0.0, 0.0)
        assert expected == 4.0

        problems = check_runoff_coefficient_domain(
            tables(tmp_path, {7: 0.005}, {7: 0.0}, {7: 0.0}, {2: 0.12}), 1.0, 0.0, 0.0
        )

        assert len(problems) == 1
        (problem,) = problems
        assert problem.blocking
        assert problem.description == "Weighted runoff coefficient exceeds 1."
        assert "Land use class 7" in problem.reason
        assert "soil class 2" in problem.reason
        assert_quotes(problem.reason, expected)

    @pytest.mark.unit
    def test_only_the_slope_term_can_cross_one_and_the_threshold_is_reported(self, tmp_path):
        """Supplement S9, PDF page 6: C_wp reaches 1 at the slope S* = 10 r / (1 - r).

        With A = 0, n = 0.0125, w1 = w3 = 0.5 and w2 = 0 the slope-free part is
        B = 0.5 * 0.02 / 0.0125 = 0.8 and the slope term can add up to w3 = 0.5,
        so C_wp reaches 1 where w3 S / (10 + S) = 1 - B.
        """
        # B = (1 - A) (w1 0.02 / n) = 1 * 0.5 * 0.02 / 0.0125 = 0.8
        # w3 S / (10 + S) = 1 - B = 0.2 has the root S = 10 r / (1 - r) with
        # r = (1 - B) / ((1 - A) w3) = 0.2 / 0.5 = 0.4, that is S* = 4 / 0.6 = 6.6667.
        b = c_wp(0.0, 0.0125, 0.0, 0.0, 0.5, 0.0, 0.5)
        assert b == pytest.approx(0.8, rel=1e-12)
        expected_threshold = 20.0 / 3.0
        # The root solves S9 itself: C_wp(S*) = 1 by an independent evaluation.
        assert c_wp(0.0, 0.0125, 0.0, expected_threshold, 0.5, 0.0, 0.5) == pytest.approx(
            1.0, rel=1e-12
        )

        problems = check_runoff_coefficient_domain(
            tables(tmp_path, {1: 0.0125}, {1: 0.0}, {1: 0.0}, {5: 0.0}), 0.5, 0.0, 0.5
        )

        assert len(problems) == 1
        (problem,) = problems
        assert not problem.blocking
        assert "Land use class 1" in problem.reason
        assert "soil class 5" in problem.reason
        assert_quotes(problem.reason, b)
        assert_quotes(problem.reason, expected_threshold)
        assert "PCRaster" in problem.reason

    @pytest.mark.unit
    def test_an_open_water_class_is_not_reported(self, tmp_path):
        """Supplement S6-S8, PDF page 6: A = a_i + a_o = 1 leaves no pervious fraction.

        A land use class fully covered by water carries no C_per term, so a small
        roughness cannot push its coefficient above 1: at A = 1 the whole of S6 is
        C_imp = 0.09 exp(2.4) = 0.9921 < 1, the largest value S7 can take on
        A in [0, 1] since it grows with A.
        """
        # C_wp(A = 1) = 0.09 exp(2.4 * 1) = 0.99209, below 1 for any roughness.
        saturated = c_wp(1.0, 0.01, 0.12, 0.0, 1.0, 0.0, 0.0)
        assert saturated == pytest.approx(0.09 * math.exp(2.4), rel=1e-12)
        assert saturated < 1.0

        problems = check_runoff_coefficient_domain(
            tables(tmp_path, {33: 0.01}, {33: 0.0}, {33: 1.0}, {5: 0.12}), 1.0, 0.0, 0.0
        )

        assert problems == []

    @pytest.mark.unit
    def test_area_fractions_that_add_up_above_one_are_left_to_the_other_check(self, tmp_path):
        """Supplement S8, PDF page 6: A = a_i + a_o > 1 is a table error, not a domain one.

        Area fractions that do not add up to 1 are blocking in check_lookup_tables;
        this check must not turn the negative pervious fraction 1 - A into a problem
        of its own.
        """
        problems = check_runoff_coefficient_domain(
            tables(tmp_path, {2: 0.01}, {2: 0.6}, {2: 0.6}, {5: 0.12}), 1.0, 0.0, 0.0
        )

        assert problems == []

    @pytest.mark.unit
    def test_an_area_fraction_outside_zero_and_one_is_left_to_the_other_check(self, tmp_path):
        """A fraction outside [0, 1] is blocking in check_lookup_tables; not reported here."""
        problems = check_runoff_coefficient_domain(
            tables(tmp_path, {2: 0.01}, {2: -0.5}, {2: 0.0}, {5: 0.12}), 1.0, 0.0, 0.0
        )

        assert problems == []

    @pytest.mark.unit
    def test_a_wilting_point_of_one_is_reported_instead_of_dividing_by_zero(self, tmp_path):
        """Supplement S9, PDF page 6: theta_PM / (1 - theta_PM) is undefined at T_w = 1."""
        problems = check_runoff_coefficient_domain(
            tables(tmp_path, {1: 0.16}, {1: 0.0}, {1: 0.0}, {4: 1.0}), 1 / 3, 1 / 3, 1 / 3
        )

        assert [problem.blocking for problem in problems] == [True]
        assert "Soil class 4" in problems[0].reason

    @pytest.mark.unit
    def test_a_non_positive_roughness_is_left_to_the_other_check(self, tmp_path):
        """n <= 0 is blocking in check_lookup_tables; this check must not add to it."""
        problems = check_runoff_coefficient_domain(
            tables(tmp_path, {1: 0.0}, {1: 0.0}, {1: 0.0}, {4: 0.12}), 1 / 3, 1 / 3, 1 / 3
        )

        assert problems == []

    @pytest.mark.unit
    def test_unreadable_tables_are_left_to_the_other_check(self, tmp_path):
        """A table that cannot be parsed is reported by check_lookup_tables, not here."""
        broken = tables(tmp_path, {1: 0.16}, {1: 0.0}, {1: 0.0}, {4: 0.12})
        Path(broken.manning).write_text("not a table\n", encoding="utf8")

        assert check_runoff_coefficient_domain(broken, 1 / 3, 1 / 3, 1 / 3) == []

    @pytest.mark.unit
    def test_the_bound_is_the_sum_of_the_slope_free_part_and_the_slope_weight(self, tmp_path):
        """Supplement S6-S9, PDF page 6: only the classes whose bound reaches 1 are reported.

        Land use class 1 (n = 0.005) has B = 3.2 with w1 = 0.8 and blocks; class 2
        (n = 0.05) has B = 0.32 and a bound of 0.52, below 1, so it is not reported.
        """
        # class 2: B = 0.8 * 0.02 / 0.05 = 0.32, bound = 0.32 + 0.2 = 0.52 < 1
        problems = check_runoff_coefficient_domain(
            tables(tmp_path, {1: 0.005, 2: 0.05}, {1: 0.0, 2: 0.0}, {1: 0.0, 2: 0.0}, {9: 0.0}),
            0.8,
            0.0,
            0.2,
        )

        assert len(problems) == 1
        assert problems[0].blocking

    @pytest.mark.unit
    def test_a_bound_of_exactly_one_reports_an_infinite_slope_instead_of_dividing_by_zero(
        self, tmp_path
    ):
        """Supplement S9, PDF page 6: the slope term is strictly below w3, so C_wp stays under 1.

        With A = 0, n = 0.02, w1 = w3 = 0.5 and T_w = 0 the slope-free part is
        B = 0.5 * 0.02 / 0.02 = 0.5 and the bound B + w3 is exactly 1, so
        r = (1 - B) / w3 = 1 and the slope of S* = 10 r / (1 - r) is not finite.
        """
        # B = 0.5 * 0.02 / 0.02 = 0.5; bound = 0.5 + 0.5 = 1.0; r = 0.5 / 0.5 = 1.0
        b = 0.5 * 0.02 / 0.02
        assert b + 0.5 == 1.0

        problems = check_runoff_coefficient_domain(
            tables(tmp_path, {1: 0.02}, {1: 0.0}, {1: 0.0}, {5: 0.0}), 0.5, 0.0, 0.5
        )

        assert len(problems) == 1
        (problem,) = problems
        assert not problem.blocking
        assert "infinite" in problem.reason

    @pytest.mark.unit
    def test_a_slope_free_part_of_exactly_one_blocks(self, tmp_path):
        """Supplement S5-S9, PDF page 6: C_wp = 1 already empties the S5 denominator.

        With A = 0, n = 0.02, w1 = 1, w2 = w3 = 0 and T_w = 0 the slope-free part is
        B = 0.02 / 0.02 = 1 exactly, the boundary of the domain: S5 becomes
        C_SR = P_MD / P_MD for every RCD, and any larger C_wp makes the denominator
        cross zero, so the pair is blocking rather than a warning.
        """
        # B = (1 - 0) (1 * 0.02 / 0.02 + 0 + 0) + 0 = 1.0
        b = c_wp(0.0, 0.02, 0.0, 0.0, 1.0, 0.0, 0.0)
        assert b == 1.0

        problems = check_runoff_coefficient_domain(
            tables(tmp_path, {1: 0.02}, {1: 0.0}, {1: 0.0}, {5: 0.0}), 1.0, 0.0, 0.0
        )

        assert len(problems) == 1
        (problem,) = problems
        assert problem.blocking
        assert problem.description == "Weighted runoff coefficient exceeds 1."
        assert_quotes(problem.reason, b)

    @pytest.mark.unit
    def test_every_term_of_the_coefficient_enters_the_reported_bound(self, tmp_path):
        """Supplement S6-S9, PDF page 6: the full B with an impervious fraction and a soil term.

        With a_i = 0.3, a_o = 0.2 (A = 0.5), n = 0.006, T_w = 0.2 and the weights
        w1 = 0.4, w2 = 0.1, w3 = 0.5:

            B = 0.5 (0.4 * 0.02 / 0.006 + 0.1 * 0.2 / 0.8) + 0.5 * 0.09 exp(1.2)
              = 0.5 * 1.3583333 + 0.1494053 = 0.8285719,

        below 1, while the slope term can add up to (1 - A) w3 = 0.25, so the pair is
        a warning and C_wp reaches 1 at S* = 21.8180.
        """
        b = c_wp(0.5, 0.006, 0.2, 0.0, 0.4, 0.1, 0.5)
        assert b == pytest.approx(0.5 * (0.4 * 0.02 / 0.006 + 0.1 * 0.25) + 0.045 * math.exp(1.2))
        assert b < 1.0 <= b + (1 - 0.5) * 0.5
        # w3 S / (10 + S) = (1 - B) / (1 - A) has the root S* = 10 r / (1 - r),
        # r = (1 - B) / ((1 - A) w3); C_wp(S*) = 1 by an independent evaluation of S9.
        r = (1.0 - b) / ((1 - 0.5) * 0.5)
        expected_threshold = 10.0 * r / (1.0 - r)
        assert c_wp(0.5, 0.006, 0.2, expected_threshold, 0.4, 0.1, 0.5) == pytest.approx(
            1.0, rel=1e-12
        )

        problems = check_runoff_coefficient_domain(
            tables(tmp_path, {12: 0.006}, {12: 0.3}, {12: 0.2}, {8: 0.2}), 0.4, 0.1, 0.5
        )

        assert len(problems) == 1
        (problem,) = problems
        assert not problem.blocking
        assert problem.description == "Weighted runoff coefficient may exceed 1 on steep cells."
        assert "Land use class 12" in problem.reason
        assert "soil class 8" in problem.reason
        assert_quotes(problem.reason, b)
        assert_quotes(problem.reason, expected_threshold)
