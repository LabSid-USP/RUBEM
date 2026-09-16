"""Diagnostics for the conda-only native runtime dependencies."""

import importlib.util

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
