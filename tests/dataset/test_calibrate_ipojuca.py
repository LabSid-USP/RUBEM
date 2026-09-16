"""Smoke test of the calibration on the published Ipojuca basin dataset.

The test rebuilds the configuration of the basin from its manifest, runs the
model once over a short window to obtain the series a perfect calibration has
to reproduce, and then asks the differential evolution to find the parameters
that produced it again, from a five-member initial population, in one
generation.

The drainage network is fixed before anything runs. ``lddcreate`` is called by
the model whenever the configuration names no ``ldd`` raster, and on the real
basin digital elevation models it returns a different network on every call, so
the accumulated runoff, which is routed along it, is not reproducible between
two runs of one configuration. A calibration on ``arn`` without a fixed network
would compare series routed on different networks; the test therefore generates
the network once and names it in the configuration, as the documentation of the
command requires.

The dataset is not part of the repository: the whole module is marked
``dataset`` and runs only where ``RUBEM_DATASET_DIR`` points at the local copy.
"""

import csv
import json
import multiprocessing
import shutil
from pathlib import Path

import numpy as np
import pytest

from rubem.api import Model
from rubem.calibration.parameters import CALIBRATION_PARAMETERS, is_admissible
from rubem.calibration.runner import EVALUATION_COLUMNS, CalibrationSettings, calibrate
from rubem.configuration.model_configuration import ModelConfiguration

# SciPy is the optional ``rubem[calibration]`` extra; an environment without it
# collects this file and skips it instead of failing to import.
pytest.importorskip("scipy.optimize")

pytestmark = [pytest.mark.dataset, pytest.mark.slow]

BASIN = "ipojuca_basin"
"""The basin this test calibrates: its manifest is ``<BASIN>.json``."""

PATH_SEGMENT = f"{BASIN}/"
"""The segment every input path of the manifest carries.

The manifests are written by the machine that extracted the datasets and hold
absolute paths of that machine, so every path is rebased onto the local copy by
replacing whatever precedes this segment.
"""

STEPS = 6
"""Monthly steps of the window the test simulates, from 01/01/2000 to 01/06/2000."""

# Five admissible members around the parameter set of the manifest, the second
# one far from it. SciPy replaces the first member with x0, so the configuration
# under calibration is always part of the initial population, and the search has
# one generation to find it again.
INIT = np.array(
    [
        [4.415, 0.078, 0.51, 0.12, 5.375, 0.581, 0.922, 0.307],
        [9.500, 0.900, 0.05, 0.85, 9.000, 0.950, 0.150, 0.900],
        [3.500, 0.150, 0.45, 0.20, 4.500, 0.500, 0.800, 0.250],
        [5.500, 0.050, 0.55, 0.10, 6.500, 0.650, 0.950, 0.400],
        [4.000, 0.200, 0.40, 0.30, 5.000, 0.450, 0.700, 0.350],
    ]
)


def _rebase(value, root: Path):
    """Return the manifest with every input path anchored on the local copy.

    :param value: A manifest document, one of its sections or one of its values.
    :param root: The directory the extracted datasets live in.
    :type root: pathlib.Path
    """
    if isinstance(value, dict):
        return {key: _rebase(item, root) for key, item in value.items()}
    if isinstance(value, str) and PATH_SEGMENT in value:
        return str(root / value[value.index(PATH_SEGMENT) :])
    return value


def _input_paths(value, root: Path):
    """Yield every path of a rebased document that lies under ``root``."""
    if isinstance(value, dict):
        for item in value.values():
            yield from _input_paths(item, root)
    elif isinstance(value, str) and value.startswith(str(root)):
        yield value


def _read_evaluations(path: Path) -> list[dict[str, str]]:
    """Return the rows of an ``evaluations.csv`` table, header first.

    A local copy of the reader of ``tests/unit/calibration/test_runner.py``:
    importing one test module from another would run the module-level
    ``importorskip`` of the other one during the collection of this one, for
    three lines of CSV reading.
    """
    with path.open(encoding="utf-8", newline="") as table:
        return list(csv.DictReader(table))


