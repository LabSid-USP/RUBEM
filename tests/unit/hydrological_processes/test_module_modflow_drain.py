from pathlib import Path
from unittest.mock import Mock, call

import pcraster as pcr
import pytest
from pydantic import ValidationError

from rubem.configuration.modflow_configuration import (
    ModflowConfiguration,
    ModflowDrainConfiguration,
)
from rubem.hydrological_processes._modflow import ModflowGroundwater

pytestmark = pytest.mark.unit


@pytest.fixture
def config(tmp_path):
    path = str(tmp_path / "input.map")
    Path(path).touch()
    layer = {
        "name": "aquifer", "top": path, "boundary": path, "initial_head": path,
        "horizontal_conductivity": path, "vertical_conductivity": path,
    }
    return {
        "enabled": 1, "bottom": path, "layers": [layer, dict(layer)],
        "dis": {"steady_state": 1},
        "river": {"enabled": 1, "layers": [
            {"layer": 2, "stage": path, "bottom": path, "conductance": path},
        ]},
        "drain": {"enabled": 1, "layers": [
            {"layer": n, "elevation": path, "conductance": path} for n in (1, 2)
        ]},
        "output": {"heads": False, "drain_flow": True},
    }


@pytest.mark.parametrize("problem", ["empty", "duplicate", "range", "elevation", "conductance"])
def test_invalid_drain_configuration(config, problem):
    layers = config["drain"]["layers"]
    if problem == "empty":
        layers.clear()
    elif problem == "duplicate":
        layers[1]["layer"] = 1
    elif problem == "range":
        layers[0]["layer"] = 3
    else:
        del layers[0][problem]
    with pytest.raises(ValidationError):
        ModflowConfiguration.model_validate(config)
    with pytest.raises(ValueError):
        ModflowGroundwater(config, 900)._validate_configuration()


@pytest.mark.parametrize("key", ["elevation", "conductance"])
def test_empty_paths_rejected(key):
    layer = {"layer": 1, "elevation": "elev.map", "conductance": "cond.map"}
    layer[key] = ""
    with pytest.raises(ValidationError):
        ModflowDrainConfiguration(enabled=1, layers=[layer])


@pytest.mark.parametrize("key", ["elevation", "conductance"])
def test_missing_drain_file(config, tmp_path, key):
    config["drain"]["layers"][0][key] = str(tmp_path / "missing.map")
    with pytest.raises(FileNotFoundError, match=rf"MODFLOW.drain.layers\[0\].{key}"):
        ModflowGroundwater(config, 900)._validate_configuration()


def test_drain_defaults_and_disabled_maps(config):
    assert ModflowConfiguration().drain.enabled == 0
    assert ModflowConfiguration().output.drain_flow is False
    config["drain"] = {"enabled": 0, "layers": [
        {"layer": 1, "elevation": "missing.map", "conductance": "missing.map"},
    ]}
    model = ModflowGroundwater(config, 900)
    model.mf = Mock()
    model._validate_configuration()
    model._set_drain_stress()
    assert model._get_drain_flow_if_requested() == {}
    assert model.mf.mock_calls == []


def test_resolve_drain_paths(config, tmp_path):
    config["drain"]["layers"][0]["elevation"] = "elev.map"
    config["drain"]["layers"][1]["conductance"] = "cond.map"
    original = ModflowConfiguration.model_validate(config)
    resolved = original.resolve_paths(tmp_path)
    assert Path(resolved.drain.layers[0].elevation) == tmp_path / "elev.map"
    assert Path(resolved.drain.layers[1].conductance) == tmp_path / "cond.map"
    assert resolved.drain.layers[0].conductance == config["bottom"]
    assert original.drain.layers[0].elevation == "elev.map"


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("output", [False, True])
def test_drain_before_each_run_and_output_independent_of_baseflow(config, typed, output):
    pcr.setclone(1, 1, 30, 0, 30)
    config["output"]["drain_flow"] = output
    model = ModflowGroundwater(
        ModflowConfiguration.model_validate(config) if typed else config, 900
    )
    model._validate_configuration()
    cond, elevation = pcr.spatial(pcr.scalar(2)), pcr.spatial(pcr.scalar(50))
    model._read_stress_inputs = Mock(side_effect=lambda package, layer, path, **heads: (
        cond, {key: elevation for key in heads}
    ))
    model.mf = Mock()
    model.mf.converged.return_value = True
    model.mf.getRiverLeakage.return_value = pcr.spatial(pcr.scalar(-2))
    model.mf.getDrain.return_value = pcr.spatial(pcr.scalar(-10))
    model._initialized = True
    for _ in range(2):
        result = model.run_timestep(pcr.scalar(0), 30)
        assert pcr.cellvalue(result.baseflow_mm, 1)[0] == pytest.approx(2 * 30 * 1000 / 900)
        assert set(result.drain_flow) == ({1, 2} if output else set())
    relevant = [c for c in model.mf.mock_calls if c[0] in ("setDrain", "run")]
    assert relevant == [call.setDrain(elevation, cond, 1), call.setDrain(elevation, cond, 2), call.run()] * 2
    assert model.mf.getDrain.call_count == (4 if output else 0)


def test_negative_drain_conductance_rejected(config):
    pcr.setclone(1, 1, 30, 0, 30)
    model = ModflowGroundwater(config, 900)
    model.mf = Mock()
    model._read_stress_inputs = Mock(return_value=(
        pcr.spatial(pcr.scalar(-1)), {"elevation": pcr.spatial(pcr.scalar(50))}
    ))
    with pytest.raises(ValueError, match="conductance must be non-negative"):
        model._set_drain_stress()
    model.mf.setDrain.assert_not_called()
