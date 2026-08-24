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
    """Undo the global changes ``dictConfig`` makes to the logging module."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    manager = root.manager
    saved_disabled = {
        name: existing.disabled
        for name, existing in manager.loggerDict.items()
        if isinstance(existing, logging.Logger)
    }
    try:
        yield
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
        for name, disabled in saved_disabled.items():
            existing = manager.loggerDict.get(name)
            if isinstance(existing, logging.Logger):
                existing.disabled = disabled
