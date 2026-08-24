import logging
import os

import pytest


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
