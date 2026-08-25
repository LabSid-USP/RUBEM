"""The legacy JSON configuration file as a validated model.

The legacy format is tolerant: the spellings found in circulating files are
accepted as aliases of the canonical keys, unknown keys are reported and
ignored, booleans may be written as strings, and numbers may be written as
strings. ``model_dump(by_alias=True)`` writes the canonical form back.
"""

import logging
import math
import os
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any, Self

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    WithJsonSchema,
    field_serializer,
    field_validator,
    model_validator,
)

from .._paths import PathInput, as_path
from ._json import read_json

logger = logging.getLogger(__name__)

DATE_FORMAT = "%d/%m/%Y"

_LEGACY_DATE_JSON_SCHEMA = WithJsonSchema({"type": "string", "pattern": r"^\d{2}/\d{2}/\d{4}$"})
LegacyDate = Annotated[date, _LEGACY_DATE_JSON_SCHEMA]


def finite_float32(value: Any, label: str) -> float:
    """Parse ``value`` as a finite number a Float32 GDAL band can store.

    The Float32 conversion itself decides overflow (a value outside
    ``numpy.finfo(numpy.float32)``'s range becomes infinite) and underflow (a
    tiny non-zero value rounds to 0.0, which would collide with a legitimate
    zero cell in the band); 0 itself stays accepted, as an explicit choice.

    :raises ValueError: If ``value`` is a bool, not numeric, non-finite,
        overflows to infinity, or (unless it is exactly zero) underflows to
        zero when converted to Float32.
    """
    if isinstance(value, bool):
        raise ValueError(f"Invalid {label}: {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid {label}: {value!r}") from e
    if not math.isfinite(number):
        raise ValueError(f"Invalid {label}: {value!r}")

    # numpy is mocked out for the documentation build; import lazily so
    # importing this module does not require it.
    import numpy as np

    as_float32 = np.float32(number)
    if not np.isfinite(as_float32):
        raise ValueError(f"Invalid {label}: {value!r} is outside the representable Float32 range.")
    if number != 0 and as_float32 == 0:
        raise ValueError(
            f"Invalid {label}: {value!r} underflows to zero when stored as Float32, "
            "which would collide with a legitimate zero cell; use 0 if a no-data "
            "value of zero is intended."
        )
    return number


