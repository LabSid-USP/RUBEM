"""Independent float64 reference of one monthly step of the published formulation.

Every expression below is transcribed from the printed equations S1 to S35 of
the journal supplement (PDF pages 5 to 12) and from the model rules confirmed
in https://github.com/LabSid-USP/RUBEM/issues/331. The module is deliberately
kept free of any import from the model package: it exists so that the tests
can compare the model outputs with an evaluation of the formulas that shares
no code with them.

Reading of the step, forced by S1 and S3: every flux of month ``t`` that
depends on the root zone moisture (``C_h`` S10, ``ks`` S26, ``LF`` S31, ``REC``
S32) is evaluated with ``TU_R,t-1``, and the baseflow threshold of S33 and the
cap of the #325 correction use ``TU_S,t-1``, since ``TU_S,t`` itself depends on
the baseflow of the month. The state is then updated with S1 and S3.

The only PCRaster use is the LDD accumulation of S35 (``pcr.accuflux``), which
is not a supplement equation; the caller must have set the clone of the grid
before calling :func:`step`. The drain directions are whatever the run routes
on: the configured LDD raster when the configuration names one, and otherwise
the ``lddcreate(dem, 1e31, 1e31, 1e31, 1e31)`` of the model initialization.
"""

from dataclasses import dataclass

import numpy as np
import pcraster as pcr

OUTPUT_VARIABLES = ("itp", "bfw", "srn", "eta", "lfw", "rec", "smc", "rnf", "arn")


@dataclass(frozen=True)
class Parameters:
    """Calibration parameters and constants of the run (config names in comments)."""

    alpha: float  # interception parameter (S17)
    b: float  # soil moisture exponent (S10)
    w1: float  # cover weight (S9)
    w2: float  # soil weight (S9)
    w3: float  # slope weight (S9)
    rcd: float  # regional consecutive dryness factor [mm] (S5)
    f: float  # vertical/horizontal partitioning coefficient (S31, S32)
    alpha_gw: float  # baseflow decay coefficient (S33)
    x: float  # damping coefficient (S35)
    fpar_min: float  # FPAR_min (S19)
    fpar_max: float  # FPAR_max (S18, S19)
    lai_max: float  # LAI_max (S18)
    i_imp: float  # impervious-area interception, 1 to 3 mm (S30, rule 5)
    baseflow_threshold: float  # BF_thresh [mm] (S33)
    cell_area: float  # A [m2] (S35)


@dataclass(frozen=True)
class Tables:
    """Lookup tables, one ``{class: value}`` dict per attribute."""

    a_v: dict  # vegetated fraction (S14, S21)
    a_s: dict  # bare soil fraction (S21)
    a_o: dict  # open water fraction alpha_W (S8, S13, S21)
    a_i: dict  # impervious fraction alpha_I (S8, S21)
    manning: dict  # Manning roughness n (S9)
    kc_min: dict  # kc_min (S23 to S25)
    kc_max: dict  # kc_max (S23)
    dg: dict  # bulk density [g cm-3] (S11)
    zr: dict  # root layer thickness [cm] (S11)
    t_sat: dict  # volumetric porosity theta_POR (S10, S12)
    t_wp: dict  # volumetric wilting point theta_PM (S9, S26)
    t_fcap: dict  # volumetric field capacity (S26)
    k_r: dict  # root zone hydraulic conductivity K_R [mm month-1] (S31, S32)


@dataclass(frozen=True)
class State:
    """State carried between months: TU_R,t-1, TU_S,t-1, BF_t-1 and Q_t-1."""

    tu_r: np.ndarray  # root zone moisture [mm]
    tu_s: np.ndarray  # saturated zone moisture [mm]
    bf: np.ndarray  # baseflow [mm]
    q_prev: np.ndarray  # routed discharge Q_t-1 [m3 s-1]


