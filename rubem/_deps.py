"""Diagnostics for the conda-only native runtime dependencies."""

import importlib.util
import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_CONDA_ONLY_DEPENDENCIES = ("pcraster", "osgeo")
_ENVIRONMENT_YML_URL = "https://github.com/LabSid-USP/RUBEM/blob/main/environment.yml"


def missing_runtime_deps() -> list[str]:
    """Return the conda-only runtime dependencies that are not importable.

    A dependency whose lookup itself fails (a broken installation whose parent
    package raises on import) counts as missing: the run would not get past it
    either.

    :return: The missing dependency names, in the order they are checked.
    """
    missing = []
    for name in _CONDA_ONLY_DEPENDENCIES:
        try:
            found = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            missing.append(name)
    return missing


def runtime_deps_message(missing: list[str]) -> str:
    """Return the installation guidance for the missing runtime dependencies.

    The command line raises it as ``SystemExit`` and the Python API as
    ``ImportError``, so both front ends give the same instructions.

    :param missing: The missing dependency names, see :func:`missing_runtime_deps`.
    """
    return (
        "RUBEM cannot run because the following conda-only dependencies are "
        f"not installed: {', '.join(missing)}. Install them from conda-forge, "
        "for example with 'conda install -c conda-forge pcraster gdal' (or the "
        "micromamba equivalent), and run RUBEM from that environment. The pinned "
        f"specification is environment.yml: {_ENVIRONMENT_YML_URL}"
    )


def require_runtime_deps() -> None:
    """Fail fast with guidance when pcraster or GDAL are not importable.

    :raises SystemExit: If any conda-only dependency is missing.
    """
    missing = missing_runtime_deps()
    if missing:
        raise SystemExit(runtime_deps_message(missing))


_PREPROCESSING_DEPENDENCIES = ("pykrige", "skgstat")


def require_preprocessing_deps() -> None:
    """Fail fast with guidance when the optional kriging dependencies are missing.

    :raises SystemExit: If pykrige or scikit-gstat is not importable.
    """
    missing = [
        name for name in _PREPROCESSING_DEPENDENCIES if importlib.util.find_spec(name) is None
    ]
    if missing:
        raise SystemExit(
            "This preprocessing tool needs the optional dependencies "
            f"{', '.join(missing)}. Install them with 'pip install \"rubem[preprocessing]\"'."
        )


_CALIBRATION_DEPENDENCIES = ("scipy",)


def missing_calibration_deps() -> list[str]:
    """Return the optional calibration dependencies that are not importable.

    As in :func:`missing_runtime_deps`, a dependency whose lookup itself fails
    counts as missing: the calibration would not get past it either.

    :return: The missing dependency names, in the order they are checked.
    """
    missing = []
    for name in _CALIBRATION_DEPENDENCIES:
        try:
            found = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            missing.append(name)
    return missing


def calibration_deps_message(missing: list[str] | None = None) -> str:
    """Return the installation guidance for the missing calibration dependencies.

    The command line raises it as ``SystemExit`` and the runner as
    ``CalibrationError``, so both front ends give the same instructions.

    :param missing: The missing dependency names, see
        :func:`missing_calibration_deps`. Defaults to ``None``, which names
        every optional calibration dependency.
    """
    names = list(_CALIBRATION_DEPENDENCIES) if missing is None else missing
    plural = "dependencies" if len(names) > 1 else "dependency"
    return (
        f"The calibration command needs the optional {plural} {', '.join(names)}. "
        "Install it with 'pip install \"rubem[calibration]\"'."
    )


def require_calibration_deps() -> None:
    """Fail fast with guidance when SciPy is not importable.

    :raises SystemExit: If any optional calibration dependency is missing.
    """
    missing = missing_calibration_deps()
    if missing:
        raise SystemExit(calibration_deps_message(missing))


_GROUNDWATER_EXTENSION = "pcraster._pcraster_modflow"
_MF2005 = "mf2005"


def resolve_mf2005() -> Path | None:
    """Return the MODFLOW-2005 executable the PCRaster MODFLOW extension launches.

    The extension starts ``mf2005`` from PATH. The conda-forge ``pcraster``
    package installs it next to the interpreter (``<prefix>/bin/mf2005``, or
    ``<prefix>/Library/bin/mf2005.exe`` on Windows), which is not on PATH when
    the environment is used without being activated, so that location is the
    fallback.

    :returns: The executable, or ``None`` when neither PATH nor the prefix has it.
    :rtype: pathlib.Path | None
    """
    found = shutil.which(_MF2005)
    if found is not None:
        return Path(found)
    prefix = Path(sys.prefix)
    for candidate in (prefix / "bin" / _MF2005, prefix / "Library" / "bin" / f"{_MF2005}.exe"):
        if candidate.is_file():
            return candidate
    return None


def missing_groundwater_deps() -> list[str]:
    """Return what the MODFLOW coupling needs and cannot find.

    The PCRaster MODFLOW extension (``pcraster._pcraster_modflow``, which
    provides ``pcraster.initialise``) and the ``mf2005`` executable, see
    :func:`resolve_mf2005`. As in :func:`missing_runtime_deps`, an extension
    whose lookup fails (looking up a submodule imports ``pcraster``) counts as
    missing.

    :returns: The missing names, in the order they are checked.
    :rtype: list[str]
    """
    missing = []
    try:
        found = importlib.util.find_spec(_GROUNDWATER_EXTENSION) is not None
    except (ImportError, ValueError):
        found = False
    if not found:
        missing.append(_GROUNDWATER_EXTENSION)
    if resolve_mf2005() is None:
        missing.append(_MF2005)
    return missing


def groundwater_deps_message(missing: list[str] | None = None) -> str:
    """Return the installation guidance for the missing MODFLOW runtime.

    :param missing: The missing names, see :func:`missing_groundwater_deps`.
        Defaults to ``None``, which names both.
    :type missing: list[str] | None
    :rtype: str
    """
    names = [_GROUNDWATER_EXTENSION, _MF2005] if missing is None else missing
    return (
        "The MODFLOW coupling needs the PCRaster MODFLOW extension "
        f"({_GROUNDWATER_EXTENSION}) and the MODFLOW-2005 executable ({_MF2005}), both "
        f"shipped by the conda-forge pcraster package; not found: {', '.join(names)}. "
        "Install pcraster from conda-forge (the pinned specification is environment.yml: "
        f"{_ENVIRONMENT_YML_URL}), or put {_MF2005} on PATH."
    )


def ensure_mf2005_on_path() -> Path | None:
    """Put the directory of :func:`resolve_mf2005` on PATH when it is not there.

    The extension launches ``mf2005`` from PATH, and spawned calibration
    workers inherit the environment of the parent, so the directory is
    prepended once, in the parent, and logged.

    :returns: The executable, or ``None`` when it cannot be found (PATH is
        then left unchanged).
    :rtype: pathlib.Path | None
    """
    found = shutil.which(_MF2005)
    if found is not None:
        return Path(found)
    executable = resolve_mf2005()
    if executable is None:
        return None
    directory = str(executable.parent)
    path = os.environ.get("PATH", "")
    if directory not in path.split(os.pathsep):
        os.environ["PATH"] = f"{directory}{os.pathsep}{path}" if path else directory
        logger.info("Added %s to PATH so that MODFLOW finds %s.", directory, _MF2005)
    return executable
