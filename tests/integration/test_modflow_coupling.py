"""The MODFLOW groundwater module against the real ``mf2005`` on a 3x3 grid.

One layer receives recharge and exchanges water with a river, a general head
boundary and a drain in every cell; with no lateral gradient each cell is a
closed balance whose head has an analytic solution (the cases of the
scientist's prototype, ported to the top-down configuration). The masked
variants leave the left column outside every layer, which exercises the
synthetic elevations of inactive columns.

The three-layer cases check what one layer cannot show: the layer types
(LAYCON) reach MODFLOW on the right layers, and class lookups and numbers give
the same run as the equivalent maps.

The full RUBEM runs couple the synthetic dataset to its three-layer section
(:func:`write_modflow_inputs`) through the validated configuration.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pcraster as pcr
import pytest

from rubem._deps import resolve_mf2005
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.modflow_configuration import ModflowSettings
from rubem.core import DynamicFrameworkWrapper
from rubem.hydrological_processes._modflow import ModflowGroundwater
from tests.helpers.synthetic import (
    CELL_SIZE,
    MODFLOW_HEAD,
    MODFLOW_TOP,
    geotiff_series_name,
    series_name,
    write_grid_map,
    write_modflow_inputs,
    write_synthetic_dataset,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(resolve_mf2005() is None, reason="mf2005 is required"),
]

GEOGRAPHIC_PIXEL = 0.0002945488721804391443
CELL_AREA = 900.0
DAYS = 30
# 30 mm in 30 days is 0.001 m/day, 0.9 m3/day over a 900 m2 cell.
RECHARGE_MM = 30.0
RECHARGE_FLOW = 0.9
RIVER_STAGE = 50.0
RIVER_CONDUCTANCE = 2.0
PROBE_CELL = 2  # row 1, column 2: active in the masked variants too


class Grid:
    """Rasters on a 3x3 clone, optionally missing on the left column."""

    def __init__(self, directory, pixel_size, masked):
        pcr.setclone(3, 3, pixel_size, 0, 3 * pixel_size)
        self.directory = directory
        self.mask = pcr.xcoordinate(pcr.spatial(pcr.boolean(1))) > pixel_size
        self.masked = masked

    def field(self, value):
        field = pcr.spatial(pcr.scalar(value))
        return pcr.ifthen(self.mask, field) if self.masked else field

    def map(self, name, value, nominal=False):
        field = pcr.spatial(pcr.nominal(value) if nominal else pcr.scalar(value))
        if self.masked:
            field = pcr.ifthen(self.mask, field)
        path = str(self.directory / f"{name}.map")
        pcr.report(field, path)
        return path


def one_layer_section(grid, laytype, **packages):
    return {
        "enabled": True,
        "top": grid.map("top", 100),
        "layers": [
            {
                "name": "aquifer",
                "bottom": grid.map("bottom", 0),
                "boundary": grid.map("boundary", 1, nominal=True),
                "initial_head": grid.map("initial", 50),
                "laytype": laytype,
                "horizontal_conductivity": grid.map("kh", 1),
                "vertical_conductivity": grid.map("kv", 1),
                "specific_yield": grid.map("sy", 0.1),
            }
        ],
        "solver": {"hclose": 1e-8, "rclose": 1e-8, "damp": 1},
        "river": {
            "enabled": True,
            "entries": [
                {
                    "layers": [1],
                    "stage": grid.map("stage", RIVER_STAGE),
                    "bottom": grid.map("bed", 10),
                    "conductance": grid.map("rivcond", RIVER_CONDUCTANCE),
                }
            ],
        },
        **packages,
    }


@pytest.fixture(name="directories")
def directories_fixture(tmp_path, monkeypatch):
    """A run directory, and an empty working directory that must stay empty."""
    run_directory = tmp_path / "run"
    working_directory = tmp_path / "cwd"
    working_directory.mkdir()
    monkeypatch.chdir(working_directory)
    return run_directory, working_directory


def assert_files_only_in_run_directory(run_directory, working_directory):
    assert (run_directory / "pcrmf.lst").is_file()
    assert os.listdir(working_directory) == []


@pytest.mark.parametrize("external_head, conductance", [(60, 3), (40, 3), (60, 0)])
@pytest.mark.parametrize("masked", [False, True])
@pytest.mark.parametrize("transient", [False, True])
@pytest.mark.parametrize("pixel_size", [30.0, GEOGRAPHIC_PIXEL])
def test_river_and_general_head_balance(
    tmp_path, directories, external_head, conductance, masked, transient, pixel_size
):
    """The metric recharge and storage balance holds whatever the clone units."""
    grid = Grid(tmp_path, pixel_size, masked)
    section = one_layer_section(
        grid,
        laytype=1 if transient else 0,
        dis={"steady_state": not transient, "nstp": 1},
        wetting={"enabled": transient, "map": grid.map("wet", -0.1), "layers": [1]},
        ghb={
            "enabled": True,
            "entries": [
                {
                    "layers": [1],
                    "head": grid.map("external", external_head),
                    "conductance": grid.map("ghbcond", conductance),
                }
            ],
        },
    )
    run_directory, working_directory = directories
    model = ModflowGroundwater(ModflowSettings.model_validate(section), CELL_AREA, run_directory)
    model.initialize(DAYS)
    expected_head = 50.0
    for _ in range(2):
        # Sy * area / duration is the implicit storage coefficient [m2/day].
        storage = 0.1 * CELL_AREA / DAYS if transient else 0.0
        expected_head = (
            conductance * external_head
            + RIVER_CONDUCTANCE * RIVER_STAGE
            + RECHARGE_FLOW
            + storage * expected_head
        ) / (conductance + RIVER_CONDUCTANCE + storage)
        expected_river = RIVER_CONDUCTANCE * (RIVER_STAGE - expected_head)
        result = model.run_step(grid.field(RECHARGE_MM), DAYS)
        assert pcr.cellvalue(result.heads[1], PROBE_CELL)[0] == pytest.approx(expected_head)
        river = pcr.cellvalue(result.net_river_leakage_m3_per_day, PROBE_CELL)[0]
        assert river == pytest.approx(expected_river, abs=1e-4)
        assert pcr.cellvalue(result.baseflow_mm, PROBE_CELL)[0] == pytest.approx(
            max(-expected_river, 0) * DAYS * 1000 / CELL_AREA, abs=1e-4 * DAYS * 1000 / CELL_AREA
        )
        if conductance:
            ghb = pcr.cellvalue(model.mf.getGeneralHeadLeakage(1), PROBE_CELL)[0]
            assert ghb == pytest.approx(conductance * (external_head - expected_head), abs=1e-4)
    assert_files_only_in_run_directory(run_directory, working_directory)


@pytest.mark.parametrize("masked", [False, True])
@pytest.mark.parametrize(
    "elevation, conductance, enabled, output",
    [
        (50, 4, True, True),
        (56.18, 4, True, True),
        (65, 4, True, True),
        (50, 0, True, True),
        (50, 4, False, True),
        (50, 4, True, False),
    ],
)
def test_drain_with_general_head_river_and_recharge(
    tmp_path, directories, masked, elevation, conductance, enabled, output
):
    grid = Grid(tmp_path, GEOGRAPHIC_PIXEL, masked)
    section = one_layer_section(
        grid,
        laytype=0,
        dis={"steady_state": True, "nstp": 1},
        ghb={
            "enabled": True,
            "entries": [
                {
                    "layers": [1],
                    "head": grid.map("external", 60),
                    "conductance": grid.map("ghbcond", 3),
                }
            ],
        },
        drain={
            "enabled": enabled,
            "entries": [
                {
                    "layers": [1],
                    "elevation": grid.map("drnelev", elevation),
                    "conductance": grid.map("drncond", conductance),
                }
            ],
        },
        output={"drain_flow": output},
    )
    run_directory, working_directory = directories
    model = ModflowGroundwater(ModflowSettings.model_validate(section), CELL_AREA, run_directory)
    model.initialize(DAYS)
    # Without the drain: RCH 0.9 m3/day, GHB C=3 at 60 m, RIV C=2 at 50 m, so
    # h = (3 * 60 + 2 * 50 + 0.9) / 5 = 56.18 m; the drain acts only below it.
    effective = conductance if enabled and elevation < 56.18 else 0
    expected_head = (280.9 + effective * elevation) / (5 + effective)
    expected_drain = -effective * max(expected_head - elevation, 0)
    expected_river = RIVER_CONDUCTANCE * (RIVER_STAGE - expected_head)
    for _ in range(2):
        result = model.run_step(grid.field(RECHARGE_MM), DAYS)
        assert pcr.cellvalue(result.heads[1], PROBE_CELL)[0] == pytest.approx(
            expected_head, abs=1e-4
        )
        assert pcr.cellvalue(result.baseflow_mm, PROBE_CELL)[0] == pytest.approx(
            max(-expected_river, 0) * DAYS * 1000 / CELL_AREA, abs=0.01
        )
        if enabled and output:
            drain = pcr.cellvalue(result.drain_flow[1], PROBE_CELL)[0]
            assert drain == pytest.approx(expected_drain, abs=1e-4)
        else:
            assert result.drain_flow == {}
    assert_files_only_in_run_directory(run_directory, working_directory)


def bcf_layer_types(run_directory):
    """The LAYCON of each layer in the BCF file, MODFLOW order (top layer first)."""
    lines = (run_directory / "pcrmf.bc6").read_text(encoding="utf8").splitlines()
    return [int(value) for value in lines[1].split()]


def test_the_layer_types_of_the_synthetic_dataset_reach_their_layers(tmp_path, directories):
    """LAYCON 1 on the top layer and 2 below: MODFLOW refuses LAYCON 1 on any other layer."""
    config = write_synthetic_dataset(str(tmp_path / "dataset"))
    settings = ModflowSettings.model_validate(write_modflow_inputs(config))
    run_directory, working_directory = directories
    model = ModflowGroundwater(settings, CELL_SIZE * CELL_SIZE, run_directory)
    model.initialize(DAYS)
    for _ in range(2):
        result = model.run_step(pcr.spatial(pcr.scalar(RECHARGE_MM)), DAYS)
        assert sorted(result.heads) == [1, 2, 3]
        for head in result.heads.values():
            assert np.isfinite(pcr.pcr2numpy(head, np.nan)).all()
    assert bcf_layer_types(run_directory) == [1, 2, 2]
    listing = (run_directory / "pcrmf.lst").read_text(encoding="utf8", errors="replace")
    assert "LAYER TYPE 1 IS ONLY ALLOWED" not in listing
    assert_files_only_in_run_directory(run_directory, working_directory)


ACTIVE = np.array([[False, True, True]] * 3)
RIVER = np.array([[False, False, True]] * 3)
CLASSES = np.array([[1, 1, 2], [2, 2, 1], [1, 2, 1]])


def three_layer_section(directory, laytypes, calibrated):
    """Three layers 20 m thick under a top at 60 m, the left column inactive.

    Layer ``n`` (top down) has the conductivity ``0.5 n`` in class 1 and ``2 n``
    in class 2. ``calibrated`` gives it as a class lookup, the storage and the
    river conductance as numbers; otherwise every input is a map. The river
    and the drain lie on layer 1, the general head boundary on layer 3, and
    wetting applies to every LAYCON 1 or 3 layer.
    """
    pcr.setclone(3, 3, 30, 0, 90)
    directory.mkdir()

    def raster(name, values, nominal=False):
        array = np.broadcast_to(np.asarray(values, dtype=float), (3, 3)).copy()
        array[~ACTIVE] = np.nan
        field = pcr.numpy2pcr(pcr.Scalar, array, np.nan)
        if nominal:
            field = pcr.nominal(field)
        path = directory / f"{name}.map"
        pcr.report(field, str(path))
        return str(path)

    layers = []
    for number, laytype in enumerate(laytypes, start=1):
        table = directory / f"kh{number}.tbl"
        table.write_text(f"1 {number * 0.5}\n2 {number * 2.0}\n", encoding="ascii")
        kh = np.where(CLASSES == 1, number * 0.5, number * 2.0)
        layers.append(
            {
                "name": f"layer{number}",
                "bottom": raster(f"bottom{number}", 60 - 20 * number),
                "boundary": raster(f"boundary{number}", 1, nominal=True),
                "initial_head": raster(f"head{number}", 50),
                "laytype": laytype,
                "horizontal_conductivity": (
                    {"map": raster(f"classes{number}", CLASSES, nominal=True), "table": str(table)}
                    if calibrated
                    else raster(f"kh{number}", kh)
                ),
                "vertical_conductivity": raster(f"kv{number}", 0.2),
                "specific_storage": 0.0001 if calibrated else raster(f"ss{number}", 0.0001),
                "specific_yield": 0.1 if calibrated else raster(f"sy{number}", 0.1),
            }
        )
    river = {
        "layers": [1],
        "stage": raster("stage", np.where(RIVER, 51, np.nan)),
        "bottom": raster("bed", np.where(RIVER, 41, np.nan)),
        "conductance": 2 if calibrated else raster("rivcond", np.where(RIVER, 2, 0)),
    }
    if calibrated:
        river["mask"] = raster("rivers", RIVER)
    return {
        "enabled": True,
        "top": raster("top", 60),
        "layers": layers,
        "dis": {"nstp": 2},
        "solver": {"hclose": 1e-6, "rclose": 1e-6, "damp": 1},
        "wetting": {
            "enabled": True,
            "map": raster("wet", 1),
            "layers": [n for n, laytype in enumerate(laytypes, start=1) if laytype in (1, 3)],
        },
        "river": {"enabled": True, "entries": [river]},
        "ghb": {
            "enabled": True,
            "entries": [
                {"layers": [3], "head": raster("ghbhead", 52), "conductance": raster("ghbcond", 1)}
            ],
        },
        "drain": {
            "enabled": True,
            "entries": [
                {
                    "layers": [1],
                    "elevation": raster("drnelev", 50.5),
                    "conductance": raster("drncond", 0.5),
                }
            ],
        },
        "output": {"storage": True, "drain_flow": True},
    }


def run_three_layers(directory, laytypes, calibrated):
    section = three_layer_section(directory, laytypes, calibrated)
    run_directory = directory / "run"
    model = ModflowGroundwater(ModflowSettings.model_validate(section), 900, run_directory)
    model.initialize(30)
    results = []
    for _ in range(2):
        result = model.run_step(pcr.spatial(pcr.scalar(30)), 30)
        assert sorted(result.heads) == sorted(result.storage) == [1, 2, 3]
        assert sorted(result.drain_flow) == [1]
        for item in [
            *result.heads.values(),
            *result.storage.values(),
            *result.drain_flow.values(),
            result.baseflow_mm,
            result.net_river_leakage_m3_per_day,
        ]:
            results.append(pcr.pcr2numpy(item, np.nan)[ACTIVE])
    assert bcf_layer_types(run_directory) == list(laytypes)
    return results


@pytest.mark.parametrize("laytypes", [(1, 2, 0), (3, 3, 2)])
def test_three_layer_constants_and_lookups_match_maps(tmp_path, directories, laytypes):
    maps = run_three_layers(tmp_path / "maps", laytypes, calibrated=False)
    calibrated = run_three_layers(tmp_path / "calibrated", laytypes, calibrated=True)
    assert len(maps) == len(calibrated)
    for expected, actual in zip(maps, calibrated, strict=True):
        np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-6)


MONTH_DAYS = {1: 31, 2: 29}  # January and February 2000


def coupled_dataset(directory, **section_updates):
    """The synthetic dataset coupled to MODFLOW, its river below the water table.

    The river stage is 5 m below the initial head, so the aquifer drains into
    the river and the baseflow is not zero.
    """
    config = write_synthetic_dataset(str(directory))
    section = write_modflow_inputs(config)
    river = section["river"]["entries"][0]
    river["stage"] = write_grid_map(Path(river["stage"]), MODFLOW_HEAD - 5.0)
    river["bottom"] = write_grid_map(Path(river["bottom"]), MODFLOW_TOP - 18.0)
    section.update(section_updates)
    config["MODFLOW"] = section
    return config


def run_rubem(config):
    DynamicFrameworkWrapper.load(ModelConfiguration(config)).run()


def read_map(path):
    return pcr.pcr2numpy(pcr.scalar(pcr.readmap(str(path))), np.nan)


def run_broken_solver_in_a_child(tmp_path, dis=None):
    """Run the coupled dataset with a solver that cannot converge, in a child process.

    The child prints ``RAISED <message>`` when the run raises ``RuntimeError``
    and ``RETURNED`` when it ends normally; a child the extension ends prints
    neither.

    :param dis: The ``dis`` object of the section; ``None`` leaves the default.
    """
    root = Path(__file__).resolve().parents[2]
    working_directory = tmp_path / "cwd"
    working_directory.mkdir()
    script = (
        "import json, sys\n"
        "from tests.integration.test_modflow_coupling import coupled_dataset, run_rubem\n"
        "dis = json.loads(sys.argv[2])\n"
        "config = coupled_dataset(sys.argv[1], solver={'mxiter': 1, 'iter1': 1,"
        " 'hclose': 1e-12, 'rclose': 1e-12}, **({'dis': dis} if dis else {}))\n"
        "assert ('dis' in config['MODFLOW']) == bool(dis)\n"
        "try:\n"
        "    run_rubem(config)\n"
        "except RuntimeError as error:\n"
        "    print('RAISED', error)\n"
        "else:\n"
        "    print('RETURNED')\n"
    )
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join([str(root), *sys.path])}
    return subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "dataset"), json.dumps(dis)],
        cwd=working_directory,
        env=environment,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=600,
        check=False,
    )


class TestCoupledRun:
    def test_the_baseflow_is_the_river_leakage_and_the_heads_are_written(
        self, tmp_path, directories, monkeypatch
    ):
        config = coupled_dataset(tmp_path / "dataset")
        output = Path(config["DIRECTORIES"]["output"])
        run_directory, working_directory = directories
        during = []
        run_step = ModflowGroundwater.run_step

        def observed_run_step(self, recharge_mm, days_in_period):
            result = run_step(self, recharge_mm, days_in_period)
            during.append(
                (
                    Path(self.run_directory),
                    (output / "modflow" / "pcrmf.lst").is_file(),
                    sorted(path.name for path in output.glob("pcrmf*")),
                    os.listdir(working_directory),
                )
            )
            return result

        monkeypatch.setattr(ModflowGroundwater, "run_step", observed_run_step)

        run_rubem(config)

        assert during == [(output / "modflow", True, [], [])] * len(MONTH_DAYS)
        assert not (output / "modflow").exists()
        assert os.listdir(working_directory) == []
        for step, days in MONTH_DAYS.items():
            baseflow = read_map(output / series_name("bfw", step))
            leakage = read_map(output / series_name("mfaq2rv", step))
            assert leakage.max() > 0
            np.testing.assert_allclose(
                baseflow, leakage * days * 1000.0 / (CELL_SIZE * CELL_SIZE), rtol=1e-5, atol=1e-6
            )
            for number in (1, 2, 3):
                prefix = f"mfh{number}"
                assert (output / series_name(prefix, step)).is_file(), (prefix, step)
                assert (output / geotiff_series_name(prefix, step)).is_file(), (prefix, step)
                assert np.isfinite(read_map(output / series_name(prefix, step))).all()

    def test_nothing_is_written_without_a_raster_format(self, tmp_path, directories):
        config = coupled_dataset(tmp_path / "dataset")
        config["RASTER_FILE_FORMAT"] = {"map_raster_series": False, "tiff_raster_series": False}
        config["GENERATE_FILE"] = {key: False for key in config["GENERATE_FILE"]}

        run_rubem(config)

        assert os.listdir(config["DIRECTORIES"]["output"]) == []
        assert os.listdir(directories[1]) == []

    def test_non_convergence_stops_the_run_and_keeps_the_listing(self, tmp_path, directories):
        config = coupled_dataset(
            tmp_path / "dataset",
            dis={"nstp": 1},
            solver={"mxiter": 1, "iter1": 1, "hclose": 1e-12, "rclose": 1e-12},
        )

        with pytest.raises(RuntimeError, match="did not converge in stress period 1"):
            run_rubem(config)

        assert (Path(config["DIRECTORIES"]["output"]) / "modflow" / "pcrmf.lst").is_file()

    def test_non_convergence_with_the_default_time_steps_raises(self, tmp_path):
        """The default ``dis`` (one time step per period) keeps the failure recoverable.

        The run happens in a child process because the opposite outcome, the
        extension ending the process, would take the test runner with it.
        """
        child = run_broken_solver_in_a_child(tmp_path)

        output = child.stdout + child.stderr
        assert child.returncode == 0, output
        assert "RAISED MODFLOW did not converge in stress period 1" in child.stdout
        assert "MODFLOW failed to converge" in output
        listing = tmp_path / "dataset" / "out" / "modflow" / "pcrmf.lst"
        assert "STOPPING SIMULATION" in listing.read_text(encoding="utf8", errors="replace")

    def test_non_convergence_before_the_last_time_step_ends_the_process(self, tmp_path):
        """Pins the documented limitation of ``dis.nstp`` above 1.

        MODFLOW saves the heads only at the last time step of the period and
        stops at the first time step that fails to converge. With several time
        steps nothing is saved in the first period, and the extension ends the
        process when it reads the missing head file, before ``converged()``
        can be asked. The run therefore happens in a child process.
        """
        child = run_broken_solver_in_a_child(tmp_path, dis={"nstp": 5})

        output = child.stdout + child.stderr
        assert child.returncode != 0, output
        assert "RAISED" not in child.stdout
        assert "RETURNED" not in child.stdout
        assert "MODFLOW failed to converge" in output
        assert "Can not open head value result file" in output
        listing = tmp_path / "dataset" / "out" / "modflow" / "pcrmf.lst"
        assert "STOPPING SIMULATION" in listing.read_text(encoding="utf8", errors="replace")
