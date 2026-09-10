import shutil

import numpy as np
import pcraster as pcr
import pytest

from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.model_configuration_file import ModelConfigurationFile
from rubem.configuration.model_configuration_file_v1 import ModelConfigurationFileV1
from rubem.core import DynamicFrameworkWrapper
from rubem.hydrological_processes import Interception
from tests.helpers.synthetic import series_name, write_synthetic_dataset

pytestmark = pytest.mark.integration


def run_case(root, monkeypatch, table_values, coupled, v1):
    root.mkdir()
    # MODFLOW writes its temporary files in the working directory.
    monkeypatch.chdir(root)
    config = write_synthetic_dataset(str(root))
    if table_values is not None:
        table = root / "lai.txt"
        table.write_text(f"3 {table_values[0]}\n4 {table_values[1]}\n", encoding="utf8")
        config["TABLES"]["lai_max"] = str(table)
        config["CONSTANTS"]["lai_max_from_table"] = True

    if coupled:
        def raster(name, value, nominal=False):
            path = str(root / f"{name}.map")
            field = pcr.nominal(value) if nominal else pcr.scalar(value)
            pcr.report(pcr.spatial(field), path)
            return path

        config["MODFLOW"] = {
            "enabled": 1, "bottom": raster("bottom", 0),
            "layers": [{
                "name": "aquifer", "top": raster("top", 200),
                "boundary": raster("boundary", 1, nominal=True),
                "initial_head": raster("head", 50), "laytype": 0,
                "horizontal_conductivity": raster("kh", 1),
                "vertical_conductivity": raster("kv", 1),
            }],
            "dis": {"steady_state": 1, "nstp": 1},
            "solver": {"hclose": 1e-6, "rclose": 1e-6, "damp": 1},
            "river": {"enabled": 1, "layers": [{
                "layer": 1, "stage": raster("stage", 50),
                "bottom": raster("bed", 10), "conductance": raster("rivcond", 100),
            }]},
            "ghb": {"enabled": 1, "layers": [{
                "layer": 1, "head": raster("external", 55),
                "conductance": raster("ghbcond", 100),
            }]},
            "drain": {"enabled": 1, "layers": [{
                "layer": 1, "elevation": raster("drnelev", 52),
                "conductance": raster("drncond", 10),
            }]},
            "output": {"drain_flow": True},
        }
    if v1:
        config = ModelConfigurationFileV1.from_legacy(
            ModelConfigurationFile.model_validate(config)
        ).to_dict()
    DynamicFrameworkWrapper(ModelConfiguration(config)).run()
    return root / "out"


@pytest.mark.parametrize("v1", [False, True])
@pytest.mark.parametrize("coupled", [False, True])
def test_fixed_lai_equals_constant_table_and_modflow_outputs_survive(tmp_path, monkeypatch, coupled, v1):
    if coupled and shutil.which("mf2005") is None:
        pytest.skip("mf2005 is required")
    fixed = run_case(tmp_path / "fixed", monkeypatch, None, coupled, v1)
    table = run_case(tmp_path / "table", monkeypatch, (12, 12), coupled, v1)
    prefixes = ["itp", "rec", "bfw", "rnf"] + (["mfh1", "mfdrn1"] if coupled else [])
    for prefix in prefixes:
        for step in (1, 2):
            name = series_name(prefix, step)
            first = pcr.pcr2numpy(pcr.readmap(str(fixed / name)), np.nan)
            second = pcr.pcr2numpy(pcr.readmap(str(table / name)), np.nan)
            np.testing.assert_array_equal(first, second)


@pytest.mark.parametrize("v1", [False, True])
def test_table_uses_current_landuse_each_timestep(tmp_path, monkeypatch, v1):
    original = Interception.get_leaf_area_index
    seen = []

    def record(fpar, fpar_max, maximum):
        seen.append(pcr.cellvalue(maximum, 1)[0])
        return original(fpar, fpar_max, maximum)

    monkeypatch.setattr(Interception, "get_leaf_area_index", staticmethod(record))
    run_case(tmp_path / "table", monkeypatch, (4, 6), False, v1)
    assert seen == [4.0, 6.0]
