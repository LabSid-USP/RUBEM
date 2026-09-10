import shutil

import pcraster as pcr
import pytest

from rubem.configuration.modflow_configuration import ModflowConfiguration
from rubem.hydrological_processes._modflow import ModflowGroundwater

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("mf2005") is None, reason="mf2005 is required"),
]


@pytest.mark.parametrize("masked", [False, True])
@pytest.mark.parametrize("elevation,conductance,enabled,output", [
    (50, 4, 1, True), (56.18, 4, 1, True), (65, 4, 1, True),
    (50, 0, 1, True), (50, 4, 0, True), (50, 4, 1, False),
])
def test_drain_with_ghb_river_and_recharge(
    tmp_path, monkeypatch, masked, elevation, conductance, enabled, output
):
    monkeypatch.chdir(tmp_path)
    pixel = 0.0002945488721804391443
    pcr.setclone(3, 3, pixel, 0, 3 * pixel)
    mask = pcr.xcoordinate(pcr.spatial(pcr.boolean(1))) > pixel

    def raster(name, value, nominal=False):
        path = str(tmp_path / f"{name}.map")
        field = pcr.nominal(value) if nominal else pcr.scalar(value)
        pcr.report(pcr.ifthen(mask, field) if masked else pcr.spatial(field), path)
        return path

    config = ModflowConfiguration(
        enabled=1, bottom=raster("bottom", 0),
        layers=[{
            "name": "aquifer", "top": raster("top", 100),
            "boundary": raster("boundary", 1, nominal=True),
            "initial_head": raster("initial", 50), "laytype": 0,
            "horizontal_conductivity": raster("kh", 1),
            "vertical_conductivity": raster("kv", 1),
        }],
        dis={"steady_state": 1, "nstp": 1},
        solver={"hclose": 1e-8, "rclose": 1e-8, "damp": 1},
        river={"enabled": 1, "layers": [{
            "layer": 1, "stage": raster("stage", 50),
            "bottom": raster("bed", 10), "conductance": raster("rivcond", 2),
        }]},
        ghb={"enabled": 1, "layers": [{
            "layer": 1, "head": raster("external", 60),
            "conductance": raster("ghbcond", 3),
        }]},
        drain={"enabled": enabled, "layers": [{
            "layer": 1, "elevation": raster("drnelev", elevation),
            "conductance": raster("drncond", conductance),
        }]},
        output={"drain_flow": output},
    )
    model = ModflowGroundwater(config, 900)
    model.initialize(30)
    # RCH = 0.9 m3/day; GHB C=3, head=60; RIV C=2, stage=50.
    effective_cond = conductance if enabled and elevation < 56.18 else 0
    expected_head = (280.9 + effective_cond * elevation) / (5 + effective_cond)
    expected_drain = -effective_cond * max(expected_head - elevation, 0)
    expected_river = 2 * (50 - expected_head)
    for _ in range(2):
        result = model.run_timestep(pcr.spatial(pcr.scalar(30)), 30)
        assert result.converged
        assert pcr.cellvalue(result.heads[1], 2)[0] == pytest.approx(expected_head, abs=1e-4)
        assert pcr.cellvalue(result.baseflow_mm, 2)[0] == pytest.approx(
            max(-expected_river, 0) * 30 * 1000 / 900, abs=0.01
        )
        if enabled and output:
            assert pcr.cellvalue(result.drain_flow[1], 2)[0] == pytest.approx(expected_drain, abs=1e-4)
        else:
            assert result.drain_flow == {}
