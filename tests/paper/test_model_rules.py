"""Conformity of the sub-grid rules the dynamic section applies inline.

The rules checked here are the ones the model applies cell by cell depending on
the sub-grid cover fractions: the open-water override of the root-zone moisture
and of the water evaporation, the impervious evapotranspiration, and the
saturation-excess form of the surface runoff. They are exercised on full runs of
the synthetic 3x3 dataset, whose tables are rewritten before the run so that a
single land-use class carries the fraction under test.

Every expectation is an independent float64 evaluation of the printed formula
(or of the rule statement) on the raster and table values fed to the model, never
of the model code. Outputs are Float32 rasters, so each comparison carries an
explicit tolerance justified in the docstring of its test.

The confirmed rules are documented in https://github.com/LabSid-USP/RUBEM/issues/331.
"""

from pathlib import Path

import numpy as np
import pcraster as pcr
import pytest

from tests.helpers.synthetic import (
    _LULC_CLASSES,
    _LULC_TABLES,
    _SOIL_TABLES,
    MISSING,
    write_synthetic_dataset,
)
from tests.helpers.synthetic import series_name as _series_name
from tests.unit.core.test_core import run_model

# Root-zone moisture contents in mm, as S11 writes the conversion the other way
# round: TU = theta * dg * Zr * 10 with dg in g/cm3 and Zr in cm.
TO_MM = _SOIL_TABLES["dg"] * _SOIL_TABLES["Zr"] * 10.0
TU_SAT = _SOIL_TABLES["Tsat"] * TO_MM


def _read_output(config, variable, step):
    """Return the Float32 output raster of ``variable`` at ``step`` as float64."""
    pcr.setclone(config["RASTERS"]["clone"])
    path = Path(config["DIRECTORIES"]["output"]) / _series_name(variable, step)
    return pcr.pcr2numpy(pcr.readmap(str(path)), np.nan).astype(np.float64)


def _read_input(config, path):
    """Return an input raster of the dataset as float64 on the synthetic clone."""
    pcr.setclone(config["RASTERS"]["clone"])
    return pcr.pcr2numpy(pcr.readmap(str(path)), np.nan).astype(np.float64)


def _series_path(config, directory_key, prefix, step):
    """Return the path of the step ``step`` member of an input map series."""
    return Path(config["DIRECTORIES"][directory_key]) / _series_name(prefix, step)


def _write_series_member(config, path, values):
    """Overwrite a Scalar member of an input series with ``values``."""
    pcr.setclone(config["RASTERS"]["clone"])
    array = np.asarray(values, dtype=np.float32)
    pcr.report(pcr.numpy2pcr(pcr.Scalar, array, MISSING), str(path))


def _write_lulc_table(config, name, values):
    """Rewrite a land-use lookup table, keeping a row for every class of the series."""
    lines = "".join(f"{lulc_class} {values[lulc_class]}\n" for lulc_class in _LULC_CLASSES)
    Path(config["TABLES"][name]).write_text(lines, encoding="utf8")


def _set_single_fraction(config, fraction, classes=(3,)):
    """Give ``fraction`` the whole cell area on ``classes`` and zero the other three."""
    for name in ("a_i", "a_o", "a_s", "a_v"):
        values = dict(_LULC_TABLES[name])
        for lulc_class in classes:
            values[lulc_class] = 1.0 if name == fraction else 0.0
        _write_lulc_table(config, name, values)


def _rainy_days(config, month):
    """Return the rainy days of ``month``, as ``lookupscalar(rainydays, month)`` reads them."""
    for line in Path(config["TABLES"]["rainydays"]).read_text(encoding="utf8").splitlines():
        key, value = line.split()
        if int(key) == month:
            return float(value)
    raise AssertionError(f"month {month} is missing from the rainy-days table")


