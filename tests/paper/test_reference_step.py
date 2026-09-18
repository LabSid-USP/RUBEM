"""End-to-end conformity of a model run with the independent reference of S1 to S35.

:mod:`tests.paper.reference` evaluates one monthly step of the published
formulation in float64 without importing anything from the model package. This
module runs the model on the synthetic 3x3 dataset, feeds the very same inputs
to that reference, and compares the nine output rasters cell by cell.

The two steps of the default dataset exercise complementary branches:

* step 1 starts from ``t_ini = 1``, so ``TU_R,0 = TU_SAT`` and the saturation
  rule of S4 (rule 3 of https://github.com/LabSid-USP/RUBEM/issues/331) gives
  ``SR = P_m - I``; the land-use class of the step is fully vegetated
  (``a_v = 1``), so S21 reduces to its vegetated term;
* step 2 starts from the depleted ``TU_R,1``, well below ``TU_SAT``, so the S4
  product ``C_SR C_h (P_m - I)`` is evaluated in full, and its land-use class
  carries bare soil (S25) and impervious (S30 with rule 5) fractions, which
  brings the S6/S7 weighting of the impervious runoff coefficient into play.

That forcing leaves four conditionals of the formulation untaken, so two
variants of the dataset turn them on; without them a wrong transcription of the
corresponding lines of the reference would pass unnoticed.

* the open-water variant makes both land-use classes cells fully covered by
  water (``alpha_W = 1``), which exercises rule 4 (the ``min(ET_P / kp, P_m)``
  cap of S28, slack at step 1 and binding at step 2, and the
  ``SR = max(P_m - ET_R,W, 0)`` of S13) and rule 2 (the root zone of such a cell
  stays at ``TU_SAT``);
* the threshold variant raises ``NDVI_min`` and ``BF_0`` so that S24 falls back
  to ``kc_min``, the cap of the #325 correction binds on S33, and the following
  step takes the zero branch of S33.

Besides comparing the two implementations, each dataset has one test that pins
its steps to closed-form values evaluated here from the printed formulas on the
concrete numbers of the dataset, so that the agreement is anchored to the
supplement and not only to a second implementation of it.

The model computes in PCRaster Float32 while the reference computes in float64,
so every comparison carries an explicit tolerance: ``rtol=1e-4`` is far above
the ~1e-7 relative resolution of Float32 even after the couple of dozen
operations of a step, and ``atol=1e-6`` only keeps a cell whose exact value is
zero from failing on a relative comparison.
"""

from calendar import monthrange
from datetime import date
from math import exp, log
from pathlib import Path

import numpy as np
import pcraster as pcr
import pytest

from tests.helpers.synthetic import series_name, write_synthetic_dataset
from tests.paper import reference
from tests.unit.core.test_core import run_model

# The synthetic series starts in January 2000; February 2000 is a leap February.
START_DATE = date(2000, 1, 1)
STEPS = (1, 2)

RTOL = 1e-4
ATOL = 1e-6

# Values of the synthetic dataset (tests/helpers/synthetic.py), repeated here so
# that the closed-form expectations below are an evaluation of the printed
# formulas on concrete numbers instead of a second reading of the generator.
CELL_AREA = 500.0 * 500.0  # A of S35 [m2]
D_G, Z_R = 1.54, 150.39  # d_g [g cm-3] and Z_r [cm] of S11
THETA_POR, THETA_PM, THETA_CC = 0.46, 0.12, 0.26  # S10 to S12, S26
K_R = 38.29  # K_R of S31 and S32 [mm month-1]
ALPHA, F, ALPHA_GW, X_DAMPING = 4.5, 0.5, 0.5, 0.5  # S17, S31/S32, S33, S35
FPAR_MIN, FPAR_MAX, LAI_MAX = 0.001, 0.95, 12.0  # S18 and S19
NDVI_MIN, NDVI_MAX = 0.2, 0.9  # S19 through RS, S23
BF_0, TU_S_0, BF_THRESH = 0.1, 1.1, 1.0  # BF_t-1, TU_S,t-1 and BF_thresh of S33

# S11 read at theta_POR, theta_PM and theta_CC: TU = theta * d_g * Z_r * 10 [mm].
TU_SAT = THETA_POR * D_G * Z_R * 10.0
TU_PM = THETA_PM * D_G * Z_R * 10.0
TU_CC = THETA_CC * D_G * Z_R * 10.0