@dataclass(frozen=True)
class Inputs:
    """Rasters of the month plus the static rasters of the grid."""

    p: np.ndarray  # P_m, total monthly precipitation [mm]
    et_p: np.ndarray  # ET_P, potential evapotranspiration [mm]
    kp: np.ndarray  # water evaporation coefficient (S28); S29 is not evaluated
    ndvi: np.ndarray  # NDVI of the month (S20, S23)
    ndvi_min: np.ndarray  # NDVI_min (S19 through RS_min, S23, S24)
    ndvi_max: np.ndarray  # NDVI_max (S19 through RS_max, S23)
    landuse: np.ndarray  # land use class raster (integer)
    soil: np.ndarray  # soil class raster (integer)
    # S of S9: slope as pcr.slope(dem) returns it; the unit question is open,
    # since S9 prints S as a percentage while pcr.slope returns a rise over run.
    slope: np.ndarray
    ldd: np.ndarray  # local drain direction codes of ``pcr.lddcreate`` (uint8)
    rainy_days: float  # d_P (S16) and the denominator of P_MD (S5)
    days_in_month: float  # days of the month (S35)


def lookup(table: dict, classes: np.ndarray) -> np.ndarray:
    """Map a class raster through a ``{class: value}`` table in float64.

    A class the table does not list stays ``nan``, so a missing entry surfaces
    as a failure instead of as an arbitrary number.
    """
    out = np.full(classes.shape, np.nan, dtype=np.float64)
    for cls, value in table.items():
        out[classes == cls] = value
    return out


def saturation_mm(tables: Tables, soil: np.ndarray) -> np.ndarray:
    """Return TU_SAT [mm], the S11 conversion ``theta_POR * d_g * Z_r * 10``.

    :func:`step` uses this very function, so a caller that builds an initial
    ``TU_R = t_ini * TU_SAT`` with it obtains a value that compares exactly with
    the ``TU_SAT`` of the step; the saturation rule of S4 (rule 3 of issue 331)
    turns on an equality, and a different order of the same products could
    differ by one unit in the last place.
    """
    return lookup(tables.t_sat, soil) * (lookup(tables.dg, soil) * lookup(tables.zr, soil) * 10.0)


