"""Conformity of the inline rules of the dynamic section with the published formulation.

The equations the model applies inline (total discharge, its routing and damping,
and the crop coefficient threshold that selects the vegetated evapotranspiration)
are checked on full runs of the synthetic 3x3 dataset. Every expectation is an
independent float64 evaluation of the printed formula on the raster values the
model read, never of the model code; the outputs are Float32 rasters, so each
comparison carries an explicit tolerance.
"""

import math

import numpy as np
import pcraster as pcr
import pytest

from tests.helpers.synthetic import (
    _LULC_TABLES,
    _SOIL_TABLES,
    CELL_SIZE,
    COLS,
    MISSING,
    ROWS,
    series_name,
    write_synthetic_dataset,
)
from tests.unit.core.test_core import run_model

# Calendar length of the simulated months, as printed in S35 (``days``): the
# synthetic series starts in January 2000 and February 2000 belongs to a leap year.
DAYS_IN_MONTH = {1: 31, 2: 29}
SECONDS_PER_DAY = 24 * 3600
CELL_AREA = CELL_SIZE * CELL_SIZE


def _read_output(config, variable, step):
    """Return the Float32 output raster of ``variable`` at ``step`` as float64."""
    pcr.setclone(config["RASTERS"]["clone"])
    path = f"{config['DIRECTORIES']['output']}/{series_name(variable, step)}"
    return pcr.pcr2numpy(pcr.readmap(path), np.nan).astype(np.float64)


def _read_input(config, path):
    """Return an input raster of the dataset as float64 on the synthetic clone."""
    pcr.setclone(config["RASTERS"]["clone"])
    return pcr.pcr2numpy(pcr.readmap(path), np.nan).astype(np.float64)


def _ldd_codes_from_dem(config):
    """Build the local drain direction the model builds in ``initial()``.

    When no LDD raster is configured the model derives it from the DEM with
    ``lddcreate(dem, 1e31, 1e31, 1e31, 1e31)``; the same call on the same DEM
    reproduces it. The codes follow the PCRaster keypad convention (1 to 9, 5 is
    a pit).
    """
    pcr.setclone(config["RASTERS"]["clone"])
    dem = pcr.readmap(config["RASTERS"]["dem"])
    ldd = pcr.lddcreate(dem, 1e31, 1e31, 1e31, 1e31)
    return pcr.pcr2numpy(ldd, 0).astype(np.int64)


# Row and column offsets of the PCRaster keypad drain codes (5 is a pit).
_LDD_OFFSETS = {
    1: (1, -1),
    2: (1, 0),
    3: (1, 1),
    4: (0, -1),
    6: (0, 1),
    7: (-1, -1),
    8: (-1, 0),
    9: (-1, 1),
}


def _accumulate(ldd_codes, values):
    """Sum ``values`` over the upstream area of every cell, the pit included.

    This is the flow accumulation the supplement describes in words ("an
    aggregate result according to the LDD"): each cell contributes its own value
    to itself and to every cell downstream of it along the drain directions.
    """
    rows, cols = ldd_codes.shape
    accumulated = np.zeros_like(values, dtype=np.float64)
    for row in range(rows):
        for col in range(cols):
            value = values[row, col]
            current = (row, col)
            visited = set()
            while current not in visited:
                visited.add(current)
                accumulated[current] += value
                code = int(ldd_codes[current])
                if code == 5:
                    break
                d_row, d_col = _LDD_OFFSETS[code]
                current = (current[0] + d_row, current[1] + d_col)
                # A negative index would silently wrap around the grid instead of
                # reporting a drain direction that leaves the map.
                assert 0 <= current[0] < rows and 0 <= current[1] < cols, (
                    f"cell {(row, col)} drains off the grid through {current}"
                )
    return accumulated


def _cell_volumes(discharge_mm, days):
    """S35 conversion of a cell discharge from mm to m3/s: 0.001 * A * Q_Tot / (days * 24 * 3600)."""
    return 0.001 * CELL_AREA * discharge_mm / (days * SECONDS_PER_DAY)


class TestTotalDischarge:
    @pytest.mark.paper
    @pytest.mark.integration
    def test_s34_total_discharge_is_the_sum_of_the_three_flows(self, tmp_path):
        """Supplement S34, PDF page 12: Q_Tot = SR + LF + BF on every cell of every step.

        The three flow rasters and the total are Float32 outputs of the same
        step, so the total carries the two Float32 roundings of ``(SR + LF) + BF``
        (at most ``2 * 2 ** -24``, about ``1.2e-7`` in relative terms):
        ``rtol=1e-6`` is about ten times that and still an order of magnitude
        below any dropped or duplicated term.
        """
        config = run_model(str(tmp_path))

        for step in (1, 2):
            surface_runoff = _read_output(config, "srn", step)
            lateral_flow = _read_output(config, "lfw", step)
            baseflow = _read_output(config, "bfw", step)
            total = _read_output(config, "rnf", step)
            expected = surface_runoff + lateral_flow + baseflow

            assert np.isfinite(total).all(), f"step {step}: total discharge has missing cells"
            assert expected.min() > 0.0, f"step {step}: the sum must be a non-trivial flow"
            np.testing.assert_allclose(
                total,
                expected,
                rtol=1e-6,
                atol=0.0,
                err_msg=f"step {step}: rnf differs from srn + lfw + bfw",
            )