# Forcing of step 1 (January 2000) and land-use class 3 of the default dataset.
P_1, ET_P_1, NDVI_1, KP_1 = 110.0, 85.0, 0.55, 0.8
RAINY_DAYS_1, DAYS_1 = 11.0, 31.0
KC_MIN_1, KC_MAX_1 = 1.14, 1.8
# Forcing of step 2 (February 2000, a leap February).
P_2, ET_P_2, KP_2, DAYS_2 = 100.0, 90.0, 0.8, 29.0
# Overrides of the threshold variant: an NDVI_min that puts step 1 on the
# kc_min side of S24, and a BF_t-1 large enough for the #325 cap to bind.
NDVI_MIN_HIGH, BF_0_HIGH = 0.52, 100.0

# The 3x3 DEM decreases towards its north-west corner, so the whole grid drains
# to cell (0, 0) and the accumulation of S35 gathers the nine cells there.
PIT = (0, 0)
GRID_CELLS = 9


def _read_field(path):
    """Return a raster of the dataset as a float64 array on the current clone."""
    return pcr.pcr2numpy(pcr.readmap(str(path)), np.nan).astype(np.float64)


def _read_classes(path):
    """Return a categorical raster of the dataset as an int64 array."""
    return pcr.pcr2numpy(pcr.readmap(str(path)), 0).astype(np.int64)


def _read_lookup_table(path):
    """Parse a PCRaster lookup table of the dataset into a ``{class: value}`` dict."""
    table = {}
    with Path(path).open(encoding="utf8") as handle:
        for line in handle:
            if not line.strip():
                continue
            key, value = line.split()
            table[int(key)] = float(value)
    return table


def _write_lookup_table(path, values):
    """Rewrite a PCRaster lookup table of the dataset with ``{class: value}``."""
    Path(path).write_text(
        "".join(f"{cls} {value}\n" for cls, value in sorted(values.items())), encoding="utf8"
    )