def accumulate_along_ldd(ldd: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Accumulate ``values`` downstream over the LDD (the aggregation of S35).

    A PCRaster scalar field is REAL4, so the accumulation costs one Float32
    rounding of each term; that is about 1e-7 in relative terms, orders of
    magnitude below the tolerance any comparison with the model can use.
    """
    ldd_field = pcr.numpy2pcr(pcr.Ldd, np.asarray(ldd, dtype=np.uint8), 0)
    value_field = pcr.numpy2pcr(pcr.Scalar, np.asarray(values, dtype=np.float32), -9999.0)
    return pcr.pcr2numpy(pcr.accuflux(ldd_field, value_field), np.nan).astype(np.float64)


def step(inputs: Inputs, tables: Tables, params: Parameters, state: State) -> tuple[dict, State]:
    """Evaluate one month of S1 to S35 and return ``(outputs, new_state)``.

    ``outputs`` maps the nine model output names (``itp``, ``bfw``, ``srn``,
    ``eta``, ``lfw``, ``rec``, ``smc``, ``rnf``, ``arn``) to float64 arrays.
    """
    p = np.asarray(inputs.p, dtype=np.float64)
    et_p = np.asarray(inputs.et_p, dtype=np.float64)
    kp = np.asarray(inputs.kp, dtype=np.float64)
    ndvi = np.asarray(inputs.ndvi, dtype=np.float64)
    ndvi_min = np.asarray(inputs.ndvi_min, dtype=np.float64)
    ndvi_max = np.asarray(inputs.ndvi_max, dtype=np.float64)
    slope = np.asarray(inputs.slope, dtype=np.float64)
    tu_r_prev = np.asarray(state.tu_r, dtype=np.float64)
    tu_s_prev = np.asarray(state.tu_s, dtype=np.float64)
    bf_prev = np.asarray(state.bf, dtype=np.float64)
    q_prev = np.asarray(state.q_prev, dtype=np.float64)

    # Land use attributes (Table S1 columns and the crop coefficient bounds).
    a_v = lookup(tables.a_v, inputs.landuse)
    a_s = lookup(tables.a_s, inputs.landuse)
    a_w = lookup(tables.a_o, inputs.landuse)
    a_i = lookup(tables.a_i, inputs.landuse)
    n_manning = lookup(tables.manning, inputs.landuse)
    kc_min = lookup(tables.kc_min, inputs.landuse)
    kc_max = lookup(tables.kc_max, inputs.landuse)

    # Soil attributes and the volumetric-to-mm conversion d_g * Z_r * 10 (S11).
    dg = lookup(tables.dg, inputs.soil)
    zr = lookup(tables.zr, inputs.soil)
    theta_por = lookup(tables.t_sat, inputs.soil)
    theta_pm = lookup(tables.t_wp, inputs.soil)
    theta_cc = lookup(tables.t_fcap, inputs.soil)
    k_r = lookup(tables.k_r, inputs.soil)
    mm_per_unit = dg * zr * 10.0  # S11 denominator
    tu_sat = saturation_mm(tables, inputs.soil)  # TU_SAT [mm] (S31, S32), theta_POR * S11
    tu_pm = theta_pm * mm_per_unit  # TU_PM [mm] (S26, S27)
    tu_cc = theta_cc * mm_per_unit  # TU_CC [mm] (S26)

    # --- Interception, S14 to S20 (PDF page 8) ---
    rs = (1.0 + ndvi) / (1.0 - ndvi)  # S20
    rs_min = (1.0 + ndvi_min) / (1.0 - ndvi_min)  # S20 applied to NDVI_min
    rs_max = (1.0 + ndvi_max) / (1.0 - ndvi_max)  # S20 applied to NDVI_max
    # S19: the printed literal 0.95 is the stated value of FPAR_max (where-list of
    # S19), so the parameter is used in its place.
    fpar = np.minimum(
        (rs - rs_min) * (params.fpar_max - params.fpar_min) / (rs_max - rs_min) + params.fpar_min,
        params.fpar_max,
    )
    lai = params.lai_max * np.log(1.0 - fpar) / np.log(1.0 - params.fpar_max)  # S18
    i_d = (
        params.alpha
        * lai
        * (1.0 - 1.0 / (1.0 + p * (1.0 - np.exp(-0.463 * lai)) / (params.alpha * lai)))
    )  # S17
    # S16 with the #323 correction: the denominator is P_m itself whenever P_m != 0
    # and 1e-5 only when P_m == 0.
    p_den = np.where(p != 0.0, p, 1e-5)
    i_r = 1.0 - np.exp(-i_d * inputs.rainy_days / p_den)  # S16
    i_v = p * i_r  # S15
    interception = a_v * i_v  # S14

    # --- Evapotranspiration, S21 to S30 (PDF pages 9 and 10) ---
    kc_interp = kc_min + (kc_max - kc_min) * ((ndvi - ndvi_min) / (ndvi_max - ndvi_min))  # S23
    kc = np.where(ndvi <= 1.1 * ndvi_min, kc_min, kc_interp)  # S24 (#324)
    ks = np.where(
        tu_r_prev < tu_pm,
        0.0,  # S27
        np.log(np.maximum(tu_r_prev - tu_pm, 0.0) + 1.0) / np.log(tu_cc - tu_pm + 1.0),  # S26
    )
    et_r_v = et_p * kc * ks  # S22
    et_r_s = et_p * kc_min * ks  # S25
    # S28 with rule 4: on a cell fully covered by water, ET_R,W = min(ET_P / kp, P_m).
    et_r_w = np.where(a_w == 1.0, np.minimum(et_p / kp, p), et_p / kp)
    # S30 with rule 5: ET_R,I is the constant i_imp (1 to 3 mm) when P_m != 0, else 0.
    et_r_i = np.where(p != 0.0, params.i_imp, 0.0)
    et_real = a_v * et_r_v + a_s * et_r_s + a_w * et_r_w + a_i * et_r_i  # S21

    # --- Surface runoff, S4 to S13 (PDF pages 6 and 7) ---
    a_imp = a_w + a_i  # S8
    c_imp = 0.09 * np.exp(2.4 * a_imp)  # S7
    c_per = (
        params.w1 * (0.02 / n_manning)
        + params.w2 * (theta_pm / (1.0 - theta_pm))
        + params.w3 * (slope / (10.0 + slope))
    )  # S9
    c_wp = (1.0 - a_imp) * c_per + a_imp * c_imp  # S6
    p_md = p / inputs.rainy_days  # average daily rain on rainy days (S5)
    c_sr = (c_wp * p_md) / (c_wp * p_md - params.rcd * c_wp + params.rcd)  # S5
    theta_tur = np.minimum(tu_r_prev / mm_per_unit, theta_por)  # S11, S12
    c_h = (theta_tur / theta_por) ** params.b  # S10 (#321: both terms in mm-equivalent)
    sr = c_sr * c_h * (p - interception)  # S4
    # Rule 3: a saturated root zone (TU_R = TU_SAT) yields SR = P_m - I.
    sr = np.where(tu_r_prev == tu_sat, p - interception, sr)
    # S13 with rule 4: on a cell fully covered by water, SR = max(P_m - ET_R,W, 0).
    sr = np.where(a_w == 1.0, np.maximum(p - et_r_w, 0.0), sr)

    # --- Lateral flow and recharge, S31 and S32 (PDF page 11) ---
    lf = params.f * k_r * (tu_r_prev / tu_sat) ** 2  # S31
    rec = (1.0 - params.f) * k_r * (tu_r_prev / tu_sat) ** 2  # S32

    # --- Baseflow, S33 (PDF page 11) ---
    decay = np.exp(-params.alpha_gw)
    bf_recession = bf_prev * decay + (1.0 - decay) * rec  # S33, TU_S > BF_thresh branch
    bf = np.where(tu_s_prev > params.baseflow_threshold, bf_recession, 0.0)  # S33
    bf = np.minimum(bf, tu_s_prev + rec)  # #325: BF = min(recession, TU_S,t-1 + REC)

    # --- Water balance, S1 to S3 (PDF page 5) ---
    p_e = p - interception  # S2
    tu_r = tu_r_prev + p_e - sr - lf - rec - et_real  # S1
    tu_r = np.maximum(tu_r, 0.0)  # rule 1: floor at 0
    tu_r = np.minimum(tu_r, tu_sat)  # rule 1 / S12: upper clamp at TU_SAT
    tu_r = np.where(a_w == 1.0, tu_sat, tu_r)  # rule 2: open water cells stay saturated
    tu_s = tu_s_prev - bf + rec  # S3

    # --- Total discharge, S34 and S35 (PDF page 12) ---
    q_tot = sr + lf + bf  # S34 [mm]
    seconds = inputs.days_in_month * 24.0 * 3600.0  # S35 denominator
    q_cell = 0.001 * params.cell_area * q_tot / seconds  # S35 per-cell volume [m3 s-1]
    q_t = params.x * q_prev + (1.0 - params.x) * accumulate_along_ldd(inputs.ldd, q_cell)  # S35

    outputs = {
        "itp": interception,
        "bfw": bf,
        "srn": sr,
        "eta": et_real,
        "lfw": lf,
        "rec": rec,
        "smc": tu_r,
        "rnf": q_tot,
        "arn": q_t,
    }
    return outputs, State(tu_r=tu_r, tu_s=tu_s, bf=bf, q_prev=q_t)
