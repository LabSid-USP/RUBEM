"""The MODFLOW groundwater module against a mocked PCRaster MODFLOW extension.

The inputs are real PCRaster maps on the 3x3 synthetic grid (pyfakefs cannot
back PCRaster I/O); the extension object is a :class:`unittest.mock.Mock`, so
the tests see every call the module makes and the numbers it passes. With the
three layers of :func:`write_modflow_inputs`, user layer 1 (the top) is
PCRaster layer 3 and user layer 3 (the base) is PCRaster layer 1.
"""

import math
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pcraster as pcr
import pytest

from rubem.configuration.modflow_configuration import ModflowSettings
from rubem.hydrological_processes import _modflow
from rubem.hydrological_processes._modflow import DRY_HEAD, ModflowGroundwater
from tests.helpers.synthetic import (
    CELL_SIZE,
    COLS,
    MODFLOW_HEAD,
    MODFLOW_KH_TABLE,
    ROWS,
    write_grid_map,
    write_modflow_inputs,
    write_synthetic_dataset,
)

pytestmark = pytest.mark.unit

NAN = math.nan
CELL_AREA = CELL_SIZE * CELL_SIZE
DAYS = 31
LEFT_COLUMN = [1.0 if index % COLS == 0 else 0.0 for index in range(ROWS * COLS)]
MIDDLE_COLUMN = [1.0 if index % COLS == 1 else 0.0 for index in range(ROWS * COLS)]


@pytest.fixture(name="section")
def section_fixture(tmp_path):
    """The MODFLOW section of :func:`write_modflow_inputs` (three layers)."""
    config = write_synthetic_dataset(str(tmp_path))
    return write_modflow_inputs(config)


@pytest.fixture(name="mf")
def mf_fixture():
    mf = Mock()
    mf.converged.return_value = True
    mf.getRiverLeakage.side_effect = lambda layer: pcr.spatial(pcr.scalar(-2.0))
    mf.getHeads.side_effect = lambda layer: pcr.spatial(pcr.scalar(float(layer)))
    mf.getStorage.side_effect = lambda layer: pcr.spatial(pcr.scalar(10.0 * layer))
    mf.getDrain.side_effect = lambda layer: pcr.spatial(pcr.scalar(-100.0))
    mf.getGeneralHeadLeakage.side_effect = lambda layer: pcr.spatial(pcr.scalar(-100.0))
    return mf


@pytest.fixture(name="extension")
def extension_fixture(monkeypatch, mf):
    """Replace the extension and the PATH lookup; records the order they are used in."""
    events = []

    def initialise(clone):
        events.append("initialise")
        return mf

    def ensure_mf2005_on_path():
        events.append("ensure_mf2005_on_path")
        return Path("mf2005")

    monkeypatch.setattr(_modflow, "_initialise", initialise)
    monkeypatch.setattr(_modflow, "ensure_mf2005_on_path", ensure_mf2005_on_path)
    return events


@pytest.fixture(name="run_dir")
def run_dir_fixture(tmp_path):
    return tmp_path / "run" / "modflow"


def build(section, run_dir, days=DAYS, area=CELL_AREA):
    model = ModflowGroundwater(ModflowSettings.model_validate(section), area, run_dir)
    model.initialize(days)
    return model


def values(field):
    return pcr.pcr2numpy(pcr.scalar(field), np.nan)


def grid(values_):
    return np.asarray(values_, dtype=float).reshape(ROWS, COLS)


def calls(mf, name):
    return [item for item in mf.mock_calls if item[0] == name]


def layer_args(mf, name, pcraster_number, position=-1):
    """The arguments of the last ``name`` call for extension layer ``pcraster_number``."""
    matching = [item.args for item in calls(mf, name) if item.args[position] == pcraster_number]
    assert matching, f"{name} was not called for layer {pcraster_number}"
    return matching[-1]


def rewrite(path, values_, nominal=False):
    write_grid_map(path, values_, nominal=nominal)


def give_layers_own_boundaries(section, active_in):
    """Cell (1, 1) active only in the layers ``active_in``, every other cell everywhere."""
    for number, layer in enumerate(section["layers"], start=1):
        layer["boundary"] = write_grid_map(
            Path(section["top"]).with_name(f"bound{number}.map"),
            [1 if index or number in active_in else 0 for index in range(9)],
            nominal=True,
        )


