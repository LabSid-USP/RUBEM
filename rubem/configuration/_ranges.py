"""Range checks shared by the configuration value models.

The admissible ranges come from the application settings
(``appsettings.json``, section ``value_ranges``), which the model reads once
through :class:`~rubem.configuration.data_ranges_settings.DataRangesSettings`.
"""

from .data_ranges_settings import DataRangesSettings


def variable_range(key: str) -> tuple[float, float]:
    """Return ``(min, max)`` of a model variable from the application settings."""
    valid_range = DataRangesSettings().variables[key]
    return valid_range["min"], valid_range["max"]


def check_range(parameter_name: str, value: float, key: str) -> None:
    """Raise ``ValueError`` when ``value`` is outside the configured range of ``key``."""
    min_value, max_value = variable_range(key)
    if not min_value <= value <= max_value:
        raise ValueError(
            f"Parameter value out of range: {parameter_name}={value} [{min_value}, {max_value}]."
        )
