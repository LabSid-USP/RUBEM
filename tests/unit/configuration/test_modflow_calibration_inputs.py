from pathlib import Path

import pytest
from pydantic import ValidationError

from rubem.configuration.modflow_configuration import (
    ModflowConfiguration,
    ModflowLayerConfiguration,
    ModflowRiverLayerConfiguration,
)

pytestmark = pytest.mark.unit


def layer(**overrides):
    return {
        "name": "aquifer", "top": "top.map", "boundary": "boundary.map",
        "initial_head": "head.map", "horizontal_conductivity": "kh.map",
        "vertical_conductivity": "kv.map", "specific_storage": 0.00001,
        "specific_yield": 0.1, "laytype": 2, **overrides,
    }


@pytest.mark.parametrize("laytype", [0, 1, 2, 3])
def test_zero_storage_is_present_and_not_a_missing_path(laytype):
    config = ModflowConfiguration(
        enabled=1, bottom="bottom.map",
        layers=[layer(laytype=laytype, specific_storage=0, specific_yield=0)],
        river={"enabled": 1, "layers": [{
            "layer": 1, "stage": "stage.map", "bottom": "bed.map",
            "conductance": 0, "mask": "rivers.map",
        }]},
    )
    assert config.layers[0].specific_storage == 0
    assert config.layers[0].specific_yield == 0


@pytest.mark.parametrize("key", ["specific_storage", "specific_yield"])
@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, ""])
def test_invalid_storage_constants(key, value):
    with pytest.raises(ValidationError):
        ModflowLayerConfiguration(**layer(**{key: value}))


def test_specific_yield_cannot_exceed_one():
    with pytest.raises(ValidationError):
        ModflowLayerConfiguration(**layer(specific_yield=1.01))


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, ""])
def test_invalid_river_conductance(value):
    with pytest.raises(ValidationError):
        ModflowRiverLayerConfiguration(
            layer=1, stage="stage.map", bottom="bed.map", conductance=value, mask="rivers.map"
        )


@pytest.mark.parametrize("value", [0, 2.5])
def test_constant_river_conductance_requires_spatial_mask(value):
    with pytest.raises(ValidationError, match="requires a 'mask'"):
        ModflowRiverLayerConfiguration(
            layer=1, stage="stage.map", bottom="bed.map", conductance=value
        )


@pytest.mark.parametrize("value", [
    {"map": "classes.map"}, {"table": "kh.tbl"},
    {"map": "", "table": "kh.tbl"}, {"map": "classes.map", "table": ""},
    {"map": "classes.map", "table": "kh.tbl", "typo": 1},
])
def test_lookup_requires_map_and_table(value):
    with pytest.raises(ValidationError):
        ModflowLayerConfiguration(**layer(horizontal_conductivity=value))


def test_three_independent_lookups_and_constants_resolve_and_roundtrip(tmp_path):
    absolute = str(tmp_path / "absolute.tbl")
    config = ModflowConfiguration(layers=[
        layer(horizontal_conductivity={"map": f"classes{i}.map", "table": f"kh{i}.tbl"})
        for i in range(1, 4)
    ], river={"enabled": 1, "layers": [{
        "layer": 3, "stage": "stage.map", "bottom": "bed.map",
        "conductance": 12, "mask": "rivers.map",
    }]})
    data = config.model_dump(mode="json")
    data["layers"][2]["horizontal_conductivity"]["table"] = absolute
    config = ModflowConfiguration.model_validate(data)
    resolved = config.resolve_paths(tmp_path)
    for i, item in enumerate(resolved.layers, 1):
        assert Path(item.horizontal_conductivity.map) == tmp_path / f"classes{i}.map"
        assert Path(item.horizontal_conductivity.table) == (
            Path(absolute) if i == 3 else tmp_path / f"kh{i}.tbl"
        )
        assert item.specific_storage == 0.00001
        assert item.specific_yield == 0.1
    assert resolved.river.layers[0].conductance == 12
    assert Path(resolved.river.layers[0].mask) == tmp_path / "rivers.map"
    assert ModflowConfiguration.model_validate_json(resolved.model_dump_json()) == resolved
    assert config.layers[0].horizontal_conductivity.map == "classes1.map"


def test_legacy_maps_remain_supported(tmp_path):
    config = ModflowConfiguration(layers=[layer(
        specific_storage="ss.map", specific_yield="sy.map"
    )], river={"enabled": 1, "layers": [{
        "layer": 1, "stage": "stage.map", "bottom": "bed.map", "conductance": "cond.map",
    }]})
    resolved = config.resolve_paths(tmp_path)
    assert Path(resolved.layers[0].horizontal_conductivity) == tmp_path / "kh.map"
    assert Path(resolved.layers[0].specific_storage) == tmp_path / "ss.map"
    assert Path(resolved.layers[0].specific_yield) == tmp_path / "sy.map"
    assert Path(resolved.river.layers[0].conductance) == tmp_path / "cond.map"
    assert resolved.river.layers[0].mask is None
