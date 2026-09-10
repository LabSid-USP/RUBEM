from unittest.mock import Mock

import numpy as np
import pcraster as pcr
import pytest

from rubem.configuration.modflow_configuration import ModflowConductivityLookup
from rubem.hydrological_processes._modflow import ModflowGroundwater

pytestmark = pytest.mark.unit


@pytest.fixture
def maps(tmp_path):
    pcr.setclone(2, 2, 30, 0, 60)

    def write(name, values, nominal=False):
        path = str(tmp_path / f"{name}.map")
        array = np.asarray(values, dtype=float).reshape(2, 2)
        raster = pcr.numpy2pcr(pcr.Scalar, array, np.nan)
        pcr.report(pcr.nominal(raster) if nominal else raster, path)
        return path

    return write


@pytest.mark.parametrize("value", [0, 0.00001, 0.2])
def test_constant_is_a_complete_spatial_field(maps, value):
    result = ModflowGroundwater({}, 900)._read_scalar_input(value, "ss")
    assert result.isSpatial()
    np.testing.assert_allclose(pcr.pcr2numpy(result, np.nan), np.full((2, 2), value))


@pytest.mark.parametrize("as_model", [False, True])
def test_lookup_rejects_unmapped_active_class_but_allows_inactive_nodata(maps, tmp_path, as_model):
    classes = maps("classes", [np.nan, 1, 2, 3], nominal=True)
    table = tmp_path / "kh.tbl"
    table.write_text("1 0.25\n2 4.5\n", encoding="ascii")
    source = {"map": classes, "table": str(table)}
    if as_model:
        source = ModflowConductivityLookup(**source)
    model = ModflowGroundwater({}, 900)
    active = np.array([[False, True], [True, False]])
    result = model._read_scalar_input(source, "kh", active, fill=1)
    np.testing.assert_array_equal(pcr.pcr2numpy(result, np.nan), [[1, 0.25], [4.5, 1]])
    active[1, 1] = True
    with pytest.raises(ValueError, match="class coverage.*row 2, column 2"):
        model._read_scalar_input(source, "kh", active, fill=1)
    # A new evaluation reads the current table after a calibrator changes it.
    table.write_text("1 2\n2 8\n3 12\n", encoding="ascii")
    result = model._read_scalar_input(source, "kh", active, fill=1)
    np.testing.assert_array_equal(pcr.pcr2numpy(result, np.nan), [[1, 2], [8, 12]])


@pytest.mark.parametrize("value", [0, -0.1])
def test_lookup_rejects_nonpositive_active_conductivity(maps, tmp_path, value):
    table = tmp_path / "kh.tbl"
    table.write_text(f"1 {value}\n", encoding="ascii")
    with pytest.raises(ValueError, match="conductivity must be positive"):
        ModflowGroundwater({}, 900)._read_scalar_input(
            {"map": maps("classes", [1]*4, nominal=True), "table": str(table)},
            "kh", np.ones((2, 2), dtype=bool),
        )


def test_lookup_requires_nominal_map(maps, tmp_path):
    table = tmp_path / "kh.tbl"
    table.write_text("1 2\n", encoding="ascii")
    with pytest.raises(ValueError, match="nominal"):
        ModflowGroundwater({}, 900)._read_scalar_input(
            {"map": maps("classes", [1.5]*4), "table": str(table)}, "kh"
        )


@pytest.mark.parametrize("conductance", [0, 12])
def test_constant_river_uses_positive_mask_and_bas_cells(maps, conductance):
    config = {"layers": [{}], "river": {"enabled": 1, "layers": [{
        "layer": 1, "stage": maps("stage", [np.nan, np.nan, np.nan, 50]),
        "bottom": maps("bottom", [np.nan, np.nan, np.nan, 40]),
        "conductance": conductance, "mask": maps("mask", [5, np.nan, 0, 2]),
    }]}}
    model = ModflowGroundwater(config, 900)
    model.mf = Mock()
    model._boundaries[1] = pcr.nominal(pcr.readmap(maps("bas", [0, 1, 1, 1])))
    model._set_river_stress()
    stage, bottom, cond, layer = model.mf.setRiver.call_args.args
    assert layer == 1
    np.testing.assert_array_equal(pcr.pcr2numpy(cond, np.nan), [[0, 0], [0, conductance]])
    assert pcr.cellvalue(stage, 4)[0] == 50
    assert pcr.cellvalue(bottom, 4)[0] == 40


def test_constant_river_requires_stage_at_selected_cells(maps):
    model = ModflowGroundwater({}, 900)
    model._boundaries[1] = pcr.spatial(pcr.nominal(1))
    with pytest.raises(ValueError, match="river.stage.*row 2, column 2"):
        model._read_stress_inputs(
            "river", 1, 2, mask=maps("mask", [0, 0, 0, 1]),
            stage=maps("stage", [np.nan]*4),
        )
