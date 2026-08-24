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