def _rational_method_coefficients(config, precipitation):
    """Return (C_SR, C_h) of S5 and S10 at step 1 on a fully pervious cell.

    C_h  = (theta_TUR / theta_POR)^b               (S10, S11 in mm: TU_R / TU_sat)
    C_SR = C_wp P_MD / (C_wp P_MD - RCD C_wp + RCD) (S5)
    C_wp = (1 - A_imp) C_per + A_imp C_imp          (S6), A_imp = a_o + a_i = 0 (S8)
    C_per = w1 (0.02 / n) + w2 (theta_PM / (1 - theta_PM)) + w3 (S / (10 + S))  (S9)

    P_MD is the average daily rain on rainy days, P_m / d_p, with d_p read from the
    rainy-days table for January as ``lookupscalar(rainydays, month)`` reads it.
    theta_PM is the tabulated wilting point Tw of the soil class, and S is the
    terrain slope raster the model builds in ``initial()``. S9 lists S as "terrain
    slope in each cell (%)" while the model feeds ``pcr.slope(dem)``, a dimensionless
    rise-over-run gradient, into S / (10 + S); this evaluation uses the slope as
    ``pcr.slope(dem)`` returns it, the unit question is open.
    """
    landuse = _read_input(config, _series_path(config, "landuse", "cob", 1))
    assert np.unique(landuse).tolist() == [3], "step 1 must be the class the tables describe"
    pcr.setclone(config["RASTERS"]["clone"])
    slope = pcr.pcr2numpy(pcr.slope(pcr.readmap(config["RASTERS"]["dem"])), np.nan).astype(
        np.float64
    )
    calibration = config["CALIBRATION"]
    moisture = config["INITIAL_SOIL_CONDITIONS"]["t_ini"] * TU_SAT
    soil_moisture_coef = (moisture / TU_SAT) ** calibration["b"]
    weighted_coef = (
        calibration["w_1"] * (0.02 / _LULC_TABLES["manning"][3])
        + calibration["w_2"] * (_SOIL_TABLES["Tw"] / (1.0 - _SOIL_TABLES["Tw"]))
        + calibration["w_3"] * (slope / (10.0 + slope))
    )
    average_daily_rain = precipitation / _rainy_days(config, 1)
    recession = calibration["rcd"]
    runoff_coef = (weighted_coef * average_daily_rain) / (
        weighted_coef * average_daily_rain - recession * weighted_coef + recession
    )
    return runoff_coef, soil_moisture_coef


