"""Diagnostics for the conda-only native runtime dependencies."""

import importlib.util

_CONDA_ONLY_DEPENDENCIES = ("pcraster", "osgeo")
_ENVIRONMENT_YML_URL = "https://github.com/LabSid-USP/RUBEM/blob/main/environment.yml"


def require_runtime_deps() -> None:
    """Fail fast with guidance when pcraster or GDAL are not importable.

    :raises SystemExit: If any conda-only dependency is missing.
    """
    missing = [name for name in _CONDA_ONLY_DEPENDENCIES if importlib.util.find_spec(name) is None]
    if missing:
        raise SystemExit(
            "RUBEM cannot run because the following conda-only dependencies are "
            f"not installed: {', '.join(missing)}. Install them from conda-forge, "
            "for example with 'conda install -c conda-forge pcraster gdal' (or the "
            "micromamba equivalent), and run RUBEM from that environment. The pinned "
            f"specification is environment.yml: {_ENVIRONMENT_YML_URL}"
        )


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
