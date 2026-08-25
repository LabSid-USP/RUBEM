"""Naming rules of the raster series RUBEM reads and writes.

Input series follow the PCRaster 8.3 convention used by the dynamic
framework: the prefix is padded with zeros up to eight characters and the
time step fills the last digits, continuing into the base name when it needs
more than three (``prec0000.001``, ``prec0001.000``). Output GeoTIFF series
use the prefix followed by the time step zero-padded to ten characters in
total (``itp0000001.tif``).
"""

import os
import re
from pathlib import Path

RASTER_SERIES_BASENAME_LENGTH = 8
RASTER_SERIES_EXTENSION_LENGTH = 3
RASTER_SERIES_DIGITS = RASTER_SERIES_BASENAME_LENGTH + RASTER_SERIES_EXTENSION_LENGTH
OUTPUT_RASTER_NAME_LENGTH = 10


def raster_series_filename(prefix: str, timestep: int) -> str:
    """Return the 8.3 file name of a raster series member.

    The result equals the name the PCRaster framework generates for
    ``readmap``/``report`` (``generateNameT``), so the model and the
    validators agree on which file belongs to which step.

    :param prefix: File name prefix, without directory or extension.
    :param timestep: Time step, ``1`` or greater.
    :raises ValueError: If the prefix is empty, too long, contains a path
        separator or a dot, or if the time step is not positive or does not
        fit in the digits the prefix leaves free.
    """
    _validate_prefix(prefix)
    if not isinstance(timestep, int) or isinstance(timestep, bool) or timestep < 1:
        raise ValueError(f"Time step must be a positive integer, got {timestep!r}.")
    digits = str(timestep)
    padding = RASTER_SERIES_DIGITS - len(prefix) - len(digits)
    if padding < 0:
        raise ValueError(
            f"Time step {timestep} does not fit the {RASTER_SERIES_DIGITS - len(prefix)} "
            f"digits left by the prefix '{prefix}'."
        )
    joined = f"{prefix}{'0' * padding}{digits}"
    return f"{joined[:RASTER_SERIES_BASENAME_LENGTH]}.{joined[RASTER_SERIES_BASENAME_LENGTH:]}"


def get_raster_series_filepath(directory, prefix: str, timestep: int) -> str:
    """Return the absolute path of a raster series member.

    :param directory: Directory of the series.
    :param prefix: File name prefix, see :func:`raster_series_filename`.
    :param timestep: Time step, ``1`` or greater.
    """
    return str((Path(os.fsdecode(directory)) / raster_series_filename(prefix, timestep)).absolute())


def raster_series_pattern(prefix: str) -> re.Pattern:
    """Return the pattern that matches the members of a raster series.

    The prefix is taken literally; the remaining characters of the 8.3 name
    are digits. Matching is case-insensitive, as file systems may be.

    :param prefix: File name prefix, see :func:`raster_series_filename`.
    """
    _validate_prefix(prefix)
    basename_digits = RASTER_SERIES_BASENAME_LENGTH - len(prefix)
    return re.compile(
        rf"^{re.escape(prefix)}[0-9]{{{basename_digits}}}"
        rf"\.[0-9]{{{RASTER_SERIES_EXTENSION_LENGTH}}}$",
        re.IGNORECASE,
    )


def output_raster_filename(prefix: str, timestep: int, extension: str) -> str:
    """Return the file name of an output raster series member.

    :param prefix: Variable prefix (``itp``, ``arn``, ...).
    :param timestep: Time step, ``1`` or greater.
    :param extension: Extension without the dot (``tif``).
    :raises ValueError: If the prefix leaves no room for the time step or the
        time step does not fit the remaining characters.
    """
    if not prefix or len(prefix) >= OUTPUT_RASTER_NAME_LENGTH:
        raise ValueError(
            f"Output prefix '{prefix}' must have between 1 and "
            f"{OUTPUT_RASTER_NAME_LENGTH - 1} characters."
        )
    if not isinstance(timestep, int) or isinstance(timestep, bool) or timestep < 1:
        raise ValueError(f"Time step must be a positive integer, got {timestep!r}.")
    digits = str(timestep).zfill(OUTPUT_RASTER_NAME_LENGTH - len(prefix))
    if len(prefix) + len(digits) > OUTPUT_RASTER_NAME_LENGTH:
        raise ValueError(
            f"Time step {timestep} does not fit the {OUTPUT_RASTER_NAME_LENGTH - len(prefix)} "
            f"digits left by the prefix '{prefix}'."
        )
    return f"{prefix}{digits}.{extension}"


def _validate_prefix(prefix: str) -> None:
    if not isinstance(prefix, str) or not prefix:
        raise ValueError("Raster series prefix must be a non-empty string.")
    if len(prefix) >= RASTER_SERIES_BASENAME_LENGTH:
        raise ValueError(
            f"Raster series prefix '{prefix}' must be shorter than "
            f"{RASTER_SERIES_BASENAME_LENGTH} characters."
        )
    if "." in prefix or "/" in prefix or "\\" in prefix or os.sep in prefix:
        raise ValueError(
            f"Raster series prefix '{prefix}' must not contain a dot or a path separator."
        )


def geotiff_series_pattern(prefix: str) -> re.Pattern:
    """Return the pattern that matches GeoTIFF members of an input series.

    Members are named like the model outputs: the prefix followed by the step
    zero-padded to ten characters in total, with a ``.tif`` or ``.tiff`` suffix.
    """
    if not prefix or len(prefix) >= OUTPUT_RASTER_NAME_LENGTH:
        raise ValueError(
            f"Output prefix '{prefix}' must have between 1 and "
            f"{OUTPUT_RASTER_NAME_LENGTH - 1} characters."
        )
    return re.compile(
        rf"^{re.escape(prefix)}[0-9]{{{OUTPUT_RASTER_NAME_LENGTH - len(prefix)}}}\.tiff?$",
        re.IGNORECASE,
    )