def _month_of_step(step):
    """Return the calendar month the model assigns to ``step`` (``relativedelta`` months)."""
    months = START_DATE.month - 1 + (step - 1)
    return date(START_DATE.year + months // 12, months % 12 + 1, START_DATE.day)


def _build_tables(config):
    """Build the reference lookup tables from the very files the model reads."""
    tables = config["TABLES"]
    return reference.Tables(
        a_v=_read_lookup_table(tables["a_v"]),
        a_s=_read_lookup_table(tables["a_s"]),
        a_o=_read_lookup_table(tables["a_o"]),
        a_i=_read_lookup_table(tables["a_i"]),
        manning=_read_lookup_table(tables["manning"]),
        kc_min=_read_lookup_table(tables["k_c_min"]),
        kc_max=_read_lookup_table(tables["k_c_max"]),
        dg=_read_lookup_table(tables["bulk_density"]),
        zr=_read_lookup_table(tables["rootzone_depth"]),
        t_sat=_read_lookup_table(tables["t_sat"]),
        t_wp=_read_lookup_table(tables["t_wp"]),
        t_fcap=_read_lookup_table(tables["t_fcap"]),
        k_r=_read_lookup_table(tables["k_sat"]),
    )


def _build_parameters(config):
    """Build the reference parameters from the calibration and constant entries."""
    calibration = config["CALIBRATION"]
    constants = config["CONSTANTS"]
    grid = config["GRID"]["grid"]
    return reference.Parameters(
        alpha=calibration["alpha"],
        b=calibration["b"],
        w1=calibration["w_1"],
        w2=calibration["w_2"],
        w3=calibration["w_3"],
        rcd=calibration["rcd"],
        f=calibration["f"],
        alpha_gw=calibration["alpha_gw"],
        x=calibration["x"],
        fpar_min=constants["fpar_min"],
        fpar_max=constants["fpar_max"],
        lai_max=constants["lai_max"],
        i_imp=constants["i_imp"],
        baseflow_threshold=config["INITIAL_SOIL_CONDITIONS"]["bfw_lim"],
        cell_area=grid * grid,
    )


def _build_inputs(config, step, static):
    """Build the reference inputs of ``step`` from the rasters and tables of the dataset."""
    directories = config["DIRECTORIES"]
    prefixes = config["FILENAME_PREFIXES"]
    month = _month_of_step(step)
    return reference.Inputs(
        p=_read_field(f"{directories['prec']}{series_name(prefixes['prec_prefix'], step)}"),
        et_p=_read_field(f"{directories['etp']}{series_name(prefixes['etp_prefix'], step)}"),
        kp=_read_field(f"{directories['kp']}{series_name(prefixes['kp_prefix'], step)}"),
        ndvi=_read_field(f"{directories['ndvi']}{series_name(prefixes['ndvi_prefix'], step)}"),
        ndvi_min=static["ndvi_min"],
        ndvi_max=static["ndvi_max"],
        landuse=_read_classes(
            f"{directories['landuse']}{series_name(prefixes['landuse_prefix'], step)}"
        ),
        soil=static["soil"],
        slope=static["slope"],
        ldd=static["ldd"],
        rainy_days=static["rainy_days"][month.month],
        days_in_month=monthrange(month.year, month.month)[1],
    )


def _read_model_outputs(config, step):
    """Read the nine Float32 output rasters the model wrote at ``step``."""
    return {
        variable: _read_field(f"{config['DIRECTORIES']['output']}/{series_name(variable, step)}")
        for variable in reference.OUTPUT_VARIABLES
    }


def _run_model_and_reference(base_dir, config):
    """Run the model on ``config`` and the reference recursion beside it.

    The static rasters are taken exactly as ``initial()`` takes them: the slope
    is ``pcr.slope(dem)``, and the drain directions are read from the configured
    LDD raster, which is the branch ``initial()`` follows whenever the
    configuration names one (it falls back to
    ``lddcreate(dem, 1e31, 1e31, 1e31, 1e31)`` only when it does not, and the
    dataset built that very raster with that call).

    The slope is used as ``pcr.slope(dem)`` returns it (rise over run); S9
    prints S in %, and the unit question is open.

    The initial state is the one ``initial()`` establishes from
    ``INITIAL_SOIL_CONDITIONS``: ``TU_R,0 = t_ini * TU_SAT`` built with
    :func:`tests.paper.reference.saturation_mm` so that the S4 saturation rule
    compares equal, ``TU_S,0 = s_sat_ini``, ``BF_0 = bfw_ini`` and a routed
    discharge of zero.
    """
    run_model(base_dir, config=config)

    pcr.setclone(config["RASTERS"]["clone"])
    tables = _build_tables(config)
    params = _build_parameters(config)
    soil = _read_classes(config["RASTERS"]["soil"])
    static = {
        "ndvi_min": _read_field(config["RASTERS"]["ndvi_min"]),
        "ndvi_max": _read_field(config["RASTERS"]["ndvi_max"]),
        "soil": soil,
        "slope": pcr.pcr2numpy(pcr.slope(pcr.readmap(config["RASTERS"]["dem"])), np.nan).astype(
            np.float64
        ),
        "ldd": pcr.pcr2numpy(pcr.readmap(config["RASTERS"]["ldd"]), 0).astype(np.uint8),
        "rainy_days": _read_lookup_table(config["TABLES"]["rainydays"]),
    }

    initial = config["INITIAL_SOIL_CONDITIONS"]
    saturation = reference.saturation_mm(tables, soil)
    state = reference.State(
        tu_r=initial["t_ini"] * saturation,
        tu_s=np.full(saturation.shape, float(initial["s_sat_ini"])),
        bf=np.full(saturation.shape, float(initial["bfw_ini"])),
        q_prev=np.zeros(saturation.shape),
    )

    paired = {}
    for step in STEPS:
        inputs = _build_inputs(config, step, static)
        outputs, state = reference.step(inputs, tables, params, state)
        paired[step] = (_read_model_outputs(config, step), outputs, inputs)
    return config, paired


@pytest.fixture(scope="module")
def model_and_reference(tmp_path_factory):
    """The default synthetic dataset: two pervious land-use classes, ``t_ini = 1``."""
    base_dir = tmp_path_factory.mktemp("reference_step")
    return _run_model_and_reference(str(base_dir), write_synthetic_dataset(str(base_dir)))


@pytest.fixture(scope="module")
def open_water_model_and_reference(tmp_path_factory):
    """The same dataset with both land-use classes turned into cells fully covered by water.

    Both steps are then evaluated with ``alpha_W = 1`` and every other fraction
    at zero, which is the condition of S13 and of rules 2 and 4 of
    https://github.com/LabSid-USP/RUBEM/issues/331, and the two steps straddle
    the cap of rule 4: at step 1 ``ET_P / kp = 106.25 mm`` stays below
    ``P_m = 110 mm``, while at step 2 ``ET_P / kp = 112.5 mm`` exceeds
    ``P_m = 100 mm`` and the cap binds. ``t_ini`` stays at 1: rule 2 keeps such
    a cell at ``TU_SAT`` from the first balance on, so this is the state the run
    reaches on its own from the second step onwards.
    """
    base_dir = tmp_path_factory.mktemp("reference_step_open_water")
    config = write_synthetic_dataset(str(base_dir))
    _write_lookup_table(config["TABLES"]["a_o"], {3: 1.0, 4: 1.0})
    for fraction in ("a_v", "a_s", "a_i"):
        _write_lookup_table(config["TABLES"][fraction], {3: 0.0, 4: 0.0})
    return _run_model_and_reference(str(base_dir), config)


@pytest.fixture(scope="module")
def threshold_model_and_reference(tmp_path_factory):
    """The same dataset tuned so that the threshold branches of S24 and S33 are taken.

    The default forcing never reaches three conditionals of the formulation, so
    this variant turns them on without touching the land use:

    * ``NDVI_min`` is raised to 0.52, so step 1 (``NDVI = 0.55``) falls on the
      ``NDVI <= 1.1 NDVI_min`` side of S24 and takes ``kc = kc_min`` while
      step 2 (``NDVI = 0.60``) still interpolates with S23;
    * ``BF_0`` is raised to 100 mm, so the recession of S33 at step 1 exceeds
      the available ``TU_S,0 + REC`` and the cap of the #325 correction binds;
    * that cap empties the saturated zone (``TU_S,1 = 0``), so step 2 falls on
      the ``TU_S <= BF_thresh`` side of S33 and its baseflow is zero.
    """
    base_dir = tmp_path_factory.mktemp("reference_step_threshold")
    config = write_synthetic_dataset(str(base_dir))
    config["INITIAL_SOIL_CONDITIONS"]["bfw_ini"] = BF_0_HIGH
    pcr.setclone(config["RASTERS"]["clone"])
    pcr.report(
        pcr.numpy2pcr(pcr.Scalar, np.full((3, 3), NDVI_MIN_HIGH, dtype=np.float32), -9999.0),
        config["RASTERS"]["ndvi_min"],
    )
    return _run_model_and_reference(str(base_dir), config)


def _interception_of_step_1(vegetated_fraction, ndvi_min=NDVI_MIN):
    """Return I of S14 at step 1, evaluated from S20, S19, S18, S17, S16 and S15.

    Supplement S14 to S20, PDF page 8, with the #323 correction of the S16
    denominator (P_m itself, since P_m = 110 mm is not zero).
    """
    # S20: RS = (1 + NDVI) / (1 - NDVI), applied to NDVI, NDVI_min and NDVI_max.
    rs = (1.0 + NDVI_1) / (1.0 - NDVI_1)
    rs_min = (1.0 + ndvi_min) / (1.0 - ndvi_min)
    rs_max = (1.0 + NDVI_MAX) / (1.0 - NDVI_MAX)
    # S19: FPAR = min((RS - RS_min)(FPAR_max - FPAR_min)/(RS_max - RS_min) + FPAR_min, 0.95)
    fpar = min((rs - rs_min) * (FPAR_MAX - FPAR_MIN) / (rs_max - rs_min) + FPAR_MIN, 0.95)
    # S18: LAI = LAI_max log(1 - FPAR) / log(1 - FPAR_max)
    lai = LAI_MAX * log(1.0 - fpar) / log(1.0 - FPAR_MAX)
    # S17: I_D = alpha LAI (1 - 1 / (1 + P_m [1 - exp(-0.463 LAI)] / (alpha LAI)))
    i_d = ALPHA * lai * (1.0 - 1.0 / (1.0 + P_1 * (1.0 - exp(-0.463 * lai)) / (ALPHA * lai)))
    # S16: I_R = 1 - exp(-I_D d_P / P_m); S15: I_V = P_m I_R; S14: I = alpha_V I_V.
    return vegetated_fraction * P_1 * (1.0 - exp(-i_d * RAINY_DAYS_1 / P_1))


def _saturated_flows(previous_baseflow, previous_saturated_storage):
    """Return ``(LF, REC, BF)`` of a month whose root zone starts at ``TU_R,t-1 = TU_SAT``.

    Supplement S31 and S32 (PDF page 11) collapse to ``f K_R`` and ``(1 - f) K_R``
    at saturation. S33 (PDF page 11) takes its recession branch only while
    ``TU_S,t-1`` exceeds ``BF_thresh``, and the #325 correction caps the result
    at the water the saturated zone actually holds, ``TU_S,t-1 + REC``.
    """
    lateral_flow = F * K_R * (TU_SAT / TU_SAT) ** 2  # S31
    recharge = (1.0 - F) * K_R * (TU_SAT / TU_SAT) ** 2  # S32
    decay = exp(-ALPHA_GW)
    # S33: BF = BF_t-1 exp(-alpha_gw) + (1 - exp(-alpha_gw)) REC while TU_S > BF_thresh.
    recession = (
        previous_baseflow * decay + (1.0 - decay) * recharge
        if previous_saturated_storage > BF_THRESH
        else 0.0
    )
    return lateral_flow, recharge, min(recession, previous_saturated_storage + recharge)  # #325


def _assert_the_grid_drains_to_the_pit(ldd):
    """Check the topology the routed-discharge expectations assume.

    ``pcr.accuflux`` gathers the material of every upstream cell, so the outlet
    of S35 carries the nine per-cell volumes only while the grid has a single
    pit (LDD code 5) and it sits at :data:`PIT`. The synthetic DEM decreases
    monotonically towards its north-west corner, which is what ``lddcreate``
    turns into that topology.
    """
    assert ldd[PIT] == 5, "the outlet of the grid must be its north-west corner"
    assert (ldd == 5).sum() == 1, "the grid must have a single pit"


def _routed_discharge_at_the_pit(total_discharge, days, previous_discharge=0.0):
    """Return Q_t of S35 at the outlet, where the nine cells of the grid accumulate.

    Supplement S35, PDF page 12: ``Q_t = x Q_t-1 + 0.001 (1 - x) A Q_Tot / (days 24 3600)``
    aggregated along the LDD. The routed discharge of the month before step 1 is
    zero, and whenever every cell carries the same ``Q_Tot`` the outlet holds
    nine times the per-cell volume.
    """
    cell_volume = 0.001 * (1.0 - X_DAMPING) * CELL_AREA * total_discharge / (days * 24.0 * 3600.0)
    return X_DAMPING * previous_discharge + GRID_CELLS * cell_volume


class TestReferenceStep:
    @pytest.mark.paper
    @pytest.mark.integration
    def test_the_dataset_exercises_both_branches_of_the_saturation_rule(self, model_and_reference):
        """The run must cover the S4 saturation rule and the full S4 product.

        Supplement S4, PDF page 6, and rule 3 of
        https://github.com/LabSid-USP/RUBEM/issues/331: with ``t_ini = 1`` the
        root zone starts at ``TU_SAT``, so step 1 takes the ``SR = P_m - I``
        branch on every cell, while step 2 starts from ``TU_R,1``, which the
        balance of step 1 left strictly below ``TU_SAT``, and therefore takes
        the ``C_SR C_h (P_m - I)`` branch. Without this the comparison below
        could pass while testing a single branch twice.

        The two constants asserted here are the ones the reference substitutes
        for printed literals: the where-list of S19 (PDF page 8) states that the
        0.95 of the formula is FPAR_max, and the where-list of S30 (PDF page 10)
        bounds the impervious interception of rule 5 to 1 to 3 mm.
        """
        config, paired = model_and_reference
        assert config["INITIAL_SOIL_CONDITIONS"]["t_ini"] == 1.0
        assert config["CONSTANTS"]["fpar_max"] == FPAR_MAX == 0.95
        assert 1.0 <= config["CONSTANTS"]["i_imp"] <= 3.0

        model_1, reference_1, inputs_1 = paired[1]
        np.testing.assert_allclose(
            model_1["srn"], inputs_1.p - reference_1["itp"], rtol=RTOL, atol=ATOL
        )

        model_2, reference_2, inputs_2 = paired[2]
        assert (model_1["smc"] < TU_SAT).all(), "step 2 must start below saturation"
        assert not np.allclose(
            model_2["srn"], inputs_2.p - reference_2["itp"], rtol=RTOL, atol=ATOL
        ), "step 2 must exercise the C_SR C_h product, not the saturation branch"
        # The land-use class of step 2 carries the bare soil and impervious
        # fractions, so S25 and S30 contribute to its evapotranspiration.
        assert not np.array_equal(inputs_1.landuse, inputs_2.landuse)

    @pytest.mark.paper
    @pytest.mark.integration
    def test_step_1_matches_values_derived_from_the_printed_formulas(self, model_and_reference):
        """Supplement S1 to S35, PDF pages 5 to 12: step 1 against closed-form values.

        Every expectation is evaluated here from the printed formulas on the
        forcing of January 2000 (``P_m = 110 mm``, ``ET_P = 85 mm``,
        ``NDVI = 0.55``, ``d_P = 11``, 31 days) and land-use class 3
        (``alpha_V = 1``, ``kc_min = 1.14``, ``kc_max = 1.8``), so the agreement
        of the model with the reference is anchored to the supplement itself.
        Every output but the routed discharge is uniform over the grid, because
        the S4 saturation branch removes the only slope-dependent term.
        """
        _, paired = model_and_reference
        model_outputs, _, inputs = paired[1]
        _assert_the_grid_drains_to_the_pit(inputs.ldd)

        interception = _interception_of_step_1(1.0)  # S14 with alpha_V = 1
        surface_runoff = P_1 - interception  # S4 with rule 3, since TU_R,0 = TU_SAT
        lateral_flow, recharge, baseflow = _saturated_flows(BF_0, TU_S_0)  # S31, S32, S33
        # S23: kc = kc_min + (kc_max - kc_min)(NDVI - NDVI_min)/(NDVI_max - NDVI_min);
        # NDVI = 0.55 > 1.1 NDVI_min = 0.22, so S24 does not apply.
        crop_coef = KC_MIN_1 + (KC_MAX_1 - KC_MIN_1) * ((NDVI_1 - NDVI_MIN) / (NDVI_MAX - NDVI_MIN))
        # S26: ks = ln(TU_R - TU_PM + 1) / ln(TU_CC - TU_PM + 1) at TU_R = TU_SAT.
        water_stress = log(TU_SAT - TU_PM + 1.0) / log(TU_CC - TU_PM + 1.0)
        # S21 with alpha_V = 1 and every other fraction at zero, over S22.
        evapotranspiration = ET_P_1 * crop_coef * water_stress
        # S1 and S2: TU_R = TU_SAT + (P_m - I) - SR - LF - REC - ET_REAL, and
        # SR = P_m - I cancels the effective rainfall.
        soil_moisture = TU_SAT - lateral_flow - recharge - evapotranspiration
        total_discharge = surface_runoff + lateral_flow + baseflow  # S34

        expected = {
            "itp": interception,
            "bfw": baseflow,
            "srn": surface_runoff,
            "eta": evapotranspiration,
            "lfw": lateral_flow,
            "rec": recharge,
            "smc": soil_moisture,
            "rnf": total_discharge,
        }
        for variable, value in expected.items():
            np.testing.assert_allclose(
                model_outputs[variable],
                value,
                rtol=RTOL,
                atol=ATOL,
                err_msg=f"step 1: {variable} differs from the closed-form evaluation",
            )
        assert model_outputs["arn"][PIT] == pytest.approx(
            _routed_discharge_at_the_pit(total_discharge, DAYS_1), rel=RTOL
        )

    @pytest.mark.paper
    @pytest.mark.integration
    @pytest.mark.parametrize("variable", reference.OUTPUT_VARIABLES)
    def test_step_1_matches_the_reference(self, model_and_reference, variable):
        """Supplement S1 to S35, PDF pages 5 to 12: step 1 of the model equals the reference.

        The model state at step 1 is the initial state of ``initial()``, so every
        flux of the step is a direct evaluation of the printed formulas on the
        input rasters. Float32 outputs against float64 expectations: see the
        module docstring for the tolerance.
        """
        _, paired = model_and_reference
        model_outputs, reference_outputs, _ = paired[1]
        np.testing.assert_allclose(
            model_outputs[variable],
            reference_outputs[variable],
            rtol=RTOL,
            atol=ATOL,
            err_msg=f"step 1: {variable} differs from the reference evaluation",
        )

    @pytest.mark.paper
    @pytest.mark.integration
    @pytest.mark.parametrize("variable", reference.OUTPUT_VARIABLES)
    def test_step_2_matches_the_reference_recursion(self, model_and_reference, variable):
        """Supplement S1 to S35, PDF pages 5 to 12: step 2 equals the reference recursion.

        The reference carries its own ``(TU_R, TU_S, BF, Q)`` from step 1 into
        step 2, exactly as S1, S3, S33 and S35 prescribe, so this comparison also
        pins the state the model hands from one month to the next. February 2000
        has 29 days and 12 rainy days, both of which enter the step.
        """
        _, paired = model_and_reference
        model_outputs, reference_outputs, _ = paired[2]
        np.testing.assert_allclose(
            model_outputs[variable],
            reference_outputs[variable],
            rtol=RTOL,
            atol=ATOL,
            err_msg=f"step 2: {variable} differs from the reference recursion",
        )


class TestOpenWaterReferenceStep:
    """The same comparison on a dataset whose two land-use classes are open water."""

    @pytest.mark.paper
    @pytest.mark.integration
    def test_both_steps_match_values_derived_from_the_printed_formulas(
        self, open_water_model_and_reference
    ):
        """Supplement S13 and S28, PDF pages 7 and 9, with rules 2 and 4 of issue 331.

        On a cell with ``alpha_W = 1`` and ``t_ini = 1``, S14 gives ``I = 0``
        because ``alpha_V = 0``, S21 reduces to its water term, and rule 2 keeps
        the root zone at ``TU_SAT`` at both steps, so S31, S32 and S33 are the
        saturated flows. The two steps sit on opposite sides of the rule 4 cap:

        * step 1: ``ET_R,W = min(85 / 0.8, 110) = 106.25 mm`` leaves the cap
          slack, and S13 gives ``SR = max(110 - 106.25, 0) = 3.75 mm``;
        * step 2: ``ET_P / kp = 90 / 0.8 = 112.5 mm`` exceeds ``P_m = 100 mm``,
          so the cap binds at ``ET_R,W = 100 mm`` and ``SR = 0``.

        Rules 2 and 4 are documented in
        https://github.com/LabSid-USP/RUBEM/issues/331.
        """
        config, paired = open_water_model_and_reference
        assert config["INITIAL_SOIL_CONDITIONS"]["t_ini"] == 1.0
        assert _read_lookup_table(config["TABLES"]["a_o"]) == {3: 1.0, 4: 1.0}
        _assert_the_grid_drains_to_the_pit(paired[1][2].ldd)

        # Step 1: the cap of rule 4 is slack.
        et_1 = min(ET_P_1 / KP_1, P_1)  # S28 with rule 4
        assert et_1 == pytest.approx(106.25, rel=1e-12)
        runoff_1 = max(P_1 - et_1, 0.0)  # S13 with rule 4
        assert runoff_1 == pytest.approx(3.75, rel=1e-12)
        lateral_1, recharge_1, baseflow_1 = _saturated_flows(BF_0, TU_S_0)  # S31, S32, S33
        discharge_1 = runoff_1 + lateral_1 + baseflow_1  # S34
        routed_1 = _routed_discharge_at_the_pit(discharge_1, DAYS_1)  # S35

        # Step 2: the cap binds, and S3 carried TU_S,1 = TU_S,0 - BF_1 + REC_1.
        et_2 = min(ET_P_2 / KP_2, P_2)  # S28 with rule 4
        assert et_2 == pytest.approx(P_2, rel=1e-12)
        runoff_2 = max(P_2 - et_2, 0.0)  # S13 with rule 4
        assert runoff_2 == 0.0
        saturated_storage_1 = TU_S_0 - baseflow_1 + recharge_1  # S3
        lateral_2, recharge_2, baseflow_2 = _saturated_flows(baseflow_1, saturated_storage_1)
        discharge_2 = runoff_2 + lateral_2 + baseflow_2  # S34
        routed_2 = _routed_discharge_at_the_pit(discharge_2, DAYS_2, routed_1)  # S35

        expected = {
            1: {
                "itp": 0.0,  # S14 with alpha_V = 0
                "bfw": baseflow_1,
                "srn": runoff_1,
                "eta": et_1,  # S21 with alpha_W = 1
                "lfw": lateral_1,
                "rec": recharge_1,
                "smc": TU_SAT,  # rule 2
                "rnf": discharge_1,
            },
            2: {
                "itp": 0.0,
                "bfw": baseflow_2,
                "srn": runoff_2,
                "eta": et_2,
                "lfw": lateral_2,
                "rec": recharge_2,
                "smc": TU_SAT,
                "rnf": discharge_2,
            },
        }
        for step, values in expected.items():
            model_outputs = paired[step][0]
            for variable, value in values.items():
                np.testing.assert_allclose(
                    model_outputs[variable],
                    value,
                    rtol=RTOL,
                    atol=ATOL,
                    err_msg=(
                        f"open water step {step}: {variable} differs from"
                        " the closed-form evaluation"
                    ),
                )
        assert paired[1][0]["arn"][PIT] == pytest.approx(routed_1, rel=RTOL)
        assert paired[2][0]["arn"][PIT] == pytest.approx(routed_2, rel=RTOL)

    @pytest.mark.paper
    @pytest.mark.integration
    @pytest.mark.parametrize("step", STEPS)
    @pytest.mark.parametrize("variable", reference.OUTPUT_VARIABLES)
    def test_the_open_water_run_matches_the_reference(
        self, open_water_model_and_reference, step, variable
    ):
        """Supplement S1 to S35, PDF pages 5 to 12, on the open-water dataset.

        Both steps evaluate S13, S28 and rules 2 and 4 on a water cell, on
        either side of the ``min(ET_P / kp, P_m)`` cap, and step 2 starts from
        the ``TU_SAT`` that rule 2 pinned, so the recursion is compared as well.
        """
        _, paired = open_water_model_and_reference
        model_outputs, reference_outputs, _ = paired[step]
        np.testing.assert_allclose(
            model_outputs[variable],
            reference_outputs[variable],
            rtol=RTOL,
            atol=ATOL,
            err_msg=f"open water step {step}: {variable} differs from the reference",
        )


class TestThresholdReferenceStep:
    """The same comparison on a dataset that reaches the threshold branches of S24 and S33."""

    @pytest.mark.paper
    @pytest.mark.integration
    def test_both_steps_match_values_derived_from_the_printed_formulas(
        self, threshold_model_and_reference
    ):
        """Supplement S24 (PDF page 9) and S33 (PDF page 11) with the #325 correction.

        With ``NDVI_min = 0.52`` the NDVI of step 1 (0.55) satisfies
        ``NDVI <= 1.1 NDVI_min = 0.572``, so S24 replaces the S23 interpolation
        by ``kc = kc_min = 1.14``. With ``BF_0 = 100 mm`` the recession of S33 at
        step 1 reaches ``100 exp(-0.5) + (1 - exp(-0.5)) 19.145 = 68.19 mm``,
        far above the ``TU_S,0 + REC = 20.245 mm`` the saturated zone holds, so
        the cap of the #325 correction binds; S3 then leaves ``TU_S,1 = 0``,
        which is below ``BF_thresh = 1 mm``, and step 2 takes the zero branch
        of S33.
        """
        config, paired = threshold_model_and_reference
        assert config["INITIAL_SOIL_CONDITIONS"]["bfw_ini"] == BF_0_HIGH
        assert NDVI_1 <= 1.1 * NDVI_MIN_HIGH, "step 1 must fall on the kc_min side of S24"
        model_1, model_2 = paired[1][0], paired[2][0]
        _assert_the_grid_drains_to_the_pit(paired[1][2].ldd)

        interception = _interception_of_step_1(1.0, ndvi_min=NDVI_MIN_HIGH)  # S14
        surface_runoff = P_1 - interception  # S4 with rule 3, since TU_R,0 = TU_SAT
        lateral_flow, recharge, baseflow = _saturated_flows(BF_0_HIGH, TU_S_0)
        # The recession of S33 is cut down to the water of the saturated zone.
        assert baseflow == pytest.approx(TU_S_0 + recharge, rel=1e-12)
        assert baseflow < BF_0_HIGH * exp(-ALPHA_GW) + (1.0 - exp(-ALPHA_GW)) * recharge
        # S22 with S24: kc = kc_min, and ks of S26 at TU_R = TU_SAT.
        water_stress = log(TU_SAT - TU_PM + 1.0) / log(TU_CC - TU_PM + 1.0)
        evapotranspiration = ET_P_1 * KC_MIN_1 * water_stress
        soil_moisture = TU_SAT - lateral_flow - recharge - evapotranspiration  # S1 and S2
        total_discharge = surface_runoff + lateral_flow + baseflow  # S34

        expected_1 = {
            "itp": interception,
            "bfw": baseflow,
            "srn": surface_runoff,
            "eta": evapotranspiration,
            "lfw": lateral_flow,
            "rec": recharge,
            "smc": soil_moisture,
            "rnf": total_discharge,
        }
        for variable, value in expected_1.items():
            np.testing.assert_allclose(
                model_1[variable],
                value,
                rtol=RTOL,
                atol=ATOL,
                err_msg=f"threshold step 1: {variable} differs from the closed-form evaluation",
            )
        assert model_1["arn"][PIT] == pytest.approx(
            _routed_discharge_at_the_pit(total_discharge, DAYS_1), rel=RTOL
        )

        # S3 empties the saturated zone, so S33 gives no baseflow at step 2.
        assert TU_S_0 - baseflow + recharge == pytest.approx(0.0, abs=1e-12)
        np.testing.assert_allclose(model_2["bfw"], 0.0, atol=ATOL)

    @pytest.mark.paper
    @pytest.mark.integration
    @pytest.mark.parametrize("step", STEPS)
    @pytest.mark.parametrize("variable", reference.OUTPUT_VARIABLES)
    def test_the_threshold_run_matches_the_reference(
        self, threshold_model_and_reference, step, variable
    ):
        """Supplement S1 to S35, PDF pages 5 to 12, on the threshold dataset.

        Step 1 takes the ``kc_min`` branch of S24 and the cap of the #325
        correction on S33; step 2 interpolates ``kc`` with S23 again and takes
        the zero branch of S33 on the saturated zone the cap emptied.
        """
        _, paired = threshold_model_and_reference
        model_outputs, reference_outputs, _ = paired[step]
        np.testing.assert_allclose(
            model_outputs[variable],
            reference_outputs[variable],
            rtol=RTOL,
            atol=ATOL,
            err_msg=f"threshold step {step}: {variable} differs from the reference",
        )