class TestOpenWaterCells:
    """Rules 2 and 4: a cell fully covered by water is saturated and evaporates."""

    @pytest.mark.paper
    @pytest.mark.integration
    def test_open_water_cells_stay_saturated_and_evaporate_the_capped_potential(self, tmp_path):
        """Supplement S1 (PDF page 5), S12 and S13 (PDF page 7), S28 (PDF page 9).

        Three confirmed rules of https://github.com/LabSid-USP/RUBEM/issues/331 meet
        on such a cell: "if alpha_W = 1 then TU_R = TU_S" of the S1 text keeps the
        root-zone moisture at the saturation content TU_sat = Tsat dg Zr 10 (rule 2);
        the water evaporation of S28, ET_R,W = ET_P / kp, is capped at the monthly
        rainfall (rule 4); and S13, SR = P_m - ET_R,A, is floored at zero (rule 4).

        The whole cell area is water (a_o = 1, the other three fractions zero), so
        the S21 sum reduces to ET_REAL = ET_R,W and the reported ``eta`` is the water
        evaporation itself. The step-1 pan coefficient is rewritten so that one cell
        has ET_P / kp above the rainfall (capped branch) and the others below it
        (uncapped branch). Because the cap makes ET_R,W <= P_m, the S13 difference is
        never negative: the floor binds only at equality, exactly on the capped cell,
        which therefore has SR = 0. The S13 identity is asserted from the saturated
        start of the dataset (``t_ini = 1``, so TU_R(0) = TU_sat); the companion test
        below starts below saturation and asserts only the storage rule there.

        Tolerances: ``smc`` is three Float32 products (Tsat dg Zr 10) against the same
        float64 product, ``eta`` one Float32 division and ``srn`` one further
        subtraction, so ``rel=1e-5`` is about a hundred times the Float32 epsilon.
        """
        base_dir = tmp_path / "water"
        base_dir.mkdir()
        config = write_synthetic_dataset(str(base_dir))
        # Both classes of the series are water, so step 2 exercises the same rule.
        _set_single_fraction(config, "a_o", classes=_LULC_CLASSES)

        capped_cell = (0, 0)
        pan_path = _series_path(config, "kp", "kp", 1)
        pan_coef = _read_input(config, pan_path)
        pan_coef[capped_cell] = 0.5
        _write_series_member(config, pan_path, pan_coef)

        precipitation = _read_input(config, _series_path(config, "prec", "prec", 1))
        potential_et = _read_input(config, _series_path(config, "etp", "etp", 1))

        run_model(str(base_dir), config=config)

        # Rule 2: TU_R = TU_sat on every water cell, at both steps.
        for step in (1, 2):
            moisture = _read_output(config, "smc", step)
            np.testing.assert_allclose(
                moisture,
                np.full(moisture.shape, TU_SAT),
                rtol=1e-5,
                err_msg=f"step {step}: smc on water cells differs from TU_sat",
            )

        # Rule 4, S28 with the confirmed cap: ET_R,W = min(ET_P / kp, P_m).
        expected_et = np.minimum(potential_et / pan_coef, precipitation)
        actual_et = _read_output(config, "eta", 1)
        np.testing.assert_allclose(actual_et, expected_et, rtol=1e-5)

        # The two branches must both occur: one cell is capped, the others are not.
        uncapped = potential_et / pan_coef
        assert uncapped[capped_cell] > precipitation[capped_cell]
        assert actual_et[capped_cell] != pytest.approx(uncapped[capped_cell], rel=1e-3)
        control_cell = (2, 2)
        assert uncapped[control_cell] < precipitation[control_cell]
        assert actual_et[control_cell] == pytest.approx(uncapped[control_cell], rel=1e-5)

        # Rule 4, S13 with the confirmed floor: SR = max(P_m - ET_R,A, 0).
        expected_runoff = np.maximum(precipitation - expected_et, 0.0)
        actual_runoff = _read_output(config, "srn", 1)
        np.testing.assert_allclose(actual_runoff, expected_runoff, rtol=1e-5, atol=1e-9)
        assert actual_runoff[capped_cell] == pytest.approx(0.0, abs=1e-9)
        assert expected_runoff[control_cell] > 0.0

    @pytest.mark.paper
    @pytest.mark.integration
    def test_open_water_cells_are_saturated_from_an_unsaturated_start(self, tmp_path):
        """Supplement S1 (PDF page 5) and S12 (PDF page 7), from TU_R(0) = 0.5 TU_sat.

        Rule 2 of https://github.com/LabSid-USP/RUBEM/issues/331 states that a cell
        fully covered by water is saturated, TU_R = TU_sat, whatever the balance of
        S1 would give. Starting the run at half the saturation content makes the rule
        the only possible source of the reported value: the S1 balance from
        TU_R(0) = 0.5 TU_sat = t_ini Tsat dg Zr 10 cannot reach TU_sat in one step,
        since the effective rainfall P_E = P_m - I is 110 mm at most (I = 0 with
        a_V = 0) against the 532.68 mm that separate the start from saturation, and
        the step also subtracts SR, LF, REC and ET_REAL. The reported ``smc`` is
        therefore checked against TU_sat at step 1 and, after the state handoff, at
        step 2.

        The water evaporation of S28 with the confirmed cap, ET_R,W = min(ET_P / kp,
        P_m), does not depend on the root-zone moisture, so it is asserted here too;
        the step-1 tables leave every cell on the uncapped branch,
        ET_P / kp = 85 / 0.8 = 106.25 mm < P_m = 110 mm. Only the storage and the
        evaporation are asserted from this start; the S13 runoff identity is checked
        from the saturated start in the test above.

        Tolerance: ``smc`` is the same three Float32 products as above against the
        float64 product Tsat dg Zr 10, and ``eta`` one Float32 division, so
        ``rel=1e-6`` still leaves about thirty times the observed rounding.
        """
        base_dir = tmp_path / "water_unsat"
        base_dir.mkdir()
        config = write_synthetic_dataset(str(base_dir))
        _set_single_fraction(config, "a_o", classes=_LULC_CLASSES)
        config["INITIAL_SOIL_CONDITIONS"]["t_ini"] = 0.5

        precipitation = _read_input(config, _series_path(config, "prec", "prec", 1))
        potential_et = _read_input(config, _series_path(config, "etp", "etp", 1))
        pan_coef = _read_input(config, _series_path(config, "kp", "kp", 1))

        run_model(str(base_dir), config=config)

        # The start is far below saturation, so the S1 balance cannot explain the
        # reported content: only the a_W = 1 override can.
        start = config["INITIAL_SOIL_CONDITIONS"]["t_ini"] * TU_SAT
        assert start + precipitation.max() < TU_SAT

        for step in (1, 2):
            moisture = _read_output(config, "smc", step)
            np.testing.assert_allclose(
                moisture,
                np.full(moisture.shape, TU_SAT),
                rtol=1e-6,
                err_msg=f"step {step}: smc on water cells differs from TU_sat",
            )

        # S28 with the confirmed cap, on the uncapped branch: ET_P / kp < P_m.
        expected_et = np.minimum(potential_et / pan_coef, precipitation)
        assert (potential_et / pan_coef < precipitation).all()
        np.testing.assert_allclose(_read_output(config, "eta", 1), expected_et, rtol=1e-6)