def str_to_bool(value) -> bool:
    """
    Converts a string value to a boolean.

    :param value: The string value to be converted.
    :type value: str

    :return: The boolean representation of the string value.
    :rtype: bool
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.lower() in ("yes", "true", "t", "1")

    raise ValueError(f"Invalid value for boolean conversion: {type(value)}")


class _Section(BaseModel):
    """A section of the legacy file: aliases accepted, unknown keys reported."""

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )

    @model_validator(mode="before")
    @classmethod
    def _normalise_input(cls, data: Any) -> Any:
        """Stringify path-like values, reject duplicated aliases, report unknown keys.

        Values loaded from a Python dictionary (rather than JSON) may carry
        :class:`os.PathLike` objects (``pathlib.Path``); the string fields of a
        section only accept ``str``, so they are converted with
        :func:`os.fspath` before the field validators run.
        """
        if not isinstance(data, dict):
            return data

        data = {
            key: os.fspath(value) if isinstance(value, os.PathLike) else value
            for key, value in data.items()
        }

        known = set()
        for name, info in cls.model_fields.items():
            spellings = {name}
            alias = info.validation_alias
            if isinstance(alias, AliasChoices):
                spellings.update(choice for choice in alias.choices if isinstance(choice, str))
            elif isinstance(alias, str):
                spellings.add(alias)
            if info.alias:
                spellings.add(info.alias)
            known.update(spellings)
            present = sorted(spelling for spelling in spellings if spelling in data)
            if len(present) > 1:
                raise ValueError(
                    f"{cls.__name__} has more than one spelling of the same field: {present}."
                )

        unknown = sorted(key for key in data if key not in known)
        if unknown:
            logger.warning("Unknown key(s) in %s ignored: %s", cls.__name__, unknown)
        return data


def _parse_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.strptime(value.strip(), DATE_FORMAT).date()
    raise ValueError(f"expected a date as {DATE_FORMAT!r}, got {value!r}")


class SimTime(_Section):
    start: LegacyDate
    end: LegacyDate
    alignment: LegacyDate | None = None

    _parse = field_validator("start", "end", "alignment", mode="before")(_parse_date)

    @field_serializer("start", "end", "alignment")
    def _serialize_date(self, value):
        return value.strftime(DATE_FORMAT) if value is not None else None


class Directories(_Section):
    output: str
    etp: str
    prec: str = Field(validation_alias=AliasChoices("prec", "precipitation", "rain"))
    ndvi: str
    kp: str = Field(validation_alias=AliasChoices("kp", "Kp"))
    landuse: str = Field(validation_alias=AliasChoices("landuse", "lulc"))


class FilenamePrefixes(_Section):
    etp_prefix: str
    prec_prefix: str = Field(validation_alias=AliasChoices("prec_prefix", "precipitation_prefix"))
    ndvi_prefix: str
    kp_prefix: str
    landuse_prefix: str = Field(validation_alias=AliasChoices("landuse_prefix", "lulc_prefix"))


class Rasters(_Section):
    dem: str
    clone: str
    ndvi_max: str
    ndvi_min: str
    soil: str
    ldd: str | None = None
    samples: str | None = Field(
        default=None, validation_alias=AliasChoices("samples", "sample_locations")
    )
    georeference: str | None = None

    @field_validator("ldd", "samples", "georeference", mode="before")
    @classmethod
    def _empty_is_none(cls, value):
        return None if value in ("", None) else value


class Tables(_Section):
    rainydays: str = Field(validation_alias=AliasChoices("rainydays", "rainy_days"))
    a_i: str
    a_o: str
    a_s: str
    a_v: str
    manning: str
    bulk_density: str = Field(validation_alias=AliasChoices("bulk_density", "dg"))
    k_sat: str = Field(validation_alias=AliasChoices("k_sat", "K_sat", "Kr"))
    t_fcap: str = Field(validation_alias=AliasChoices("t_fcap", "T_fcap", "Tcc"))
    t_sat: str = Field(validation_alias=AliasChoices("t_sat", "T_sat", "Tsat"))
    t_wp: str = Field(validation_alias=AliasChoices("t_wp", "T_wp", "Tw"))
    rootzone_depth: str = Field(validation_alias=AliasChoices("rootzone_depth", "Zr"))
    k_c_min: str = Field(validation_alias=AliasChoices("k_c_min", "kc_min", "kcmin", "K_c_min"))
    k_c_max: str = Field(validation_alias=AliasChoices("k_c_max", "kc_max", "kcmax", "K_c_max"))


class Grid(_Section):
    grid: float


class Calibration(_Section):
    alpha: float
    b: float = Field(validation_alias=AliasChoices("b", "beta"))
    w_1: float = Field(validation_alias=AliasChoices("w_1", "w1"))
    w_2: float = Field(validation_alias=AliasChoices("w_2", "w2"))
    w_3: float = Field(validation_alias=AliasChoices("w_3", "w3"))
    rcd: float
    f: float
    alpha_gw: float
    x: float


class InitialSoilConditionsSection(_Section):
    t_ini: float = Field(validation_alias=AliasChoices("t_ini", "T_ini"))
    bfw_ini: float
    bfw_lim: float
    s_sat_ini: float = Field(validation_alias=AliasChoices("s_sat_ini", "S_sat_ini"))


class Constants(_Section):
    fpar_max: float
    fpar_min: float
    lai_max: float
    i_imp: float


class GenerateFile(_Section):
    itp: bool
    bfw: bool
    srn: bool
    eta: bool
    lfw: bool
    rec: bool
    smc: bool
    rnf: bool
    arn: bool
    tss: bool

    _parse = field_validator("*", mode="before")(str_to_bool)


class RasterFileFormat(_Section):
    map_raster_series: bool = True
    tiff_raster_series: bool = False
    no_data_value: float = -9999

    @field_validator("map_raster_series", "tiff_raster_series", mode="before")
    @classmethod
    def _flags(cls, value):
        return str_to_bool(value)

    @field_validator("no_data_value", mode="before")
    @classmethod
    def _finite_number(cls, value):
        return finite_float32(value, "RASTER_FILE_FORMAT.no_data_value")


class ModelConfigurationFile(_Section):
    """The legacy configuration file, section by section.

    Field names are the lower-case section names; the JSON keys are the
    upper-case aliases (``SIM_TIME``, ``DIRECTORIES``, ...). Both spellings are
    accepted on input and the upper-case one is written on output.
    """

    sim_time: SimTime = Field(alias="SIM_TIME")
    directories: Directories = Field(alias="DIRECTORIES")
    filename_prefixes: FilenamePrefixes = Field(alias="FILENAME_PREFIXES")
    rasters: Rasters = Field(alias="RASTERS")
    tables: Tables = Field(alias="TABLES")
    grid: Grid = Field(alias="GRID")
    calibration: Calibration = Field(alias="CALIBRATION")
    initial_soil_conditions: InitialSoilConditionsSection = Field(alias="INITIAL_SOIL_CONDITIONS")
    constants: Constants = Field(alias="CONSTANTS")
    generate_file: GenerateFile = Field(alias="GENERATE_FILE")
    raster_file_format: RasterFileFormat = Field(
        alias="RASTER_FILE_FORMAT", default_factory=RasterFileFormat
    )

    @classmethod
    def from_json(cls, path: PathInput) -> Self:
        """Read a legacy JSON file, warning about duplicated keys (the last value wins)."""
        return cls.model_validate(read_json(path))

    def resolve_paths(self, base_dir: PathInput | None) -> Self:
        """Return a copy whose relative paths are anchored on ``base_dir``.

        Absolute paths are kept; with ``base_dir=None`` the file is returned unchanged.
        """
        if base_dir is None:
            return self
        base = as_path(base_dir)

        def anchor(value):
            if value is None:
                return None
            path = Path(value)
            return value if path.is_absolute() else str(base / path)

        directories = {k: anchor(v) for k, v in self.directories.model_dump(by_alias=True).items()}
        rasters = {k: anchor(v) for k, v in self.rasters.model_dump(by_alias=True).items()}
        tables = {k: anchor(v) for k, v in self.tables.model_dump(by_alias=True).items()}
        data = self.model_dump(by_alias=True)
        data["DIRECTORIES"] = directories
        data["RASTERS"] = rasters
        data["TABLES"] = tables
        return type(self).model_validate(data)

    def to_dict(self) -> dict:
        """The canonical legacy dictionary (upper-case sections, canonical keys)."""
        return self.model_dump(by_alias=True)
