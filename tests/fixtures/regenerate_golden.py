"""Regenerate the golden outputs of the synthetic regression dataset.

Run from the repository root, inside the golden environment
(``ci/golden-env.lock``):

    python tests/fixtures/regenerate_golden.py

The script runs the model through the CLI with the configuration from
``tests.helpers.config.base_model_config`` (the same one the integration and
exact tests use), copies the compared output files into
``tests/fixtures/base/out/`` and rewrites ``SHA256SUMS``. Golden changes must
be justified in ``tests/fixtures/AUDIT.md``.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from tests.helpers.compare import sha256_of  # noqa: E402
from tests.helpers.config import (  # noqa: E402
    GOLDEN_DIR,
    GOLDEN_FILES,
    REPO_ROOT,
    SHA256SUMS_PATH,
    base_model_config,
)


def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "config.json")
        with open(config_path, "w", encoding="utf8") as config_file:
            json.dump(base_model_config(temp_dir), config_file)

        subprocess.check_call(
            [sys.executable, os.path.join(REPO_ROOT, "rubem"), "-c", config_path],
            cwd=REPO_ROOT,
        )

        missing = [
            name
            for name in GOLDEN_FILES
            if not os.path.isfile(os.path.join(temp_dir, name))
        ]
        if missing:
            raise SystemExit(f"run did not produce: {', '.join(missing)}")

        os.makedirs(GOLDEN_DIR, exist_ok=True)
        for name in GOLDEN_FILES:
            shutil.copy2(os.path.join(temp_dir, name), os.path.join(GOLDEN_DIR, name))

    with open(SHA256SUMS_PATH, "w", encoding="utf-8") as sums_file:
        for name in sorted(GOLDEN_FILES):
            digest = sha256_of(os.path.join(GOLDEN_DIR, name))
            sums_file.write(f"{digest}  {name}\n")

    print(f"regenerated {len(GOLDEN_FILES)} golden files in {GOLDEN_DIR}")
    print(f"checksums written to {SHA256SUMS_PATH}")


if __name__ == "__main__":
    main()