class TestImperviousCells:
    """Rule 5: the impervious evapotranspiration is the configured constant."""

    @pytest.mark.paper
    @pytest.mark.integration
    @pytest.mark.parametrize("interception_constant", [2.5, 1.5])
    def test_impervious_evapotranspiration_is_the_constant_where_it_rains(
        self, tmp_path, interception_constant
    ):
        """Supplement S21 and S30, PDF page 9, on a_i = 1 cells.

        S30 states ET_R,I = I, the interception loss of the impervious fraction;
        the model instead applies the confirmed rule of
        https://github.com/LabSid-USP/RUBEM/issues/331: ET_R,I is the constant
        ``CONSTANTS.i_imp`` (1 to 3 mm) wherever the monthly rainfall is not zero,
        and zero where it is. The whole cell area is impervious (a_i = 1, the other
        three fractions zero), so the S21 sum reduces to ET_REAL = a_I ET_R,I = i_imp.
        Both configured values are exercised, and the step-1 rainfall is rewritten
        with one dry cell.

        Tolerance: the constant is an exact Float32 value multiplied by the 0/1 flag,
        so ``rel=1e-6`` leaves room for one rounding; the dry cell must be exactly
        zero, compared with ``abs=1e-9``.
        """
        base_dir = tmp_path / f"imp{interception_constant}"
        base_dir.mkdir()
        config = write_synthetic_dataset(str(base_dir))
        config["CONSTANTS"]["i_imp"] = interception_constant
        _set_single_fraction(config, "a_i")

        dry_cell = (1, 1)
        precipitation_path = _series_path(config, "prec", "prec", 1)
        precipitation = _read_input(config, precipitation_path)
        precipitation[dry_cell] = 0.0
        _write_series_member(config, precipitation_path, precipitation)

        run_model(str(base_dir), config=config)
        actual_et = _read_output(config, "eta", 1)

        # ET_REAL = a_I * ET_R,I with ET_R,I = i_imp if P_m != 0 else 0.
        expected = np.where(precipitation != 0.0, interception_constant, 0.0)
        assert expected[dry_cell] == 0.0
        wet = np.ones(expected.shape, dtype=bool)
        wet[dry_cell] = False
        assert (expected[wet] == interception_constant).all()
        np.testing.assert_allclose(actual_et, expected, rtol=1e-6, atol=1e-9)
        assert actual_et[dry_cell] == pytest.approx(0.0, abs=1e-9)


