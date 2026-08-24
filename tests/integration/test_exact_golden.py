import json
import os
import subprocess
import sys

import pytest

from tests.helpers.compare import sha256_of
from tests.helpers.config import (
    GOLDEN_FILES,
    REPO_ROOT,
    base_model_config,
    read_sha256sums,
)


@pytest.mark.exact
@pytest.mark.skipif(
    os.environ.get("RUBEM_EXACT_GOLDEN") != "1",
    reason="byte-exact golden reproduction runs only on the golden environment "
    "(set RUBEM_EXACT_GOLDEN=1)",
)
def test_exact_golden_reproduction(tmp_path):
    """Regenerate the outputs and compare byte-for-byte with the goldens.

    Byte identity is only expected on the environment frozen in
    ``ci/golden-env.lock``; every other environment compares semantically
    through the regular integration tests.
    """
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(base_model_config(str(tmp_path))))

    subprocess.check_output(
        [sys.executable, os.path.join(REPO_ROOT, "rubem"), "-c", str(config_path)],
        cwd=REPO_ROOT,
    )

    expected = read_sha256sums()
    mismatches = []
    for name in GOLDEN_FILES:
        candidate = tmp_path / name
        if not candidate.is_file():
            mismatches.append(f"{name}: not produced")
            continue
        actual = sha256_of(candidate)
        if actual != expected[name]:
            mismatches.append(f"{name}: expected {expected[name]}, got {actual}")
    header = (
        "byte identity is expected only on the environment and runner image "
        "recorded in tests/fixtures/AUDIT.md:"
    )
    assert not mismatches, "\n".join([header, *mismatches])
