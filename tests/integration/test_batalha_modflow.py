"""Optional Batalha exercise using documented, explicitly prepared inputs.

The Batalha dataset is the scientist's unpublished delivery of 2026-11-03,
not one of the published datasets: CI never sets ``RUBEM_DATASET_DIR``, so
this module always skips there, and the CI signal for the coupling is the
unit and integration tests that drive ``mf2005`` on synthetic grids. The
layout it expects under ``RUBEM_DATASET_DIR`` and the SHA-256 manifest of the
files it reads are in ``examples/batalha_modflow/README.md``.
"""

import json
import re
import runpy
import warnings
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
EXAMPLE = Path(__file__).parents[2] / "examples/batalha_modflow"
SOURCE = "bauru_modflow_t_ini_jul25_hist_x065.json"
"""The delivered configuration, pinned by name: the delivery names the series it reads."""
MAX_PERCENT_DISCREPANCY = 1.0
"""The closure the scientist accepted on 2026-10-26: "o que tem menor discrepância (< 1%)".

Answer to item 9 of ``perguntas-cientista-2026-10-26 (respondido).docx``.
"""


class DeliveryCopyWarning(UserWarning):
    """The run read files whose bytes are not those of the 2026-11-03 delivery manifest."""


@pytest.mark.parametrize(
    ("profile", "ghb"), (("scientist", None), ("answered", "none"), ("answered", "split"))
)
def test_prepared_batalha_converges_and_conserves_river_exchange(
    dataset_dir, tmp_path, monkeypatch, restore_logging, record_property, profile, ghb
):
    """Two months with the same explicit preparation as the example.

    This checks a numerical sensitivity scenario, not calibrated accuracy.
    Capture each listing before the framework cleans its MODFLOW directory.
    Every listing must converge and close its water budget within the 1 %
    the scientist accepted on 2026-10-26; that bound is a numerical sanity
    check, not a measure of accuracy. The largest PERCENT DISCREPANCY
    measured is 0.16 % in the first stress period of the delivery of
    2026-09-23 (NSTP 5, rising 0.02, 0.06, 0.11, 0.13, 0.16 %, then 0.01 to
    0.06 % in the second). In this two-month window on the delivery of
    2026-11-03 it is at most 0.02 % in the three cases (measured 2026-11-03);
    over longer windows the scientist's own configuration reaches 0.11 % (24
    months, 2026-10-18) and 0.12 % (the first 24 of 300 months, 2026-11-03).
    Each case records its maxima by native run as the
    ``percent_discrepancy_by_run`` property.
    The inputs are compared with the committed SHA-256 manifest of the
    2026-11-03 delivery: on another copy the test does not fail for that
    reason but warns with the differing paths, and the cell counts below,
    which hold for those exact bytes, are only asserted on a matching copy.
    The scientist's profile keeps the -888 sentinels of the two lower layers,
    which the PR refuses unless blocking problems are allowed, and closes at
    the delivered 20 m / 10 m3/day. The answered profile fills them and runs
    without the bypass; with the corrected conductivities the delivered
    criterion no longer closes the first substep (the wet/dry cycle at cell
    (15, 231)), so it runs with the three wetting repairs, rewetting from
    below only and 1 m / 1 m3/day: measured on 2026-10-18 over the earlier
    24-month series, that closes with a budget discrepancy below 0.1 % until
    month 12 with GHB off and month 9 with GHB split, where seasonal
    rewetting stops it; the two months here are well inside that window.
    """
    dataset = (dataset_dir / "batalha_basin").resolve()
    source = dataset / SOURCE
    if not source.is_file():
        pytest.skip(
            f"{source} is missing: RUBEM_DATASET_DIR must hold batalha_basin/ with {SOURCE} "
            "(from batalha_basin.zip) beside input/ (from batalha_basin_hist.zip); see "
            "examples/batalha_modflow/README.md."
        )
    pytest.importorskip("scipy.ndimage", reason="Batalha head preparation requires SciPy.")
    # The delivered series may start years before August 2023 (the historical dataset of
    # 2026-10-29 starts in August 2000): the window's first month is that source step.
    day, month, year = (
        int(x) for x in json.loads(source.read_text())["SIM_TIME"]["start"].split("/")
    )
    first_step = (2023 - year) * 12 + (8 - month) + 1
    assert day == 1 and first_step >= 1
    window = dict(source=source, months=2, first_step=first_step)
    preparer = runpy.run_path(str(EXAMPLE / "prepare.py"))
    prepare = preparer["prepare"]
    if profile == "scientist":
        configs = prepare(dataset, tmp_path, profile=profile, **window)
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
            profile=profile,
            ghb=ghb,
            wetting_fixes=FIXES,
            wetting="below",
            solver=TIGHT,
            station=(137, 241),
            **window,
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
    worst = []
    for listing in recorded:
        assert "FAILURE TO MEET SOLVER CONVERGENCE CRITERIA" not in listing
        discrepancies = re.findall(r"PERCENT DISCREPANCY\s*=\s*([-+\d.Ee]+)", listing)
        assert discrepancies, "MODFLOW did not report its water budget."
        worst.append(max(abs(float(value)) for value in discrepancies))
    record_property("percent_discrepancy_by_run", worst)
    assert max(worst) < MAX_PERCENT_DISCREPANCY, f"by native run: {worst}"
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
    assert source.name in manifest["source_sha256"]
    assert "input/modflow/bound3.map" in manifest["source_sha256"]
    assert manifest["window"] == {"start": "01/08/2023", "end": "01/09/2023"}
    if first_step > 1:
        assert manifest["series"]["prec"]["links"] == {"1": first_step, "2": first_step + 1}
    expected = [
        path.relative_to(dataset).as_posix()
        for path in preparer["delivery_files"](dataset, source, first_step=first_step, months=2)
    ]
    departures = preparer["compare_with_delivery"](
        manifest["source_sha256"],
        expected,
        preparer["read_sha256_manifest"](EXAMPLE / "delivery-2026-11-03.sha256"),
    )
    delivered = not any(departures.values())
    record_property("delivery_2026_11_03", delivered)
    if not delivered:
        warnings.warn(
            DeliveryCopyWarning(
                "This verdict is on a copy that departs from the 2026-11-03 delivery "
                "manifest (examples/batalha_modflow/delivery-2026-11-03.sha256), so the "
                f"exact cell counts were not checked: {departures}"
            ),
            stacklevel=1,
        )
    if profile == "answered":
        assert manifest["answers"]["1_conductivity_suffixes"] == {
            "lower": 3,
            "middle": 2,
            "upper": 1,
        }
        assert manifest["answers"]["8_11_ghb"] == ghb
        assert manifest["answers"]["6_wetting_strategy"] == "below"
        assert manifest["wetting"]["ihdwet"] == 1
        assert (manifest["solver"]["hclose"], manifest["solver"]["rclose"]) == (1.0, 1.0)
    if profile == "answered" and delivered:
        lower, middle, upper = manifest["layers"]
        assert (lower["heads_filled"], middle["heads_filled"]) == (18, 277)
        assert upper["below_bottom_cells"] == [[15, 231]]
        assert upper["clipped_to_surface"] == 20419
        assert upper["deactivated_cells"] == [[15, 231]]
        assert manifest["station"]["sample_id"] == 35
