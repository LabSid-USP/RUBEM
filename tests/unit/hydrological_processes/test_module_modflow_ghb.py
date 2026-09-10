from unittest.mock import Mock, call

import pcraster as pcr
import pytest

from rubem.configuration.modflow_configuration import ModflowConfiguration
from rubem.hydrological_processes._modflow import ModflowGroundwater

pytestmark = pytest.mark.unit


@pytest.fixture
def config(tmp_path):
    raster = tmp_path / "input.map"
    raster.touch()
    path = str(raster)
    layer = {
        "name": "aquifer", "top": path, "boundary": path,
        "initial_head": path, "horizontal_conductivity": path,
        "vertical_conductivity": path,
    }
    return {
        "enabled": 1, "bottom": path, "layers": [layer, dict(layer)],
        "dis": {"steady_state": 1},
        "river": {"enabled": 1, "layers": [
            {"layer": 2, "stage": path, "bottom": path, "conductance": path},
        ]},
        "ghb": {"enabled": 1, "layers": [
            {"layer": 1, "head": path, "conductance": path},
            {"layer": 2, "head": path, "conductance": path},
        ]},
        "output": {"heads": False, "storage": False},
    }


@pytest.mark.parametrize("typed", [False, True])
def test_ghb_applied_before_each_run(config, typed):
    pcr.setclone(1, 1, 30, 0, 30)
    groundwater = ModflowGroundwater(
        ModflowConfiguration.model_validate(config) if typed else config, 900
    )
    groundwater._validate_configuration()
    groundwater.mf = Mock()
    groundwater.mf.converged.return_value = True
    groundwater.mf.getRiverLeakage.return_value = pcr.spatial(pcr.scalar(-2))
    groundwater._read_stress_inputs = Mock(
        side_effect=lambda package, layer, conductance, **heads: (conductance, heads)
    )
    groundwater._initialized = True

    for _ in range(2):
        result = groundwater.run_timestep(pcr.scalar(0), 30)
        # GHB does not add a second contribution to RUBEM's RIV baseflow.
        assert pcr.cellvalue(result.baseflow_mm, 1)[0] == pytest.approx(2 * 30 * 1000 / 900)

    stress_calls = [
        item for item in groundwater.mf.mock_calls
        if item[0] in ("setGeneralHead", "run")
    ]
    path = config["bottom"]
    assert stress_calls == [
        call.setGeneralHead(path, path, 1),
        call.setGeneralHead(path, path, 2),
        call.run(),
    ] * 2


def test_disabled_ghb_does_not_read_maps_or_call_backend(config):
    config["ghb"] = {"enabled": 0, "layers": [
        {"layer": 1, "head": "missing.map", "conductance": "missing.map"},
    ]}
    groundwater = ModflowGroundwater(config, 900)
    groundwater.mf = Mock()
    groundwater._validate_configuration()
    groundwater._set_ghb_stress()
    groundwater.mf.setGeneralHead.assert_not_called()


@pytest.mark.parametrize("key", ["head", "conductance"])
def test_missing_ghb_file_has_context(config, tmp_path, key):
    config["ghb"]["layers"][0][key] = str(tmp_path / "missing.map")
    with pytest.raises(FileNotFoundError, match=rf"MODFLOW.ghb.layers\[0\].{key}"):
        ModflowGroundwater(config, 900)._validate_configuration()


@pytest.mark.parametrize("problem", ["empty", "duplicate", "range", "head", "conductance"])
def test_mapping_configuration_validated(config, problem):
    layers = config["ghb"]["layers"]
    if problem == "empty":
        layers.clear()
    elif problem == "duplicate":
        layers[1]["layer"] = 1
    elif problem == "range":
        layers[0]["layer"] = 3
    else:
        del layers[0][problem]
    with pytest.raises(ValueError):
        ModflowGroundwater(config, 900)._validate_configuration()
