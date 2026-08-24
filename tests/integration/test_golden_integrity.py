import os

import pytest

from tests.helpers.compare import sha256_of
from tests.helpers.config import GOLDEN_DIR, GOLDEN_FILES, read_sha256sums


class TestGoldenIntegrity:
    """Guard the golden fixture files against accidental edits.

    ``SHA256SUMS`` records the digests of the files written by
    ``tests/fixtures/regenerate_golden.py``; see ``tests/fixtures/AUDIT.md``
    for the provenance of the current goldens.
    """

    @pytest.mark.integration
    def test_sha256sums_covers_exactly_the_golden_files(self):
        assert set(read_sha256sums()) == set(GOLDEN_FILES)

    @pytest.mark.integration
    def test_golden_directory_contains_exactly_the_golden_files(self):
        assert set(os.listdir(GOLDEN_DIR)) == set(GOLDEN_FILES) | {"SHA256SUMS"}

    @pytest.mark.integration
    def test_golden_files_match_recorded_checksums(self):
        mismatches = []
        for name, digest in sorted(read_sha256sums().items()):
            actual = sha256_of(os.path.join(GOLDEN_DIR, name))
            if actual != digest:
                mismatches.append(f"{name}: recorded {digest}, actual {actual}")
        assert not mismatches, "\n".join(mismatches)
