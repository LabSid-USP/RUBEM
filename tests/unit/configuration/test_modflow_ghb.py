from pathlib import Path

import pytest
from pydantic import ValidationError

from rubem.configuration.modflow_configuration import (
    ModflowConfiguration,
    ModflowGhbConfiguration,
)

pytestmark = pytest.mark.unit


def ghb_layer(layer=1):
    return {"layer": layer, "head": "head.map", "conductance": "cond.map"}


def test_ghb_disabled_by_default():
    assert ModflowConfiguration().ghb.enabled == 0
    assert ModflowGhbConfiguration(enabled=0).layers == []


@pytest.mark.parametrize(
    "layers",
    [
        [],
        [ghb_layer(), ghb_layer()],
        [ghb_layer(0)],
        [{"layer": 1, "conductance": "cond.map"}],
        [{"layer": 1, "head": "head.map"}],
        [{"layer": 1, "head": "", "conductance": "cond.map"}],
        [{"layer": 1, "head": "head.map", "conductance": ""}],
    ],
)
def test_invalid_ghb_inputs(layers):
    with pytest.raises(ValidationError):
        ModflowGhbConfiguration(enabled=1, layers=layers)


def test_ghb_layer_must_exist_in_model():
    with pytest.raises(ValidationError, match="GHB layer 2 is outside"):
        ModflowConfiguration(
            enabled=1,
            bottom="bottom.map",
            layers=[{
                "name": "aquifer", "top": "top.map", "boundary": "bound.map",
                "initial_head": "head.map", "horizontal_conductivity": "k.map",
                "vertical_conductivity": "k.map",
            }],
            dis={"steady_state": 1},
            river={"enabled": 1, "layers": [{
                "layer": 1, "stage": "stage.map", "bottom": "bed.map",
                "conductance": "riv_cond.map",
            }]},
            ghb={"enabled": 1, "layers": [ghb_layer(2)]},
        )


def test_resolve_ghb_paths_per_layer(tmp_path):
    absolute_head = str(tmp_path / "external.map")
    config = ModflowConfiguration(ghb={"enabled": 1, "layers": [
        ghb_layer(), {"layer": 2, "head": absolute_head, "conductance": "cond2.map"},
    ]})
    resolved = config.resolve_paths(tmp_path)
    assert Path(resolved.ghb.layers[0].head) == tmp_path / "head.map"
    assert Path(resolved.ghb.layers[0].conductance) == tmp_path / "cond.map"
    assert resolved.ghb.layers[1].head == absolute_head
    assert Path(resolved.ghb.layers[1].conductance) == tmp_path / "cond2.map"
    assert config.ghb.layers[0].head == "head.map"
