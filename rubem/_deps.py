"""Diagnostics for the conda-only native runtime dependencies."""

import importlib.util

_CONDA_ONLY_DEPENDENCIES = ("pcraster", "osgeo")


def require_runtime_deps() -> None:
    """Fail fast with guidance when pcraster or GDAL are not importable.

    :raises SystemExit: If any conda-only dependency is missing.
    """
    missing = [name for name in _CONDA_ONLY_DEPENDENCIES if importlib.util.find_spec(name) is None]
    if missing:
        raise SystemExit(
            "RUBEM cannot run because the following conda-only dependencies are "
            f"not installed: {', '.join(missing)}. Create the runtime environment "
            "with 'conda env create -f environment.yml' (or micromamba) and "
            "install RUBEM inside it with 'pip install .'."
        )
