from pathlib import Path

import pytest
from pydantic import ValidationError

from rubem.configuration.input_table_files import TABLE_FIELDS, InputTableFiles
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.model_configuration_file import ModelConfigurationFile
from rubem.configuration.model_configuration_file_v1 import ModelConfigurationFileV1
from tests.helpers.synthetic import write_synthetic_dataset

pytestmark = pytest.mark.unit


@pytest.fixture
def legacy(tmp_path):
    config = write_synthetic_dataset(str(tmp_path))
    table = tmp_path / "lai_max.txt"
    table.write_text("3 4.0\n4 6.0\n", encoding="utf8")
    config["TABLES"]["lai_max"] = str(table)
    config["CONSTANTS"]["lai_max_from_table"] = True
    return config


@pytest.mark.parametrize("v1", [False, True])
def test_lai_table_reaches_runtime_configuration(legacy, v1):
    config = legacy
    if v1:
        config = ModelConfigurationFileV1.from_legacy(
            ModelConfigurationFile.model_validate(legacy)
        ).to_dict()
    runtime = ModelConfiguration(config)
    assert runtime.constants.leaf_area_interception_max_from_table is True
    assert runtime.lookuptable_files.lai_max == legacy["TABLES"]["lai_max"]


@pytest.mark.parametrize("v1", [False, True])
def test_fixed_lai_remains_default(legacy, v1):
    del legacy["CONSTANTS"]["lai_max_from_table"]
    del legacy["TABLES"]["lai_max"]
    config = legacy if not v1 else ModelConfigurationFileV1.from_legacy(
        ModelConfigurationFile.model_validate(legacy)
    ).to_dict()
    runtime = ModelConfiguration(config)
    assert runtime.constants.leaf_area_interception_max_from_table is False
    assert runtime.lookuptable_files.lai_max is None
    assert runtime.constants.leaf_area_interception_max == legacy["CONSTANTS"]["lai_max"]


@pytest.mark.parametrize("v1", [False, True])
def test_enabled_table_requires_a_path(legacy, v1):
    if v1:
        doc = ModelConfigurationFileV1.from_legacy(
            ModelConfigurationFile.model_validate(legacy)
        ).to_dict()
        del doc["lookup_tables"]["lai_max"]
        model = ModelConfigurationFileV1
    else:
        doc = legacy
        del doc["TABLES"]["lai_max"]
        model = ModelConfigurationFile
    with pytest.raises(ValidationError, match="requires .*lai_max"):
        model.model_validate(doc)


def test_roundtrip_and_relative_paths_keep_modflow(legacy, tmp_path):
    legacy["MODFLOW"] = {
        "ghb": {"enabled": 1, "layers": [
            {"layer": 1, "head": "ghb.map", "conductance": "ghbc.map"},
        ]},
        "drain": {"enabled": 1, "layers": [
            {"layer": 1, "elevation": "drn.map", "conductance": "drnc.map"},
        ]},
    }
    legacy["TABLES"]["lai_max"] = "lai_max.txt"
    source = ModelConfigurationFile.model_validate(legacy)
    v1 = ModelConfigurationFileV1.from_legacy(source)
    roundtrip = v1.to_legacy()
    assert roundtrip.constants.lai_max_from_table is True
    assert roundtrip.tables.lai_max == "lai_max.txt"
    assert roundtrip.modflow == source.modflow
    for resolved in [source.resolve_paths(tmp_path), v1.resolve_paths(tmp_path)]:
        tables = resolved.tables if isinstance(resolved, ModelConfigurationFile) else resolved.lookup_tables
        assert Path(tables.lai_max) == tmp_path / "lai_max.txt"
        assert Path(resolved.modflow.ghb.layers[0].head) == tmp_path / "ghb.map"
        assert Path(resolved.modflow.drain.layers[0].elevation) == tmp_path / "drn.map"


def test_optional_table_normalizes_path_and_validates_file(tmp_path):
    path = tmp_path / "table.txt"
    path.write_text("3 4.0\n", encoding="utf8")
    required = dict.fromkeys(TABLE_FIELDS, str(path))
    assert InputTableFiles(**required, lai_max=path).lai_max == str(path)
    with pytest.raises(FileNotFoundError):
        InputTableFiles(**required, lai_max=tmp_path / "missing.txt")
    empty = tmp_path / "empty.txt"
    empty.touch()
    with pytest.raises(ValueError, match="Empty input lookuptable"):
        InputTableFiles(**required, lai_max=empty)
