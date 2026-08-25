"""Deprecated spelling of :mod:`rubem.file._file_conversions`.

Kept for one minor release; import :mod:`rubem.file._file_conversions` instead.
"""

import warnings

from ._file_conversions import *  # noqa: F401, F403
from ._file_conversions import tss2csv  # noqa: F401

warnings.warn(
    "rubem.file._file_convertions is deprecated; use rubem.file._file_conversions.",
    DeprecationWarning,
    stacklevel=2,
)
