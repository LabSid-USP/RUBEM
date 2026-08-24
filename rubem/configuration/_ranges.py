"""Range checks shared by the configuration models.

The admissible ranges come from the application settings
(``appsettings.json``, section ``value_ranges``).
"""

from .app_settings import AppSettings, ValueRange


def variable_range(key: str) -> tuple[float, float]:
    """Return ``(min, max)`` of a model variable from the application settings."""
    valid_range = AppSettings.default().value_ranges.variables[key]
    return valid_range.min, valid_range.max


def raster_range(key: str) -> dict[str, float]:
    """Return the ``{"min": ..., "max": ...}`` range of an input raster."""
    return AppSettings.default().value_ranges.rasters[key].model_dump()


def raster_ranges() -> dict[str, dict[str, float]]:
    """Return every input raster range keyed by raster name."""
    rasters: dict[str, ValueRange] = AppSettings.default().value_ranges.rasters
    return {name: valid_range.model_dump() for name, valid_range in rasters.items()}


def check_range(parameter_name: str, value: float, key: str) -> None:
    """Raise ``ValueError`` when ``value`` is outside the configured range of ``key``."""
    min_value, max_value = variable_range(key)
    if not min_value <= value <= max_value:
        raise ValueError(
            f"Parameter value out of range: {parameter_name}={value} [{min_value}, {max_value}]."
        )
