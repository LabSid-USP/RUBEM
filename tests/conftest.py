import logging
import os
from pathlib import Path

import pytest

DATASET_DIR_VARIABLE = "RUBEM_DATASET_DIR"
"""Environment variable pointing at the local copy of the published datasets.

The directory it names holds the manifest ``<basin>_basin.json`` of every
published basin beside the extracted ``<basin>_basin/`` directory of its inputs.
The datasets are hundreds of megabytes and are not part of the repository, so
the tests that need them are marked ``dataset`` and run only where the variable
is set; everywhere else the suite stays self-contained.
"""

NO_DATASET_DIR = f"{DATASET_DIR_VARIABLE} is not set"
"""The reason a test marked ``dataset`` is skipped with when the variable is unset."""


def _dataset_dir() -> tuple[Path | None, str]:
    """Return the datasets directory, or ``None`` and the reason it is not available.

    An unset or empty variable means the published datasets are not on this
    machine; a variable that names something other than a directory is reported
    as such, so that a mistyped path or a mount that is not up does not read as
    "not requested".
    """
    value = os.environ.get(DATASET_DIR_VARIABLE)
    if not value:
        return None, NO_DATASET_DIR
    directory = Path(value)
    if not directory.is_dir():
        return None, f"{DATASET_DIR_VARIABLE}={value} is not a directory"
    return directory, ""


def pytest_collection_modifyitems(config, items):
    """Skip every test marked ``dataset`` when the datasets are not there.

    The marker alone is enough: a test that never asks for the ``dataset_dir``
    fixture, because it reaches the datasets through another fixture or through
    a helper, is skipped for the same reason as one that does.
    """
    directory, reason = _dataset_dir()
    if directory is not None:
        return
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if item.get_closest_marker("dataset") is not None:
            item.add_marker(skip)


@pytest.fixture
def dataset_dir():
    """The directory of the published datasets, or a skipped test.

    :return: The directory :data:`DATASET_DIR_VARIABLE` names.
    :rtype: pathlib.Path
    """
    directory, reason = _dataset_dir()
    if directory is None:
        pytest.skip(reason)
    return directory


@pytest.fixture(autouse=True)
def preserve_working_directory():
    """Fail any test that leaks a changed process working directory."""
    before = os.getcwd()
    yield
    after = os.getcwd()
    if after != before:
        os.chdir(before)
    assert after == before, f"test changed the working directory to {after}"


@pytest.fixture(name="restore_logging")
def restore_logging_fixture():
    """Undo the global changes ``dictConfig`` makes to the logging module.

    ``dictConfig`` rewrites handlers, levels and propagation of the loggers it
    names, so restoring only the ``disabled`` flag would leave, for instance,
    ``rubem.progress`` attached to a handler bound to a capture stream that no
    longer exists, and the next test would write into it. The whole
    configuration of every named logger is snapshotted, and loggers created
    during the test are removed.
    """
    root = logging.getLogger()
    manager = root.manager
    saved_root = (root.handlers[:], root.level)
    saved = {
        name: (existing.handlers[:], existing.level, existing.propagate, existing.disabled)
        for name, existing in manager.loggerDict.items()
        if isinstance(existing, logging.Logger)
    }
    try:
        yield
    finally:
        root.handlers[:] = saved_root[0]
        root.setLevel(saved_root[1])
        for name, existing in list(manager.loggerDict.items()):
            if not isinstance(existing, logging.Logger):
                continue
            if name not in saved:
                del manager.loggerDict[name]
                continue
            handlers, level, propagate, disabled = saved[name]
            existing.handlers[:] = handlers
            existing.setLevel(level)
            existing.propagate = propagate
            existing.disabled = disabled