class TestRoutedDischarge:
    @pytest.mark.paper
    @pytest.mark.integration
    def test_s35_without_damping_routes_the_converted_cell_volumes(self, tmp_path):
        """Supplement S35, PDF page 12, with x = 0: Q_t = accuflux(LDD, 0.001 A Q_Tot / (days 24 3600)).

        As printed, S35 converts the cell total ``Q_Tot`` (mm) into m3/s with the
        cell area ``A`` and the seconds of the month; the text above it states
        that the total flow "is computed using an aggregate result according to
        the LDD". With ``x = 0`` the damping term vanishes and the routed flow of
        every cell must equal the accumulation of the converted volumes of its
        upstream cells. The LDD is left unset so that ``initial()`` derives it
        from the DEM; the test rebuilds it with the same ``lddcreate`` call and
        accumulates the volumes itself. Float32 conversions and sums of at most
        nine terms stay well inside ``rtol=1e-5``; a wrong number of days
        would miss January by 6.9%, a missing accumulation the pit by a
        factor of about nine.
        """
        config = write_synthetic_dataset(str(tmp_path))
        config["CALIBRATION"]["x"] = 0.0
        config["RASTERS"]["ldd"] = None
        run_model(str(tmp_path), config=config)
        ldd_codes = _ldd_codes_from_dem(config)

        for step, month in ((1, 1), (2, 2)):
            volumes = _cell_volumes(_read_output(config, "rnf", step), DAYS_IN_MONTH[month])
            expected = _accumulate(ldd_codes, volumes)
            routed = _read_output(config, "arn", step)

            np.testing.assert_allclose(
                routed,
                expected,
                rtol=1e-5,
                atol=0.0,
                err_msg=f"step {step}: arn differs from the accumulated cell volumes",
            )

        # The DEM rises from the upper-left corner, so that corner is the only pit
        # and drains the whole grid: its routed flow is the sum of all nine
        # converted volumes, whatever the drain directions in between.
        assert int(ldd_codes[0, 0]) == 5
        assert np.count_nonzero(ldd_codes == 5) == 1
        volumes_step_1 = _cell_volumes(_read_output(config, "rnf", 1), DAYS_IN_MONTH[1])
        assert _read_output(config, "arn", 1)[0, 0] == pytest.approx(
            float(volumes_step_1.sum()), rel=1e-5
        )

    @pytest.mark.paper
    @pytest.mark.integration
    def test_s35_damping_blends_the_previous_flow_with_the_routed_volumes(self, tmp_path):
        """Supplement S35, PDF page 12, with x = 0.3: Q_t = x Q_(t-1) + (1 - x) accuflux(...).

        ``initial()`` sets the previous cell total flow to a zero scalar, so at
        step 1 the routed flow is ``(1 - x)`` times the accumulated volumes of
        January (31 days). At step 2 the previous flow is the step-1 output and
        the volumes use the 29 days of February 2000. One multiplication and one
        addition in Float32 on top of the routing: ``rtol=1e-5``.
        """
        damping = 0.3
        config = write_synthetic_dataset(str(tmp_path))
        config["CALIBRATION"]["x"] = damping
        config["RASTERS"]["ldd"] = None
        run_model(str(tmp_path), config=config)
        ldd_codes = _ldd_codes_from_dem(config)

        routed_1 = _accumulate(
            ldd_codes, _cell_volumes(_read_output(config, "rnf", 1), DAYS_IN_MONTH[1])
        )
        expected_1 = damping * 0.0 + (1.0 - damping) * routed_1
        flow_1 = _read_output(config, "arn", 1)
        np.testing.assert_allclose(
            flow_1,
            expected_1,
            rtol=1e-5,
            atol=0.0,
            err_msg="step 1: arn differs from (1 - x) times the routed volumes",
        )

        routed_2 = _accumulate(
            ldd_codes, _cell_volumes(_read_output(config, "rnf", 2), DAYS_IN_MONTH[2])
        )
        expected_2 = damping * flow_1 + (1.0 - damping) * routed_2
        flow_2 = _read_output(config, "arn", 2)
        np.testing.assert_allclose(
            flow_2,
            expected_2,
            rtol=1e-5,
            atol=0.0,
            err_msg="step 2: arn differs from x arn(1) + (1 - x) times the routed volumes",
        )
        # The damping term must weigh: the step-2 flow is neither the undamped
        # routing of the step nor a mere repetition of the step-1 flow.
        assert not np.allclose(flow_2, routed_2, rtol=1e-3, atol=0.0)
        assert not np.allclose(flow_2, flow_1, rtol=1e-3, atol=0.0)


