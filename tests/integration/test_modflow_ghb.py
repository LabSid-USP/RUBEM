import shutil

import pcraster as pcr
import pytest

from rubem.configuration.modflow_configuration import ModflowConfiguration
from rubem.hydrological_processes._modflow import ModflowGroundwater

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("mf2005") is None, reason="mf2005 is required"),
]


@pytest.mark.parametrize("external_head, conductance", [(60, 3), (40, 3), (60, 0)])
@pytest.mark.parametrize("masked", [False, True])
@pytest.mark.parametrize("transient", [False, True])
@pytest.mark.parametrize("pixel_size", [30.0, 0.0002945488721804391443])
def test_ghb_river_equilibrium(
    tmp_path, monkeypatch, external_head, conductance, masked, transient, pixel_size
):
    """Check the metric recharge/storage balance independently of clone units."""
    monkeypatch.chdir(tmp_path)
    # PCG eliminates isolated cells; use connected cells with identical heads.
    pcr.setclone(3, 3, pixel_size, 0, 3 * pixel_size)
    mask = pcr.xcoordinate(pcr.spatial(pcr.boolean(1))) > pixel_size
    # 30 mm/month -> 0.001 m/day * 900 m2 = 0.9 m3/day per cell.
    recharge_flow = 0.9
    expected_head = 50.0

    def raster(name, value, nominal=False):
        path = tmp_path / f"{name}.map"
        value = pcr.nominal(value) if nominal else pcr.scalar(value)
        if masked:
            value = pcr.ifthen(mask, value)
        pcr.report(pcr.spatial(value), str(path))
        return str(path)

    config = ModflowConfiguration(
        enabled=1,
        bottom=raster("bottom", 0),
        layers=[{
            "name": "aquifer",
            "top": raster("top", 100),
            "boundary": raster("boundary", 1, nominal=True),
            "initial_head": raster("initial", 50),
            "horizontal_conductivity": raster("kh", 1),
            "vertical_conductivity": raster("kv", 1),
            "laytype": 1 if transient else 0,
            "specific_yield": raster("sy", 0.1),
        }],
        dis={"steady_state": 0 if transient else 1, "nstp": 1},
        wetting={"enabled": int(transient), "map": raster("wet", -0.1)},
        solver={"hclose": 1e-8, "rclose": 1e-8, "damp": 1},
        river={"enabled": 1, "layers": [{
            "layer": 1, "stage": raster("stage", 50),
            "bottom": raster("bed", 10), "conductance": raster("rivcond", 2),
        }]},
        ghb={"enabled": 1, "layers": [{
            "layer": 1, "head": raster("external", external_head),
            "conductance": raster("ghbcond", conductance),
        }]},
    )
    groundwater = ModflowGroundwater(config, cell_area_m2=900)
    groundwater.initialize(first_period_days=30)
    for _ in range(2):
        # Sy * area / duration is the implicit storage coefficient in m2/day.
        storage_coefficient = 0.1 * 900 / 30 if transient else 0.0
        expected_head = (
            conductance * external_head + 2 * 50 + recharge_flow
            + storage_coefficient * expected_head
        ) / (conductance + 2 + storage_coefficient)
        expected_ghb_flow = conductance * (external_head - expected_head)
        expected_river_flow = 2 * (50 - expected_head)
        recharge = pcr.ifthen(mask, pcr.scalar(30)) if masked else pcr.spatial(pcr.scalar(30))
        result = groundwater.run_timestep(recharge, 30)
        assert result.converged
        assert pcr.cellvalue(result.heads[1], 2)[0] == pytest.approx(expected_head)
        river_flow = pcr.cellvalue(result.net_river_leakage_m3_per_day, 2)[0]
        assert river_flow == pytest.approx(expected_river_flow, abs=1e-4)
        # Apply the same flow tolerance after conversion from m3/day to mm.
        assert pcr.cellvalue(result.baseflow_mm, 2)[0] == pytest.approx(
            max(-expected_river_flow, 0) * 30 * 1000 / 900, abs=1e-4 * 30 * 1000 / 900
        )
        if conductance:
            ghb_flow = pcr.cellvalue(groundwater.mf.getGeneralHeadLeakage(1), 2)[0]
            assert ghb_flow == pytest.approx(expected_ghb_flow, abs=1e-4)
