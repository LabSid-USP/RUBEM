import shutil

import numpy as np
import pcraster as pcr
import pytest

from rubem.configuration.modflow_configuration import ModflowConfiguration
from rubem.hydrological_processes._modflow import ModflowGroundwater

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("mf2005") is None, reason="mf2005 is required"),
]


def run_case(root, monkeypatch, calibrated, typed, laytypes):
    root.mkdir()
    monkeypatch.chdir(root)
    pcr.setclone(3, 3, 30, 0, 90)
    active = np.array([[False, True, True]] * 3)
    river = np.array([[False, False, True]] * 3)

    def raster(name, values, nominal=False):
        array = np.broadcast_to(np.asarray(values, dtype=float), (3, 3)).copy()
        array[~active] = np.nan
        field = pcr.numpy2pcr(pcr.Scalar, array, np.nan)
        if nominal:
            field = pcr.nominal(field)
        path = root / f"{name}.map"
        pcr.report(field, str(path))
        return str(path)

    layers = []
    for number, laytype in enumerate(laytypes, 1):
        class_values = np.array([[1, 1, 2], [2, 2, 1], [1, 2, 1]])
        classes = raster(f"classes{number}", class_values, nominal=True)
        kh = np.where(class_values == 1, number * 0.5, number * 2.0)
        table = root / f"kh{number}.tbl"
        table.write_text(f"1 {number * 0.5}\n2 {number * 2.0}\n", encoding="ascii")
        layers.append({
            "name": f"layer{number}", "top": raster(f"top{number}", number * 20),
            "boundary": raster(f"boundary{number}", 1, nominal=True),
            "initial_head": raster(f"head{number}", 50), "laytype": laytype,
            "horizontal_conductivity": (
                {"map": classes, "table": str(table)} if calibrated else raster(f"kh{number}", kh)
            ),
            "vertical_conductivity": raster(f"kv{number}", 0.2),
            "specific_storage": 0.0001 if calibrated else raster(f"ss{number}", 0.0001),
            "specific_yield": 0.1 if calibrated else raster(f"sy{number}", 0.1),
        })
    river_layer = {
        "layer": 3, "stage": raster("stage", np.where(river, 51, np.nan)),
        "bottom": raster("bed", np.where(river, 41, np.nan)),
        "conductance": 2 if calibrated else raster("rivcond", np.where(river, 2, 0)),
    }
    if calibrated:
        river_layer["mask"] = raster("rivers", river)
    config = {
        "enabled": 1, "bottom": raster("bottom", 0), "layers": layers,
        "dis": {"nstp": 2},
        "solver": {"hclose": 1e-6, "rclose": 1e-6, "damp": 1},
        "river": {"enabled": 1, "layers": [river_layer]},
        "ghb": {"enabled": 1, "layers": [{
            "layer": 1, "head": raster("ghbhead", 52), "conductance": raster("ghbcond", 1),
        }]},
        "drain": {"enabled": 1, "layers": [{
            "layer": 3, "elevation": raster("drnelev", 50.5),
            "conductance": raster("drncond", 0.5),
        }]},
        "output": {"storage": True, "drain_flow": True},
    }
    if typed:
        config = ModflowConfiguration.model_validate(config).resolve_paths(root)
    model = ModflowGroundwater(config, 900)
    model.initialize(30)
    results = []
    for _ in range(2):
        result = model.run_timestep(pcr.spatial(pcr.scalar(30)), 30)
        assert result.converged
        for field in [
            *result.heads.values(), *result.storage.values(), *result.drain_flow.values(),
            result.baseflow_mm, result.net_river_leakage_m3_per_day,
        ]:
            results.append(pcr.pcr2numpy(field, np.nan)[active])
    return results


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("laytypes", [(0, 2, 1), (2, 3, 3)])
def test_three_layer_constants_and_lookups_match_maps(tmp_path, monkeypatch, typed, laytypes):
    maps = run_case(tmp_path / "maps", monkeypatch, False, typed, laytypes)
    calibrated = run_case(tmp_path / "calibrated", monkeypatch, True, typed, laytypes)
    assert len(maps) == len(calibrated)
    for expected, actual in zip(maps, calibrated):
        np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-6)