class TestCropCoefficientThreshold:
    @pytest.mark.paper
    @pytest.mark.integration
    def test_s24_ndvi_at_the_threshold_uses_kc_min_and_above_it_interpolates(self, tmp_path):
        """Supplement S24 and S23, PDF page 9: kc = kc_min if NDVI <= 1.1 NDVI_min, else S23.

        Corrected in https://github.com/LabSid-USP/RUBEM/issues/320: a cell whose
        NDVI is exactly ``1.1 NDVI_min`` takes ``kc_min``. PCRaster evaluates the
        product in Float32, so the cell receives ``float32(1.1) * float32(NDVI_min)``.
        At step 1 the land-use class of the dataset has ``a_v = 1`` and no other
        fraction, so the total evapotranspiration is ET_R,V = ET_P kc ks (S21,
        S22) with ks from S26 and S27 on the initial root-zone moisture
        TU_R(0) = t_ini TU_sat (S26 has no upper bound, so ks exceeds 1 when
        TU_R(0) > TU_CC, as here). The control cell keeps the NDVI of the series,
        clearly above the threshold, and must follow the S23 interpolation.
        Expectations are float64; the Float32 chain of the model has about a
        dozen operations and the logarithms compress the relative error, so
        ``rel=1e-5`` holds with margin.
        """
        threshold_cell = (0, 0)
        control_cell = (2, 2)
        config = write_synthetic_dataset(str(tmp_path))
        ndvi_path = f"{config['DIRECTORIES']['ndvi']}{series_name('ndvi', 1)}"
        ndvi_min = _read_input(config, config["RASTERS"]["ndvi_min"])
        ndvi_max = _read_input(config, config["RASTERS"]["ndvi_max"])
        ndvi = _read_input(config, ndvi_path).astype(np.float32)
        threshold = np.float32(1.1) * np.float32(ndvi_min[threshold_cell])
        ndvi[threshold_cell] = threshold
        assert ndvi[control_cell] > 1.1 * ndvi_min[control_cell]
        pcr.report(pcr.numpy2pcr(pcr.Scalar, ndvi, MISSING), ndvi_path)

        # Step 1 uses the land-use class the dataset writes first; its fractions
        # make the cell fully vegetated.
        landuse_path = f"{config['DIRECTORIES']['landuse']}{series_name('cob', 1)}"
        landuse = _read_input(config, landuse_path)
        assert landuse.shape == (ROWS, COLS)
        assert np.unique(landuse).tolist() == [3]
        assert _LULC_TABLES["a_v"][3] == 1.0
        assert _LULC_TABLES["a_i"][3] == _LULC_TABLES["a_o"][3] == _LULC_TABLES["a_s"][3] == 0.0
        kc_min = _LULC_TABLES["kcmin"][3]
        kc_max = _LULC_TABLES["kcmax"][3]

        potential_et = _read_input(config, f"{config['DIRECTORIES']['etp']}{series_name('etp', 1)}")

        run_model(str(tmp_path), config=config)
        actual_et = _read_output(config, "eta", 1)

        # Root-zone moisture contents in mm: theta * dg * Zr * 10 (S1 units).
        to_mm = _SOIL_TABLES["dg"] * _SOIL_TABLES["Zr"] * 10.0
        tu_sat = _SOIL_TABLES["Tsat"] * to_mm
        tu_wilting = _SOIL_TABLES["Tw"] * to_mm
        tu_field_capacity = _SOIL_TABLES["Tcc"] * to_mm
        tu_initial = config["INITIAL_SOIL_CONDITIONS"]["t_ini"] * tu_sat
        assert tu_initial >= tu_wilting, "S27 would zero ks; the test needs the S26 branch"
        ks = math.log(tu_initial - tu_wilting + 1.0) / math.log(
            tu_field_capacity - tu_wilting + 1.0
        )

        expected_threshold = float(potential_et[threshold_cell]) * kc_min * ks
        assert actual_et[threshold_cell] == pytest.approx(expected_threshold, rel=1e-5)

        ndvi_control = float(ndvi[control_cell])
        kc_control = kc_min + (kc_max - kc_min) * (
            (ndvi_control - ndvi_min[control_cell])
            / (ndvi_max[control_cell] - ndvi_min[control_cell])
        )
        expected_control = float(potential_et[control_cell]) * kc_control * ks
        assert kc_control > kc_min
        assert actual_et[control_cell] == pytest.approx(expected_control, rel=1e-5)
        # The interpolated cell must not collapse to the kc_min branch.
        assert actual_et[control_cell] != pytest.approx(
            float(potential_et[control_cell]) * kc_min * ks, rel=1e-3
        )
