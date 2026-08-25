import os
from pathlib import Path

import pytest

from rubem._paths import as_path


class BytesPathLike:
    """A minimal ``os.PathLike`` whose ``__fspath__`` returns ``bytes``."""

    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def __fspath__(self) -> bytes:
        return self._raw


class TestAsPath:
    @pytest.mark.unit
    def test_a_string_becomes_a_path(self):
        assert as_path("some/dir/file.txt") == Path("some/dir/file.txt")

    @pytest.mark.unit
    def test_a_path_like_object_becomes_a_path(self):
        original = Path("some/dir/file.txt")
        assert as_path(original) == original

    @pytest.mark.unit
    def test_bytes_are_decoded_with_a_deprecation_warning(self):
        raw = os.fsencode("some/dir/file.txt")
        with pytest.warns(DeprecationWarning, match="bytes paths are deprecated"):
            result = as_path(raw)
        assert result == Path("some/dir/file.txt")

    @pytest.mark.unit
    def test_a_bytes_path_like_object_is_decoded_with_a_deprecation_warning(self):
        """A ``PathLike`` whose ``__fspath__`` returns ``bytes`` must not reach ``Path`` as bytes.

        ``pathlib.Path`` raises ``TypeError`` when handed a path-like object
        that resolves to ``bytes``; ``as_path`` decodes it instead, the same
        way it decodes a plain ``bytes`` value.
        """
        raw = BytesPathLike(os.fsencode("some/dir/file.txt"))
        with pytest.warns(DeprecationWarning, match="bytes paths are deprecated"):
            result = as_path(raw)
        assert result == Path("some/dir/file.txt")

    @pytest.mark.unit
    def test_anything_else_is_rejected(self):
        with pytest.raises(TypeError, match="expected a path-like object, got int"):
            as_path(123)