class TestConstruction:
    @pytest.mark.parametrize("area", [0.0, -1.0, math.nan, math.inf])
    def test_the_cell_area_must_be_finite_and_positive(self, section, run_dir, area):
        settings = ModflowSettings.model_validate(section)
        with pytest.raises(ValueError, match="cell area"):
            ModflowGroundwater(settings, area, run_dir)

    def test_a_disabled_section_is_refused(self, run_dir):
        with pytest.raises(ValueError, match="not enabled"):
            ModflowGroundwater(ModflowSettings(), CELL_AREA, run_dir)


@pytest.mark.usefixtures("extension")
class TestInitialize:
    def test_the_packages_are_set_dis_bas_bcf_wetting_solver_stress(self, section, run_dir, mf):
        groups = {
            "createBottomLayer": 0,
            "addLayer": 0,
            "setRowWidth": 0,
            "setColumnWidth": 0,
            "setDISParameter": 0,
            "setBoundary": 1,
            "setInitialHead": 1,
            "setDryHead": 2,
            "setConductivity": 2,
            "setStorage": 2,
            "setWettingParameter": 3,
            "setWetting": 3,
            "setPCG": 4,
            "setRiver": 5,
            "setGeneralHead": 5,
            "setDrain": 5,
        }
        build(section, run_dir)
        ranks = [groups[item[0]] for item in mf.mock_calls]
        assert ranks == sorted(ranks)
        assert set(ranks) == set(range(6))

    def test_the_surfaces_reach_the_extension_from_the_bottom_up(self, section, run_dir, mf):
        build(section, run_dir)
        base, above_base = mf.createBottomLayer.call_args.args
        np.testing.assert_array_equal(values(base), np.full((ROWS, COLS), 40.0))
        np.testing.assert_array_equal(values(above_base), np.full((ROWS, COLS), 60.0))
        tops = [values(item.args[0]) for item in calls(mf, "addLayer")]
        np.testing.assert_array_equal(
            tops, [np.full((ROWS, COLS), 80.0), np.full((ROWS, COLS), 100.0)]
        )

    def test_columns_inactive_in_every_layer_get_synthetic_elevations(self, section, run_dir, mf):
        inactive_left = [
            NAN if index == 0 else 0.0 if index % COLS == 0 else 1.0 for index in range(9)
        ]
        rewrite(section["layers"][0]["boundary"], inactive_left, nominal=True)
        for number, layer in enumerate(section["layers"], start=1):
            rewrite(
                layer["bottom"],
                [NAN if index % COLS == 0 else 100.0 - 20.0 * number for index in range(9)],
            )
        rewrite(section["top"], [NAN if index % COLS == 0 else 100.0 for index in range(9)])
        build(section, run_dir)
        base, above_base = mf.createBottomLayer.call_args.args
        surfaces = [base, above_base] + [item.args[0] for item in calls(mf, "addLayer")]
        for index, surface in enumerate(surfaces):
            np.testing.assert_array_equal(values(surface)[:, 0], [float(index)] * ROWS)
            np.testing.assert_array_equal(
                values(surface)[:, 1:], np.full((ROWS, COLS - 1), 40.0 + 20.0 * index)
            )
        boundary = pcr.pcr2numpy(layer_args(mf, "setBoundary", 3)[0], -99)
        np.testing.assert_array_equal(boundary[:, 0], [0, 0, 0])

    def test_a_column_active_in_an_upper_layer_only_needs_every_elevation(
        self, section, run_dir, mf
    ):
        give_layers_own_boundaries(section, active_in={1})
        rewrite(section["layers"][2]["bottom"], [NAN if index == 0 else 40.0 for index in range(9)])
        with pytest.raises(ValueError, match=r"bottom of layer 3 \(layer3\).*row 1, column 1"):
            build(section, run_dir)
        mf.createBottomLayer.assert_not_called()

    def test_a_column_active_in_the_base_layer_only_keeps_its_elevations(
        self, section, run_dir, mf
    ):
        give_layers_own_boundaries(section, active_in={3})
        build(section, run_dir)
        base, above_base = mf.createBottomLayer.call_args.args
        surfaces = [base, above_base] + [item.args[0] for item in calls(mf, "addLayer")]
        assert [float(values(surface)[0, 0]) for surface in surfaces] == [40.0, 60.0, 80.0, 100.0]

    @pytest.mark.parametrize("surface", ["top", "bottom"])
    def test_a_missing_elevation_in_an_active_column_is_refused(
        self, section, run_dir, mf, surface
    ):
        path = section["top"] if surface == "top" else section["layers"][2]["bottom"]
        level = 100.0 if surface == "top" else 40.0
        rewrite(path, [NAN if index == 1 else level for index in range(9)])
        with pytest.raises(ValueError, match="row 1, column 2"):
            build(section, run_dir)
        mf.createBottomLayer.assert_not_called()

    def test_a_bottom_above_the_surface_over_it_is_refused(self, section, run_dir, mf):
        rewrite(
            section["layers"][1]["bottom"], [90.0 if index == 4 else 60.0 for index in range(9)]
        )
        with pytest.raises(ValueError, match="row 2, column 2"):
            build(section, run_dir)
        mf.createBottomLayer.assert_not_called()

    def test_user_layers_reach_the_extension_bottom_up(self, section, run_dir, mf):
        """The extension numbers the layers bottom up, and takes them in that order.

        It appends the LAYCON of each ``setConductivity`` call to the BCF file in
        call order, whatever layer number the call names: called top down, the
        top layer would get the LAYCON of the base.
        """
        build(section, run_dir)
        assert [item.args[-1] for item in calls(mf, "setBoundary")] == [1, 2, 3]
        assert [item.args[-1] for item in calls(mf, "setInitialHead")] == [1, 2, 3]
        assert [
            (item.args[0], item.args[3], item.args[4]) for item in calls(mf, "setConductivity")
        ] == [
            (2, 1, True),
            (2, 2, True),
            (1, 3, True),
        ]
        assert [item.args[-1] for item in calls(mf, "setStorage")] == [1, 2, 3]
        assert [item.args[-1] for item in calls(mf, "setWetting")] == [3]
        assert [item.args[-1] for item in calls(mf, "setRiver")] == [3]
        assert sorted(item.args[-1] for item in calls(mf, "setGeneralHead")) == [1, 2, 3]

    def test_the_initial_head_is_read_from_its_map(self, section, run_dir, mf):
        build(section, run_dir)
        head = layer_args(mf, "setInitialHead", 3)[0]
        np.testing.assert_array_equal(values(head), np.full((ROWS, COLS), MODFLOW_HEAD))

    def test_the_conductivity_classes_are_looked_up_in_the_table(self, section, run_dir, mf):
        build(section, run_dir)
        kh = layer_args(mf, "setConductivity", 3, position=3)[1]
        expected = [MODFLOW_KH_TABLE[1]] * COLS + [MODFLOW_KH_TABLE[2]] * (ROWS - 1) * COLS
        np.testing.assert_allclose(values(kh), grid(expected))

    def test_a_rewritten_table_is_read_again(self, section, run_dir, mf):
        build(section, run_dir)
        table = Path(section["layers"][0]["horizontal_conductivity"]["table"])
        table.write_text("1 2.0\n2 3.0\n", encoding="utf8")
        build(section, run_dir.parent / "second")
        kh = layer_args(mf, "setConductivity", 3, position=3)[1]
        np.testing.assert_allclose(values(kh), grid([2.0] * COLS + [3.0] * (ROWS - 1) * COLS))

    def test_a_number_is_spread_over_the_clone(self, section, run_dir, mf):
        build(section, run_dir)
        kv = layer_args(mf, "setConductivity", 2, position=3)[2]
        np.testing.assert_allclose(values(kv), np.full((ROWS, COLS), 0.1))

    def test_a_missing_property_on_an_active_cell_is_refused(self, section, run_dir, mf):
        rewrite(
            section["layers"][0]["initial_head"],
            [NAN if index == 5 else 90.0 for index in range(9)],
        )
        with pytest.raises(ValueError, match="row 2, column 3"):
            build(section, run_dir)

    def test_a_property_missing_only_on_inactive_cells_is_filled(self, section, run_dir, mf):
        rewrite(
            section["layers"][0]["boundary"],
            [0 if index == 5 else 1 for index in range(9)],
            nominal=True,
        )
        rewrite(
            section["layers"][0]["initial_head"],
            [NAN if index == 5 else 90.0 for index in range(9)],
        )
        build(section, run_dir)
        head = values(layer_args(mf, "setInitialHead", 3)[0])
        assert np.isfinite(head).all()

    def test_a_transient_run_sets_the_storage_of_each_layer_type(self, section, run_dir, mf):
        section["layers"][2]["laytype"] = 0
        build(section, run_dir)
        stored = [
            (float(values(item.args[0])[0, 0]), float(values(item.args[1])[0, 0]), item.args[2])
            for item in calls(mf, "setStorage")
        ]
        assert stored == [
            (pytest.approx(1e-5), pytest.approx(1e-5), 1),
            (pytest.approx(1e-5), pytest.approx(0.15), 2),
            (pytest.approx(0.15), pytest.approx(0.15), 3),
        ]

    def test_a_transient_run_starts_with_the_first_period(self, section, run_dir, mf):
        build(section, run_dir, days=28)
        mf.setDISParameter.assert_called_once_with(4, 2, 28.0, 1, 1.0, 0)

    def test_a_steady_run_sets_no_storage(self, section, run_dir, mf):
        section["dis"] = {"steady_state": True, "nstp": 2, "tsmult": 1.5}
        build(section, run_dir)
        mf.setDISParameter.assert_called_once_with(4, 2, 31.0, 2, 1.5, 1)
        mf.setStorage.assert_not_called()

    @pytest.mark.parametrize("area", [900.0, CELL_AREA])
    def test_the_cells_are_squares_of_the_grid_area_whatever_the_clone_units(
        self, section, run_dir, mf, area
    ):
        build(section, run_dir, area=area)
        width = math.sqrt(area)
        mf.setRowWidth.assert_called_once_with([width] * ROWS)
        mf.setColumnWidth.assert_called_once_with([width] * COLS)

    def test_the_solver_takes_the_configured_pcg_settings(self, section, run_dir, mf):
        section["solver"] = {"mxiter": 50, "hclose": 0.01, "damp": 1.0}
        build(section, run_dir)
        mf.setPCG.assert_called_once_with(50, 20, 1, 0.01, 3.0, 1.0, 2, 1.0)
        mf.setDryHead.assert_called_once_with(DRY_HEAD)

    def test_wetting_is_set_with_its_parameters_on_the_listed_layers(self, section, run_dir, mf):
        section["wetting"].update({"wetfct": 0.5, "iwetit": 2, "ihdwet": 1})
        build(section, run_dir)
        mf.setWettingParameter.assert_called_once_with(0.5, 2, 1)
        (wetdry, layer), _ = mf.setWetting.call_args
        assert layer == 3
        np.testing.assert_allclose(values(wetdry), np.full((ROWS, COLS), 1.0))

    def test_wetting_reaches_the_extension_bottom_up(self, section, run_dir, mf):
        section["layers"][1]["laytype"] = 3
        section["wetting"]["layers"] = [1, 2]
        build(section, run_dir)
        assert [item.args[-1] for item in calls(mf, "setWetting")] == [2, 3]

    def test_disabled_wetting_is_not_set(self, section, run_dir, mf):
        section["wetting"]["enabled"] = False
        build(section, run_dir)
        mf.setWettingParameter.assert_not_called()
        mf.setWetting.assert_not_called()

    def test_river_conductance_is_zero_outside_the_mask_and_the_boundary(
        self, section, run_dir, mf
    ):
        rewrite(
            section["layers"][0]["boundary"],
            [0 if index == 7 else 1 for index in range(9)],
            nominal=True,
        )
        build(section, run_dir)
        stage, bottom, conductance, layer = mf.setRiver.call_args.args
        expected = [10.0 if index in (1, 4) else 0.0 for index in range(9)]
        np.testing.assert_allclose(values(conductance), grid(expected))
        np.testing.assert_allclose(values(stage)[:2, 1], [95.0, 95.0])
        np.testing.assert_allclose(values(bottom)[:2, 1], [90.0, 90.0])

    def test_a_stress_map_needs_values_on_the_cells_of_the_package(self, section, run_dir, mf):
        rewrite(
            section["river"]["entries"][0]["stage"],
            [NAN if index == 1 else 95.0 for index in range(9)],
        )
        with pytest.raises(ValueError, match="row 1, column 2"):
            build(section, run_dir)

    def test_a_stress_map_is_filled_outside_the_cells_of_the_package(self, section, run_dir, mf):
        rewrite(
            section["river"]["entries"][0]["stage"],
            [95.0 if index % COLS == 1 else NAN for index in range(9)],
        )
        build(section, run_dir)
        assert np.isfinite(values(mf.setRiver.call_args.args[0])).all()

    def test_non_positive_conductance_is_not_a_package_cell(self, section, run_dir, mf):
        conductance = section["ghb"]["entries"][0]["conductance"]
        rewrite(
            conductance, [-1.0 if index == 3 else value for index, value in enumerate(LEFT_COLUMN)]
        )
        build(section, run_dir)
        ghb = values(mf.setGeneralHead.call_args_list[0].args[1])
        np.testing.assert_allclose(ghb[:, 0], [1.0, 0.0, 1.0])

    def test_a_package_layer_without_cells_is_not_set(self, section, run_dir, mf, caplog):
        empty = write_grid_map(Path(section["top"]).with_name("empty.map"), 0.0)
        head = section["ghb"]["entries"][0]["head"]
        section["ghb"]["entries"] = [
            {
                "layers": [1, 2],
                "head": head,
                "conductance": section["ghb"]["entries"][0]["conductance"],
            },
            {"layers": [3], "head": head, "conductance": empty},
        ]
        with caplog.at_level("WARNING"):
            build(section, run_dir)
        assert [item.args[-1] for item in calls(mf, "setGeneralHead")] == [3, 2]
        assert "ghb" in caplog.text and "layer 3 (layer3)" in caplog.text

    def test_the_extension_starts_after_mf2005_is_on_path(self, section, run_dir, extension):
        build(section, run_dir)
        assert extension == ["ensure_mf2005_on_path", "initialise"]

    def test_initialize_runs_once(self, section, run_dir):
        model = build(section, run_dir)
        with pytest.raises(RuntimeError, match="already initialized"):
            model.initialize(DAYS)

    def test_the_run_directory_is_created(self, section, run_dir):
        build(section, run_dir)
        assert run_dir.is_dir()


