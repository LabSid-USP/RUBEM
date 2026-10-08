"""Optional Batalha exercise using documented, explicitly prepared inputs."""

import json
import re
import runpy
from pathlib import Path

import numpy as np
import pcraster as pcr
import pytest

from rubem._deps import resolve_mf2005
from rubem.configuration._problems import ConfigurationError
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.core import DynamicFrameworkWrapper
from rubem.hydrological_processes._modflow import ModflowGroundwater

pytestmark = [
    pytest.mark.integration,
    pytest.mark.dataset,
    pytest.mark.slow,
    pytest.mark.skipif(resolve_mf2005() is None, reason="mf2005 is required"),
]


@pytest.mark.parametrize(
    ("profile", "wetting"),
    (("reconstructed", "off"), ("reconstructed", "below"), ("scientist", None)),
)
def test_prepared_batalha_converges_and_conserves_river_exchange(
    dataset_dir, tmp_path, monkeypatch, restore_logging, profile, wetting
):
    """Two months with the same explicit initialization as the example.

    This checks a numerical sensitivity scenario, not calibrated accuracy.
    Capture each listing before the framework cleans its MODFLOW directory.
    The scientist's profile keeps the -888 sentinels of the two lower layers,
    which the PR refuses unless blocking problems are allowed.
    """
    dataset = dataset_dir / "batalha_basin"
    if not (dataset / "bauru_modflow.json").is_file():
        pytest.skip("The Batalha MODFLOW inputs are not present in RUBEM_DATASET_DIR.")
    pytest.importorskip("scipy.ndimage", reason="Batalha head preparation requires SciPy.")
    example = Path(__file__).parents[2] / "examples/batalha_modflow/prepare.py"
    prepare = runpy.run_path(str(example))["prepare"]
    if profile == "scientist":
        if not (dataset / "bauru_modflow(patched).json").is_file():
            pytest.skip("The scientist's Batalha configuration is not present.")
        configs = prepare(dataset, tmp_path, months=2, profile=profile)
        with pytest.raises(ConfigurationError):
            ModelConfiguration(configs["feat_356_modflow_coupling"])
        config = ModelConfiguration(
            configs["feat_356_modflow_coupling"], allow_blocking_problems=True
        )
        assert any(problem.blocking for problem in config.problems)
    else:
        options = (
            dict(wetdry_threshold=10, wetfct=0.1, ihdwet=1, mxiter=200)
            if wetting == "below"
            else {}
        )
        configs = prepare(dataset, tmp_path, months=2, wetting=wetting, **options)
        with pytest.raises(ConfigurationError):
            ModelConfiguration(tmp_path / "feat_356_modflow_coupling-original-heads.json")
        config = ModelConfiguration(configs["feat_356_modflow_coupling"])
        assert not any(problem.blocking for problem in config.problems)
    recorded = []
    run_step = ModflowGroundwater.run_step

    def record_listing(self, *args, **kwargs):
        result = run_step(self, *args, **kwargs)
        listing = (self.run_directory / "pcrmf.lst").read_text()
        assert "FAILURE TO MEET SOLVER CONVERGENCE CRITERIA" not in listing
        discrepancies = re.findall(r"PERCENT DISCREPANCY\s*=\s*([-+\d.Ee]+)", listing)
        assert discrepancies, "MODFLOW did not report its water budget."
        assert max(abs(float(value)) for value in discrepancies) < 0.1
        recorded.append(listing)
        return result

    monkeypatch.setattr(ModflowGroundwater, "run_step", record_listing)
    DynamicFrameworkWrapper.load(config).run()
    assert len(recorded) == 2
    output = tmp_path / "runs/feat_356_modflow_coupling"

    def values(prefix, step):
        name = f"{prefix}{step:0{11 - len(prefix)}d}"
        path = output / f"{name[:8]}.{name[8:]}"
        return pcr.pcr2numpy(pcr.scalar(pcr.readmap(str(path))), np.nan)

    for step, days in ((1, 31), (2, 30)):
        baseflow = values("bfw", step)
        discharge = values("mfaq2rv", step)
        infiltration = values("mfrv2aq", step)
        net = values("mfrvnet", step)
        domain = np.isfinite(baseflow)
        assert domain.any()
        assert np.all(np.isfinite(discharge[domain]))
        assert np.all(discharge[domain] >= 0)
        assert np.all(infiltration[domain] >= 0)
        np.testing.assert_allclose(
            baseflow[domain], discharge[domain] * days * 1000 / 900, rtol=2e-6, atol=1e-5
        )
        np.testing.assert_allclose(
            net[domain], infiltration[domain] - discharge[domain], rtol=2e-6, atol=1e-5
        )
        for layer in (1, 2, 3):
            head = values(f"mfh{layer}", step)
            finite = head[np.isfinite(head)]
            assert finite.size
            assert np.all(finite > 0), "A head output contains a dry/no-data sentinel."

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    if profile == "scientist":
        assert manifest["profile"] == "scientist"
        assert "bauru_modflow(patched).json" in manifest["source_sha256"]
        assert "input/modflow/bound3.map" in manifest["source_sha256"]
    else:
        assert sum(manifest["river_cells_bottom_to_top"]) == 2209
        assert manifest["river_cells_excluded"] == 68
