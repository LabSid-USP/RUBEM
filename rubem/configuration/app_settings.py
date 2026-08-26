"""Application settings: value ranges, language and logging.

The packaged ``appsettings.json`` is the default. When the ``PYTHON_ENVIRONMENT``
variable is set, ``appsettings.<PYTHON_ENVIRONMENT>.json`` is looked up first in
the package directory and then in the current working directory, and the first
non-empty file found replaces the default.
"""

import json
import math
import os
import sys
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from .._paths import PathInput, as_path

PACKAGE_DIR = Path(__file__).parent.parent
DEFAULT_SETTINGS_FILE = PACKAGE_DIR / "appsettings.json"


def _freeze(value):
    """A read-only view of JSON-like data, mappings and sequences included.

    A frozen model still hands out its mutable ``dict`` and ``list`` members;
    with :meth:`AppSettings.default` cached, a mutation through one reference
    would be observed by every other consumer.
    """
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value):
    """A plain, mutable copy of what :func:`_freeze` produced.

    ``logging.config.dictConfig`` pops keys from the dictionaries it is given,
    so consumers receive copies, never the frozen settings themselves.
    """
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _finite(value):
    """Turn the JSON spellings of the infinities into the largest finite floats."""
    if value == "Infinity":
        return sys.float_info.max
    if value == "-Infinity":
        return -sys.float_info.max
    return value


class ValueRange(BaseModel):
    """Admissible ``[min, max]`` interval of a raster or a model variable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min: float
    max: float

    @field_validator("min", "max", mode="before")
    @classmethod
    def _convert_infinities(cls, value):
        value = _finite(value)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"expected a number, got {value!r}")
        if not math.isfinite(value):
            raise ValueError('expected a finite number (use "Infinity" for an open bound)')
        return value

    @model_validator(mode="after")
    def _check_order(self):
        if self.min >= self.max:
            raise ValueError("'max' value must be greater than 'min' value")
        return self


class ValueRanges(BaseModel):
    """The ranges of the input rasters and of the model variables."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rasters: Mapping[str, ValueRange]
    variables: Mapping[str, ValueRange]

    @field_validator("rasters", "variables", mode="after")
    @classmethod
    def _freeze(cls, value: Mapping[str, ValueRange]) -> Mapping[str, ValueRange]:
        # A frozen model still exposes a mutable dict unless the mapping
        # itself is made read-only: the cached default (AppSettings.default())
        # must not be corrupted by a caller mutating what it returns.
        return MappingProxyType(dict(value))

    @field_serializer("rasters", "variables", mode="wrap")
    def _serialize_mapping(self, value: Mapping[str, ValueRange], handler):
        # Serialize as a plain dict; the handler still applies the normal
        # (recursive) dict[str, ValueRange] serialization on top of it.
        return handler(dict(value))


class I18nSettings(BaseModel):
    """Language of the human-readable output."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    language: str = "en_US"


class AppSettings(BaseModel):
    """The application settings.

    :param value_ranges: Admissible ranges of the input rasters and the model variables.
    :param i18n: Language settings.
    :param logging: A ``logging.config.dictConfig`` dictionary; empty for the default setup.
        Read-only on the instance; :meth:`get_setting` and :meth:`model_dump`
        hand out plain copies.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    value_ranges: ValueRanges
    i18n: I18nSettings = I18nSettings()
    logging: Mapping[str, Any] = Field(default={}, validate_default=True)

    @field_validator("logging", mode="after")
    @classmethod
    def _freeze_logging(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return _freeze(value)

    @field_serializer("logging")
    def _serialize_logging(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return _thaw(value)

    @classmethod
    def load(cls, settings_file: PathInput) -> "AppSettings":
        """Load the settings from a JSON file.

        :raises FileNotFoundError: If the file does not exist.
        """
        path = as_path(settings_file).absolute()
        if not path.is_file():
            raise FileNotFoundError(f"Application settings file not found: {path}")
        with path.open(encoding="utf8") as file:
            return cls.model_validate(json.load(file))

    @classmethod
    def default_file(cls) -> Path:
        """The settings file selected by ``PYTHON_ENVIRONMENT``, or the packaged one."""
        environment = os.environ.get("PYTHON_ENVIRONMENT", "")
        if environment:
            name = f"appsettings.{environment}.json"
            for candidate in (PACKAGE_DIR / name, Path.cwd() / name):
                if candidate.is_file() and candidate.stat().st_size > 0:
                    return candidate.absolute()
        return DEFAULT_SETTINGS_FILE.absolute()

    @classmethod
    def default(cls) -> "AppSettings":
        """The settings of :meth:`default_file`, read once per file."""
        return _load_cached(str(cls.default_file()))

    def get_setting(self, key: str) -> Any:
        """Return a top-level setting as plain data, or ``None`` when absent.

        Kept for callers written against the previous dictionary-based settings.
        """
        if key not in type(self).model_fields:
            return None
        value = getattr(self, key)
        return value.model_dump() if isinstance(value, BaseModel) else _thaw(value)


@lru_cache(maxsize=8)
def _load_cached(settings_file: str) -> AppSettings:
    return AppSettings.load(settings_file)
