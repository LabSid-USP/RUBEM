from unittest.mock import Mock

import numpy as np
import pcraster as pcr
import pytest

from rubem.hydrological_processes._modflow import ModflowGroundwater

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("pixel_size", [30.0, 0.0002945488721804391443])
@pytest.mark.parametrize("metric_width", [30.0, 50.0])
def test_metric_dimensions_follow_rubem_grid(pixel_size, metric_width):
    pcr.setclone(3, 5, pixel_size, 0, 3 * pixel_size)
    model = ModflowGroundwater({}, metric_width ** 2)
    model.mf = Mock()
    model._setup_cell_dimensions()
    model.mf.setRowWidth.assert_called_once_with([metric_width] * 3)
    model.mf.setColumnWidth.assert_called_once_with([metric_width] * 5)
    assert pcr.clone().cellSize() == pixel_size


@pytest.mark.parametrize("area", [0, -1, np.nan, np.inf])
def test_invalid_metric_area_is_rejected(area):
    with pytest.raises(ValueError, match="finite and greater than zero"):
        ModflowGroundwater({}, area)


@pytest.fixture
def maps(tmp_path):
    pcr.setclone(2, 2, 30, 0, 60)

    def write(name, values):
        path = str(tmp_path / f"{name}.map")
        array = np.asarray(values, dtype=float).reshape(2, 2)
        pcr.report(pcr.numpy2pcr(pcr.Scalar, array, np.nan), path)
        return path

    return write


def test_geometry_fills_only_columns_inactive_in_all_layers(maps):
    boundary = maps("boundary", [np.nan, 1, 0, -1])
    bottom = maps("bottom", [np.nan, 10, 500, 20])
    first_top = maps("top1", [np.nan, 30, np.nan, 40])
    second_top = maps("top2", [np.nan, 50, -50, 60])
    model = ModflowGroundwater({
        "bottom": bottom,
        "layers": [
            {"boundary": boundary, "top": first_top},
            {"boundary": boundary, "top": second_top},
        ],
    }, 900)
    model.mf = Mock()
    model._setup_geometry()
    base, top = model.mf.createBottomLayer.call_args.args
    upper = model.mf.addLayer.call_args.args[0]
    for field, expected in [
        (base, [[0, 10], [0, 20]]),
        (top, [[1, 30], [1, 40]]),
        (upper, [[2, 50], [2, 60]]),
        (model._boundaries[1], [[0, 1], [0, -1]]),
    ]:
        np.testing.assert_array_equal(pcr.pcr2numpy(field, np.nan), expected)
    # Preparation leaves the source map untouched.
    assert np.isnan(pcr.pcr2numpy(pcr.readmap(bottom), np.nan)[0, 0])


@pytest.mark.parametrize("boundary_value", [1, -1])
@pytest.mark.parametrize("surface", ["bottom", "top"])
def test_missing_elevation_in_active_column_is_rejected(maps, boundary_value, surface):
    boundary = maps("boundary", [boundary_value, 1, 1, 1])
    bottom = maps("bottom", [np.nan if surface == "bottom" else 0, 0, 0, 0])
    top = maps("top", [np.nan if surface == "top" else 10, 10, 10, 10])
    model = ModflowGroundwater({
        "bottom": bottom, "layers": [{"boundary": boundary, "top": top}],
    }, 900)
    model.mf = Mock()
    with pytest.raises(ValueError, match="row 1, column 1"):
        model._setup_geometry()
    model.mf.createBottomLayer.assert_not_called()


def test_upper_active_layer_requires_geometry_even_when_lower_is_inactive(maps):
    model = ModflowGroundwater({
        "bottom": maps("bottom", [np.nan, 0, 0, 0]),
        "layers": [
            {"boundary": maps("bound1", [0, 1, 1, 1]), "top": maps("top1", [10]*4)},
            {"boundary": maps("bound2", [1]*4), "top": maps("top2", [20]*4)},
        ],
    }, 900)
    model.mf = Mock()
    with pytest.raises(ValueError, match="MODFLOW.bottom.*row 1, column 1"):
        model._setup_geometry()


def test_inverted_active_geometry_is_rejected(maps):
    model = ModflowGroundwater({
        "bottom": maps("bottom", [10]*4),
        "layers": [{"boundary": maps("boundary", [1]*4), "top": maps("top", [5]*4)}],
    }, 900)
    model.mf = Mock()
    with pytest.raises(ValueError, match="top must be above"):
        model._setup_geometry()


def test_required_property_is_not_filled(maps):
    model = ModflowGroundwater({}, 900)
    path = maps("head", [np.nan, 10, 10, 10])
    with pytest.raises(ValueError, match="initial_head.*row 1, column 1"):
        model._read_scalar_input(path, "initial_head", np.ones((2, 2), dtype=bool))


def test_sparse_stress_maps_require_head_only_where_conductance_is_positive(maps):
    model = ModflowGroundwater({}, 900)
    model._boundaries[1] = pcr.nominal(pcr.readmap(maps("boundary", [0, 1, 1, 1])))
    conductance = maps("cond", [9, np.nan, 0, 2])
    head = maps("head", [np.nan, np.nan, np.nan, 50])
    cond, heads = model._read_stress_inputs("GHB", 1, conductance, head=head)
    np.testing.assert_array_equal(pcr.pcr2numpy(cond, np.nan), [[0, 0], [0, 2]])
    np.testing.assert_array_equal(pcr.pcr2numpy(heads["head"], np.nan), [[0, 0], [0, 50]])
    with pytest.raises(ValueError, match="GHB.head.*row 2, column 2"):
        model._read_stress_inputs(
            "GHB", 1, conductance, head=maps("missing_head", [np.nan]*4)
        )