class TestRuntime:
    def test_a_missing_executable_is_reported_before_the_extension_starts(
        self, section, run_dir, monkeypatch
    ):
        started = []
        monkeypatch.setattr(_modflow, "ensure_mf2005_on_path", lambda: None)
        monkeypatch.setattr(_modflow, "_initialise", started.append)
        monkeypatch.setattr(_modflow, "missing_groundwater_deps", lambda: ["mf2005"])
        with pytest.raises(RuntimeError, match="MODFLOW-2005 executable"):
            build(section, run_dir)
        assert started == []

    def test_a_missing_extension_is_reported_with_the_installation_guidance(
        self, section, run_dir, monkeypatch
    ):
        monkeypatch.setattr(_modflow, "ensure_mf2005_on_path", lambda: Path("mf2005"))
        monkeypatch.delattr(pcr, "initialise", raising=False)
        monkeypatch.setattr(
            _modflow, "missing_groundwater_deps", lambda: ["pcraster._pcraster_modflow"]
        )
        with pytest.raises(RuntimeError, match=r"not found: pcraster\._pcraster_modflow"):
            build(section, run_dir)


@pytest.mark.usefixtures("extension")
class TestRunStep:
    def test_recharge_goes_to_the_highest_active_cell_in_metres_per_day(self, section, run_dir, mf):
        model = build(section, run_dir)
        recharge = pcr.numpy2pcr(pcr.Scalar, grid([NAN] + [31.0] * 8), np.nan)
        model.run_step(recharge, DAYS)
        field, option = mf.setRecharge.call_args.args
        assert option == 3
        np.testing.assert_allclose(values(field), grid([0.0] + [0.001] * 8))

    def test_each_transient_period_takes_its_length(self, section, run_dir, mf):
        model = build(section, run_dir)
        model.run_step(pcr.scalar(0.0), 28)
        mf.updateDISParameter.assert_called_once_with(28.0, 1, 1.0)

    def test_a_steady_run_keeps_its_period(self, section, run_dir, mf):
        section["dis"] = {"steady_state": True}
        model = build(section, run_dir)
        model.run_step(pcr.scalar(0.0), 28)
        mf.updateDISParameter.assert_not_called()

    def test_modflow_runs_in_the_run_directory(self, section, run_dir, mf):
        model = build(section, run_dir)
        model.run_step(pcr.scalar(0.0), DAYS)
        (directory,), _ = mf.run.call_args
        assert Path(directory) == run_dir

    def test_stress_packages_are_set_once_for_every_period(self, section, run_dir, mf):
        model = build(section, run_dir)
        for _ in range(2):
            model.run_step(pcr.scalar(0.0), DAYS)
        names = [item[0] for item in mf.mock_calls]
        assert names.count("setRiver") == 1
        assert names.count("setGeneralHead") == 3
        assert names.count("run") == 2
        assert max(
            index
            for index, name in enumerate(names)
            if name.startswith("set") and name != "setRecharge"
        ) < names.index("run")

    def test_a_period_that_does_not_converge_raises(self, section, run_dir, mf):
        mf.converged.side_effect = [True, False]
        model = build(section, run_dir)
        model.run_step(pcr.scalar(0.0), DAYS)
        with pytest.raises(RuntimeError, match="did not converge in stress period 2"):
            model.run_step(pcr.scalar(0.0), DAYS)

    def test_the_baseflow_is_the_aquifer_to_river_leakage_in_mm(self, section, run_dir, mf):
        leakage = grid([-2.0, 3.0, 0.0] * 3)
        mf.getRiverLeakage.side_effect = lambda layer: pcr.numpy2pcr(pcr.Scalar, leakage, np.nan)
        model = build(section, run_dir)
        result = model.run_step(pcr.scalar(0.0), DAYS)
        expected_mm = 2.0 * DAYS * 1000.0 / CELL_AREA
        np.testing.assert_allclose(values(result.baseflow_mm), grid([expected_mm, 0.0, 0.0] * 3))
        np.testing.assert_allclose(
            values(result.aquifer_to_river_m3_per_day), grid([2.0, 0.0, 0.0] * 3)
        )
        np.testing.assert_allclose(
            values(result.river_to_aquifer_m3_per_day), grid([0.0, 3.0, 0.0] * 3)
        )
        np.testing.assert_allclose(values(result.net_river_leakage_m3_per_day), leakage)
        assert [item.args for item in calls(mf, "getRiverLeakage")] == [(3,)]

    def test_general_head_and_drain_flows_never_reach_the_baseflow(self, section, run_dir, mf):
        section["drain"] = {
            "enabled": True,
            "entries": [
                {
                    "layers": [2],
                    "elevation": section["top"],
                    "conductance": section["ghb"]["entries"][0]["conductance"],
                }
            ],
        }
        section["output"] = {"drain_flow": True}
        model = build(section, run_dir)
        result = model.run_step(pcr.scalar(0.0), DAYS)
        np.testing.assert_allclose(
            values(result.baseflow_mm), np.full((ROWS, COLS), 2.0 * DAYS * 1000.0 / CELL_AREA)
        )

    def test_the_river_leakage_is_read_only_for_layers_with_river_cells(self, section, run_dir, mf):
        bound2 = write_grid_map(
            Path(section["top"]).with_name("bound2.map"),
            [0 if value else 1 for value in MIDDLE_COLUMN],
            nominal=True,
        )
        section["layers"][1]["boundary"] = bound2
        section["river"]["entries"][0]["layers"] = [1, 2]
        model = build(section, run_dir)
        model.run_step(pcr.scalar(0.0), DAYS)
        assert [item.args for item in calls(mf, "getRiverLeakage")] == [(3,)]

    def test_heads_are_keyed_by_user_layer(self, section, run_dir, mf):
        model = build(section, run_dir)
        result = model.run_step(pcr.scalar(0.0), DAYS)
        assert sorted(result.heads) == [1, 2, 3]
        assert {number: float(values(head)[0, 0]) for number, head in result.heads.items()} == {
            1: 3.0,
            2: 2.0,
            3: 1.0,
        }

    def test_heads_are_not_read_unless_requested(self, section, run_dir, mf):
        section["output"] = {"heads": False}
        model = build(section, run_dir)
        result = model.run_step(pcr.scalar(0.0), DAYS)
        assert result.heads == {}
        mf.getHeads.assert_not_called()

    def test_storage_is_read_when_requested(self, section, run_dir, mf):
        model = build(section, run_dir)
        assert model.run_step(pcr.scalar(0.0), DAYS).storage == {}
        mf.getStorage.assert_not_called()
        section["output"] = {"storage": True}
        model = build(section, run_dir.parent / "second")
        storage = model.run_step(pcr.scalar(0.0), DAYS).storage
        assert {number: float(values(item)[0, 0]) for number, item in storage.items()} == {
            1: 30.0,
            2: 20.0,
            3: 10.0,
        }

    def test_the_drain_flow_is_read_only_for_layers_with_drain_cells(self, section, run_dir, mf):
        empty = write_grid_map(Path(section["top"]).with_name("empty.map"), 0.0)
        conductance = section["ghb"]["entries"][0]["conductance"]
        section["drain"] = {
            "enabled": True,
            "entries": [
                {"layers": [1], "elevation": section["top"], "conductance": conductance},
                {"layers": [2], "elevation": section["top"], "conductance": empty},
            ],
        }
        section["output"] = {"drain_flow": True}
        model = build(section, run_dir)
        result = model.run_step(pcr.scalar(0.0), DAYS)
        assert [item.args for item in calls(mf, "getDrain")] == [(3,)]
        assert sorted(result.drain_flow) == [1, 2]
        np.testing.assert_allclose(values(result.drain_flow[1]), np.full((ROWS, COLS), -100.0))
        np.testing.assert_allclose(values(result.drain_flow[2]), np.zeros((ROWS, COLS)))

    def test_the_drain_flow_is_not_read_unless_requested(self, section, run_dir, mf):
        section["drain"] = {
            "enabled": True,
            "entries": [
                {
                    "layers": [1],
                    "elevation": section["top"],
                    "conductance": section["ghb"]["entries"][0]["conductance"],
                }
            ],
        }
        model = build(section, run_dir)
        assert model.run_step(pcr.scalar(0.0), DAYS).drain_flow == {}
        mf.getDrain.assert_not_called()

    @pytest.mark.parametrize("days", [0, -1, math.nan])
    def test_a_period_must_last_a_positive_number_of_days(self, section, run_dir, days):
        model = build(section, run_dir)
        with pytest.raises(ValueError, match="days"):
            model.run_step(pcr.scalar(0.0), days)

    def test_a_step_needs_an_initialized_model(self, section, run_dir):
        model = ModflowGroundwater(ModflowSettings.model_validate(section), CELL_AREA, run_dir)
        with pytest.raises(RuntimeError, match="initialize"):
            model.run_step(pcr.scalar(0.0), DAYS)