def _fixed_ldd(document: dict, destination: Path) -> str:
    """Generate the drainage network of the basin once and return its path.

    The network is derived from the digital elevation model of the basin with
    the parameters the model itself uses when no network is configured, and is
    written so that every run of the calibration routes the runoff along the
    very same network.
    """
    import pcraster as pcr

    pcr.setclone(document["RASTERS"]["clone"])
    dem = pcr.readmap(document["RASTERS"]["dem"])
    pcr.report(pcr.lddcreate(dem, 1e31, 1e31, 1e31, 1e31), str(destination))
    return str(destination)


def test_the_calibration_recovers_the_parameters_of_the_ipojuca_basin(
    dataset_dir, tmp_path, monkeypatch
):
    manifest = dataset_dir / f"{BASIN}.json"
    if not manifest.is_file():
        pytest.skip(f"{manifest} is not there")

    # The inputs are read where they were extracted, so the persistent auxiliary
    # metadata of GDAL would annotate every raster of the dataset with a sidecar
    # file of its statistics, next to the raster itself. The test writes nothing
    # outside its own temporary directory; the workers inherit the variable.
    monkeypatch.setenv("GDAL_PAM_ENABLED", "NO")

    assert [tuple(row) for row in INIT if not is_admissible(row)] == [], (
        "every member of the initial population must be admissible, or the search "
        "would spend its generation on candidates it never runs"
    )

    document = _rebase(json.loads(manifest.read_text(encoding="utf-8")), dataset_dir)
    missing = [path for path in _input_paths(document, dataset_dir) if not Path(path).exists()]
    assert missing == [], "the manifest was rebased onto the local copy of the datasets"

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    document["DIRECTORIES"]["output"] = str(output_dir)
    document["SIM_TIME"] = {"start": "01/01/2000", "end": "01/06/2000"}
    document["RASTERS"]["ldd"] = _fixed_ldd(document, tmp_path / "ldd.map")

    config_file = tmp_path / f"{BASIN}.json"
    config_file.write_text(json.dumps(document, indent=2), encoding="utf-8")
    parameters = ModelConfiguration(config_file, validate_input=False).calibration_parameters
    expected = parameters.model_dump()

    written = Model.from_file(config_file).run().time_series["arn"][0]
    observed = tmp_path / "observed.csv"
    shutil.copyfile(written, observed)
    assert len(observed.read_text(encoding="utf-8").splitlines()) == STEPS + 1, (
        "the header and one row per monthly step of the window"
    )

    temp_dir = tmp_path / "tmp"
    result = calibrate(
        config_file,
        observed,
        tmp_path / "run",
        CalibrationSettings(
            init=INIT,
            maxiter=1,
            popsize=5,
            workers=2,
            seed=1,
            temp_dir=str(temp_dir),
        ),
    )

    # The observed series is what the configuration itself wrote, so the global
    # optimum of the search is that configuration, with an efficiency of 1.
    assert result.best_objective == 0.0
    assert result.best_nse == pytest.approx(1.0, abs=1e-12)
    assert result.best_parameters == pytest.approx(expected, abs=1e-12)
    assert set(result.best_parameters) == set(CALIBRATION_PARAMETERS)

    rows = _read_evaluations(result.evaluations_csv)
    assert list(rows[0]) == list(EVALUATION_COLUMNS)
    assert len(rows) == result.evaluations
    assert [row["error"] for row in rows if row["error"]] == []

    summary = json.loads(result.result_json.read_text(encoding="utf-8"))
    assert summary["nfev"] == result.evaluations
    assert summary["population_size"] == len(INIT)

    assert result.calibrated_config.name == f"{BASIN}-calibrated.json"
    calibrated = ModelConfiguration(result.calibrated_config, validate_input=False)
    assert calibrated.calibration_parameters.model_dump() == pytest.approx(
        result.best_parameters, abs=1e-12
    )

    assert multiprocessing.active_children() == []
    assert list(temp_dir.iterdir()) == []
