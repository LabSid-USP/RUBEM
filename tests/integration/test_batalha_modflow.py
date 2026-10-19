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


FIXES = ("a1", "a2", "d")
TIGHT = {"hclose": 1.0, "rclose": 1.0}


@pytest.mark.parametrize(
    ("profile", "ghb"), (("scientist", None), ("answered", "none"), ("answered", "split"))
)
def test_prepared_batalha_converges_and_conserves_river_exchange(
    dataset_dir, tmp_path, monkeypatch, restore_logging, profile, ghb
):
    """Two months with the same explicit preparation as the example.

    This checks a numerical sensitivity scenario, not calibrated accuracy.
    Capture each listing before the framework cleans its MODFLOW directory.
    The scientist's profile keeps the -888 sentinels of the two lower layers,
    which the PR refuses unless blocking problems are allowed, and closes at
    the delivered 20 m / 10 m3/day. The answered profile fills them and runs
    without the bypass; with the corrected conductivities the delivered
    criterion no longer closes the first substep (the wet/dry cycle at cell
    (15, 231)), so it runs with the three wetting repairs, rewetting from
    below only and 1 m / 1 m3/day: measured on 2026-10-18, that closes with a
    budget discrepancy below 0.1 % until month 12, where seasonal rewetting
    stops it; the two months here are well inside that window.
    """
    dataset = dataset_dir / "batalha_basin"
    if not (dataset / "bauru_modflow.json").is_file():
        pytest.skip("The Batalha MODFLOW inputs are not present in RUBEM_DATASET_DIR.")
    pytest.importorskip("scipy.ndimage", reason="Batalha head preparation requires SciPy.")
    example = Path(__file__).parents[2] / "examples/batalha_modflow/prepare.py"
    prepare = runpy.run_path(str(example))["prepare"]
    if profile == "scientist":
        configs = prepare(dataset, tmp_path, months=2, profile=profile)
        with pytest.raises(ConfigurationError):
            ModelConfiguration(configs["feat_356_modflow_coupling"])
        config = ModelConfiguration(
            configs["feat_356_modflow_coupling"], allow_blocking_problems=True
        )
        assert any(problem.blocking for problem in config.problems)
    else:
        configs = prepare(
            dataset,
            tmp_path,
            months=2,
            profile=profile,
            ghb=ghb,
            wetting_fixes=FIXES,
            wetting="below",
            solver=TIGHT,
        )
        config = ModelConfiguration(configs["feat_356_modflow_coupling"])
        assert not any(problem.blocking for problem in config.problems)
    recorded = []
    run_step = ModflowGroundwater.run_step

    class RecordingExtension:
        """Copy the listing after every native run: each substep overwrites it."""

        def __init__(self, inner, directory):
            self._inner, self._directory = inner, directory

        def __getattr__(self, item):
            value = getattr(self._inner, item)
            if item != "run":
                return value

            def run(*args, **kwargs):
                try:
                    return value(*args, **kwargs)
                finally:
                    recorded.append((self._directory / "pcrmf.lst").read_text())

            return run

    def record_listings(self, *args, **kwargs):
        if not isinstance(self.mf, RecordingExtension):
            self.mf = RecordingExtension(self.mf, self.run_directory)
        return run_step(self, *args, **kwargs)

    monkeypatch.setattr(ModflowGroundwater, "run_step", record_listings)
    DynamicFrameworkWrapper.load(config).run()
    nstp = config.modflow.dis.nstp
    assert len(recorded) == 2 * nstp, "one listing per native run (substep)"
    for listing in recorded:
        assert "FAILURE TO MEET SOLVER CONVERGENCE CRITERIA" not in listing
        discrepancies = re.findall(r"PERCENT DISCREPANCY\s*=\s*([-+\d.Ee]+)", listing)
        assert discrepancies, "MODFLOW did not report its water budget."
        assert max(abs(float(value)) for value in discrepancies) < 0.1
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
        assert domain.sum() > 100_000, "the whole active clone carries a baseflow value"
        assert np.all(np.isfinite(discharge[domain]))
        assert np.all(discharge[domain] >= 0)
        assert np.all(infiltration[domain] >= 0)
        assert (discharge[domain] > 0).sum() > 1_000, "the rivers drain the aquifer"
        assert discharge[domain].sum() * days > 1e5, "aquifer-to-river volume of the month [m3]"
        np.testing.assert_allclose(
            baseflow[domain], discharge[domain] * days * 1000 / 900, rtol=2e-6, atol=1e-5
        )
        np.testing.assert_allclose(
            net[domain], infiltration[domain] - discharge[domain], rtol=2e-6, atol=1e-5
        )
        for layer in (1, 2, 3):
            head = values(f"mfh{layer}", step)
            finite = head[np.isfinite(head)]
            boundary = pcr.pcr2numpy(pcr.readmap(str(config.modflow.layers[layer - 1].boundary)), 0)
            active = int((boundary != 0).sum())
            assert active > 100_000
            assert finite.size >= 0.95 * active, "heads cover the active cells (dry ones excepted)"
            assert np.all(finite > 0), "A head output contains a dry/no-data sentinel."

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["profile"] == profile
    assert "bauru_modflow.json" in manifest["source_sha256"]
    assert "input/modflow/bound3.map" in manifest["source_sha256"]
    if profile == "answered":
        assert manifest["answers"]["1_conductivity_suffixes"] == {
            "lower": 3,
            "middle": 2,
            "upper": 1,
        }
        assert manifest["answers"]["8_11_ghb"] == ghb
        lower, middle, upper = manifest["layers"]
        assert (lower["heads_filled"], middle["heads_filled"]) == (18, 277)
        assert upper["below_bottom_cells"] == [[15, 231]]
        assert upper["clipped_to_surface"] == 20419
        assert upper["deactivated_cells"] == [[15, 231]]
        assert manifest["answers"]["6_wetting_strategy"] == "below"
        assert manifest["wetting"]["ihdwet"] == 1
        assert (manifest["solver"]["hclose"], manifest["solver"]["rclose"]) == (1.0, 1.0)
