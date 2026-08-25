"""Path normalisation shared by the public entry points.

Every public parameter that names a file or a directory accepts ``str`` or any
:class:`os.PathLike`. ``bytes`` paths are still accepted for one minor release
with a :class:`DeprecationWarning`; they are decoded with the file system
encoding.
"""

import os
import warnings
from pathlib import Path

PathInput = str | os.PathLike[str] | bytes


def as_path(value: PathInput) -> Path:
    """Return ``value`` as a :class:`pathlib.Path`.

    ``os.fspath`` is resolved first, so a ``PathLike`` whose ``__fspath__``
    returns ``bytes`` is decoded the same way a plain ``bytes`` value is,
    instead of reaching :class:`pathlib.Path` as bytes and raising ``TypeError``.

    :raises TypeError: If ``value`` is not a path-like object.
    """
    if isinstance(value, os.PathLike):
        value = os.fspath(value)
    elif not isinstance(value, (str, bytes)):
        raise TypeError(f"expected a path-like object, got {type(value).__name__}")
    if isinstance(value, bytes):
        warnings.warn(
            "bytes paths are deprecated; pass a str or an os.PathLike instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        value = os.fsdecode(value)
    return Path(value)