def enable_root_depth(section, method, layer=None):
    water_table = {"method": method} if layer is None else {"method": method, "layer": layer}
    section["coupling"] = {
        "dynamic_root_depth": {
            "enabled": True,
            "minimum_depth_table": section["layers"][0]["horizontal_conductivity"]["table"],
            "water_table": water_table,
        }
    }


@pytest.mark.usefixtures("extension")
class TestWaterTable:
    """User layer 1 is dry in cell 1 and 95 m elsewhere, layer 2 is 85 m, layer 3 is 50 m.

    Layer 1 spans 80-100 m, layer 2 60-80 m and layer 3 40-60 m, so the head of
    layer 2 lies above its top (the layer is confined there).
    """

    @pytest.fixture(autouse=True)
    def heads(self, mf, section):  # section sets the clone the fields need
        user = {
            1: pcr.numpy2pcr(pcr.Scalar, grid([DRY_HEAD] + [95.0] * 8), np.nan),
            2: pcr.spatial(pcr.scalar(85.0)),
            3: pcr.spatial(pcr.scalar(50.0)),
        }
        mf.getHeads.side_effect = lambda layer: user[4 - layer]

    def test_without_the_coupling_there_is_no_water_table(self, section, run_dir):
        assert build(section, run_dir).run_step(pcr.scalar(0.0), DAYS).water_table_head is None

    def test_the_highest_active_head_skips_dry_and_inactive_cells(self, section, run_dir):
        bound1 = write_grid_map(
            Path(section["top"]).with_name("bound1.map"),
            [0 if index == 2 else 1 for index in range(9)],
            nominal=True,
        )
        section["layers"][0]["boundary"] = bound1
        enable_root_depth(section, "highest_active_head")
        result = build(section, run_dir).run_step(pcr.scalar(0.0), DAYS)
        np.testing.assert_allclose(
            values(result.water_table_head), grid([85.0, 95.0, 85.0] + [95.0] * 6)
        )

    def test_the_water_table_uses_the_inputs_read_at_initialize(
        self, section, run_dir, monkeypatch
    ):
        section["layers"][0]["boundary"] = write_grid_map(
            Path(section["top"]).with_name("bound1.map"),
            [0 if index == 2 else 1 for index in range(9)],
            nominal=True,
        )
        enable_root_depth(section, "highest_active_head")
        model = build(section, run_dir)

        def read_field(*args, **kwargs):
            raise AssertionError("an input was read again after initialize")

        monkeypatch.setattr(_modflow, "read_field", read_field)
        result = model.run_step(pcr.scalar(0.0), DAYS)
        np.testing.assert_allclose(
            values(result.water_table_head), grid([85.0, 95.0, 85.0] + [95.0] * 6)
        )

    def test_the_highest_unconfined_head_skips_convertible_layers_above_their_top(
        self, section, run_dir
    ):
        enable_root_depth(section, "highest_unconfined")
        result = build(section, run_dir).run_step(pcr.scalar(0.0), DAYS)
        np.testing.assert_allclose(values(result.water_table_head), grid([50.0] + [95.0] * 8))

    def test_the_highest_unconfined_head_keeps_a_convertible_layer_below_its_top(
        self, section, run_dir, mf
    ):
        # 70 m lies inside layer 2 (60-80 m): above its bottom, below its top.
        user = {
            1: pcr.numpy2pcr(pcr.Scalar, grid([DRY_HEAD] + [95.0] * 8), np.nan),
            2: pcr.spatial(pcr.scalar(70.0)),
            3: pcr.spatial(pcr.scalar(50.0)),
        }
        mf.getHeads.side_effect = lambda layer: user[4 - layer]
        enable_root_depth(section, "highest_unconfined")
        result = build(section, run_dir).run_step(pcr.scalar(0.0), DAYS)
        np.testing.assert_allclose(values(result.water_table_head), grid([70.0] + [95.0] * 8))

    def test_the_highest_unconfined_head_skips_confined_layers(self, section, run_dir):
        section["layers"][0]["laytype"] = 0
        section["wetting"]["enabled"] = False
        enable_root_depth(section, "highest_unconfined")
        result = build(section, run_dir).run_step(pcr.scalar(0.0), DAYS)
        np.testing.assert_allclose(values(result.water_table_head), np.full((ROWS, COLS), 50.0))

    def test_an_explicit_layer_gives_its_head(self, section, run_dir):
        enable_root_depth(section, "layer", layer=2)
        result = build(section, run_dir).run_step(pcr.scalar(0.0), DAYS)
        np.testing.assert_allclose(values(result.water_table_head), np.full((ROWS, COLS), 85.0))

    def test_an_explicit_layer_skips_its_dry_and_inactive_cells(self, section, run_dir):
        section["layers"][0]["boundary"] = write_grid_map(
            Path(section["top"]).with_name("bound1.map"),
            [0 if index == 2 else 1 for index in range(9)],
            nominal=True,
        )
        enable_root_depth(section, "layer", layer=1)
        result = build(section, run_dir).run_step(pcr.scalar(0.0), DAYS)
        np.testing.assert_allclose(
            values(result.water_table_head), grid([NAN, 95.0, NAN] + [95.0] * 6)
        )

    def test_the_coupling_reads_heads_that_are_not_reported(self, section, run_dir, mf):
        section["output"] = {"heads": False}
        enable_root_depth(section, "layer", layer=3)
        result = build(section, run_dir).run_step(pcr.scalar(0.0), DAYS)
        assert result.heads == {}
        np.testing.assert_allclose(values(result.water_table_head), np.full((ROWS, COLS), 50.0))