class TestSaturationExcessRunoff:
    """Rule 3 and S4: a saturated pervious cell routes all the effective rainfall."""

    @pytest.mark.paper
    @pytest.mark.integration
    def test_a_saturated_pervious_cell_runs_off_the_whole_effective_rainfall(self, tmp_path):
        """Supplement S2 (PDF page 5) and S4 (PDF page 6), with TU_R = TU_sat.

        With ``t_ini = 1`` the initial root-zone moisture TU_R(0) = TU_sat, and the
        confirmed rule of https://github.com/LabSid-USP/RUBEM/issues/331 makes the
        surface runoff of a pervious cell the whole effective precipitation of S2,
        SR = P_E = P_m - I, instead of the S4 product: the soil cannot store more.
        The default land-use table gives the step-1 class a_v = 1, so no water and no
        impervious fraction interferes.

        The interception raster of the same step is the model's own S14 output, which
        S4 takes as an input; the rule under test is the identity between ``srn`` and
        ``prec - itp``. One Float32 subtraction of two reported values: ``rel=1e-6``.
        """
        base_dir = tmp_path / "sat"
        base_dir.mkdir()
        config = write_synthetic_dataset(str(base_dir))
        assert config["INITIAL_SOIL_CONDITIONS"]["t_ini"] == 1.0
        assert _LULC_TABLES["a_v"][3] == 1.0
        assert _LULC_TABLES["a_o"][3] == _LULC_TABLES["a_i"][3] == _LULC_TABLES["a_s"][3] == 0.0

        run_model(str(base_dir), config=config)

        precipitation = _read_input(config, _series_path(config, "prec", "prec", 1))
        interception = _read_output(config, "itp", 1)
        surface_runoff = _read_output(config, "srn", 1)

        expected = precipitation - interception
        assert (interception > 0.0).all(), "the effective rainfall must be a real difference"
        np.testing.assert_allclose(surface_runoff, expected, rtol=1e-6)

        # The saturated branch must be the one taken: the S4 product of the same step
        # (C_h = 1 here, C_SR < 1) is strictly smaller than the effective rainfall.
        runoff_coef, soil_moisture_coef = _rational_method_coefficients(config, precipitation)
        assert soil_moisture_coef == pytest.approx(1.0)
        assert (runoff_coef < 1.0).all()
        assert surface_runoff.flatten().tolist() != pytest.approx(
            (runoff_coef * soil_moisture_coef * expected).flatten().tolist(), rel=1e-3
        )

    @pytest.mark.paper
    @pytest.mark.integration
    def test_an_unsaturated_pervious_cell_follows_the_rational_method(self, tmp_path):
        """Supplement S4 to S11, PDF pages 6 and 7, with TU_R(0) = 0.5 TU_sat.

        Rule 3 of https://github.com/LabSid-USP/RUBEM/issues/331 applies only at
        saturation; below it the printed S4 governs the cell.

        Below saturation the surface runoff of a pervious cell is the S4 product
        SR = C_SR C_h (P_m - I), with C_SR and C_h evaluated in float64 from the
        printed S5 to S11 by :func:`_rational_method_coefficients` (see its docstring
        for the formulas, for the rainy days of S5 and for the open question on the
        unit of the slope S of S9). The default land-use table gives the step-1 class
        a_v = 1, so A_imp = a_o + a_i = 0 (S8) and S6 leaves C_wp = C_per.

        Tolerance: the model chains about ten Float32 operations through S9, S5, S10
        and S4 before rounding the reported raster, and the independent float64
        product agrees with it to 4.7e-8 in relative terms on the nine cells, so
        ``rel=1e-6`` keeps about twenty times that margin while staying roughly six
        orders of magnitude below the gap to the saturated branch P_m - I.
        """
        base_dir = tmp_path / "unsat"
        base_dir.mkdir()
        config = write_synthetic_dataset(str(base_dir))
        config["INITIAL_SOIL_CONDITIONS"]["t_ini"] = 0.5

        run_model(str(base_dir), config=config)

        precipitation = _read_input(config, _series_path(config, "prec", "prec", 1))
        interception = _read_output(config, "itp", 1)
        surface_runoff = _read_output(config, "srn", 1)

        runoff_coef, soil_moisture_coef = _rational_method_coefficients(config, precipitation)
        # S4: SR = C_SR C_h (P_m - I).
        expected = runoff_coef * soil_moisture_coef * (precipitation - interception)

        np.testing.assert_allclose(surface_runoff, expected, rtol=1e-6)
        # The rational method must damp the effective rainfall: the cell is not on the
        # saturated branch of rule 3.
        assert (runoff_coef * soil_moisture_coef < 1.0).all()
        assert surface_runoff.flatten().tolist() != pytest.approx(
            (precipitation - interception).flatten().tolist(), rel=1e-3
        )
