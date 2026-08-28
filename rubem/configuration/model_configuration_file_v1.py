"""Configuration file format 1.0 (issues #179, #181, #182, #184; discussion #126).

The format is strict: unknown keys are rejected everywhere, and ``version``
must be ``"1.0"``. It is not yet read by the loader nor exposed on the
command line; the model, its conversions from and to the legacy format and
the resolution of the raster series are prepared here.

Raster series may be given in three ways: a list of dated entries
(``file_path``, ``from``, ``to``), a monthly set of twelve rasters optionally
replaced by one raster from a given year on (``monthly``, ``yearly_from``,
``yearly_file_path``), or a directory with a common file prefix (``dir_path``,
``files_prefix``). The dates ``from``/``to`` accept the JSON-pointer references
``{"$ref": "#/simulation_period/start"}`` and ``{"$ref": "#/simulation_period/finish"}``.
"""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self
from .modflow_configuration import ModflowConfiguration

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .._paths import PathInput, as_path
from ._json import DuplicateKeyWarning
from .model_configuration_file import ModelConfigurationFile, finite_float32

VERSION = "1.0"

SERIES_NAMES = ("precipitation", "etp", "kp", "ndvi", "landuse")
VARIABLE_IDS = ("itp", "bfw", "srn", "eta", "lfw", "rec", "smc", "rnf", "arn")

_START_REF = "#/simulation_period/start"
_FINISH_REF = "#/simulation_period/finish"


_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _reject_numeric_date(value):
    """Format 1.0 dates are ISO strings, ``YYYY-MM-DD`` and nothing else.

    A bare number is a Unix timestamp trap (pydantic reads it as one), and
    pydantic's default date parsing is otherwise lenient: it also accepts a
    quoted timestamp ("946684800") and a full datetime string
    ("2000-01-01T00:00:00"). Both are rejected here, before pydantic parses
    the value at all.
    """
    if isinstance(value, (bool, int, float)):
        raise ValueError(f"expected an ISO date string (YYYY-MM-DD), got {value!r}")
    if isinstance(value, str) and not _ISO_DATE.match(value):
        raise ValueError(f"expected an ISO date string (YYYY-MM-DD), got {value!r}")
    return value


IsoDate = Annotated[date, BeforeValidator(_reject_numeric_date)]


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Metadata(_Strict):
    """Free-form description of the simulation (issue #182)."""

    title: str | None = None
    description: str | None = None
    keywords: list[str] = []
    authors: list[str] = []
    contact: list[str] = []
    creation_date: IsoDate | None = None
    last_update: IsoDate | None = None
    license: str | None = None


class SimulationPeriod(_Strict):
    """ISO dates; ``finish`` is the last simulated month."""

    start: IsoDate
    finish: IsoDate
    alignment: IsoDate | None = None

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.start >= self.finish:
            raise ValueError(f"start ({self.start}) must be before finish ({self.finish}).")
        if self.alignment is not None and self.alignment > self.start:
            raise ValueError(
                f"alignment ({self.alignment}) must not be after start ({self.start})."
            )
        return self


class DateRef(_Strict):
    """A JSON-pointer reference to a simulation period bound."""

    ref: Literal["#/simulation_period/start", "#/simulation_period/finish"] = Field(alias="$ref")


DateOrRef = IsoDate | DateRef


class DatedRaster(_Strict):
    """One raster valid from ``from`` to ``to`` (both inclusive, whole months)."""

    file_path: str
    from_: DateOrRef = Field(alias="from")
    to: DateOrRef


class MonthlyRaster(_Strict):
    month: Annotated[int, Field(ge=1, le=12)]
    file_path: str


class MonthlyRasterSeries(_Strict):
    """Twelve rasters repeated every year, optionally replaced from ``yearly_from`` on."""

    monthly: list[MonthlyRaster]
    yearly_from: int | None = None
    yearly_file_path: str | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        months = sorted(entry.month for entry in self.monthly)
        if months != list(range(1, 13)):
            raise ValueError(f"monthly must list each month 1-12 exactly once, got {months}.")
        if (self.yearly_from is None) != (self.yearly_file_path is None):
            raise ValueError("yearly_from and yearly_file_path must be given together.")
        return self


class DirectoryRasterSeries(_Strict):
    """One raster per step, named ``<files_prefix>`` plus the PCRaster 8.3 step suffix."""

    dir_path: str
    files_prefix: str


RasterSeriesSpec = list[DatedRaster] | MonthlyRasterSeries | DirectoryRasterSeries


class RasterSeries(_Strict):
    precipitation: RasterSeriesSpec
    etp: RasterSeriesSpec
    kp: RasterSeriesSpec
    ndvi: RasterSeriesSpec
    landuse: RasterSeriesSpec

    @field_validator(*SERIES_NAMES)
    @classmethod
    def _non_empty(cls, value):
        if isinstance(value, list) and not value:
            raise ValueError("a dated raster series needs at least one entry.")
        return value


class Rasters(_Strict):
    dem: str
    clone: str
    ndvi_max: str
    ndvi_min: str
    soil: str
    ldd: str | None = None
    samples: str | None = None
    georeference: str | None = None
    zones: str | None = None


class LookupTables(_Strict):
    rainy_days: str
    a_i: str
    a_o: str
    a_s: str
    a_v: str
    manning: str
    bulk_density: str
    k_sat: str
    t_fcap: str
    t_sat: str
    t_wp: str
    rootzone_depth: str
    kc_min: str
    kc_max: str


class RasterInfo(_Strict):
    grid_size: float


class CalibrationParameters(_Strict):
    alpha: float
    b: float
    w_1: float
    w_2: float
    w_3: float
    rcd: float
    f: float
    alpha_gw: float
    x: float


class InitialSoilConditions(_Strict):
    t_ini: float
    bfw_ini: float
    bfw_lim: float
    s_sat_ini: float


class Constants(_Strict):
    fpar_max: float
    fpar_min: float
    lai_max: float
    i_imp: float


class RasterFormat(StrEnum):
    GEOTIFF = "GeoTIFF"
    PCRASTER_MAP = "PCRasterMap"


class TimeSeriesFormat(StrEnum):
    CSV = "CSV"
    PCRASTER_TSS = "PCRasterTSS"


class _VariableSelection(_Strict):
    itp: bool = False
    bfw: bool = False
    srn: bool = False
    eta: bool = False
    lfw: bool = False
    rec: bool = False
    smc: bool = False
    rnf: bool = False
    arn: bool = False

    def enabled(self) -> tuple[str, ...]:
        return tuple(name for name in VARIABLE_IDS if getattr(self, name))


def _unique(values):
    seen = []
    for value in values:
        if value in seen:
            raise ValueError(f"formats lists {value!r} more than once.")
        seen.append(value)
    return values


class RasterSeriesOutput(_VariableSelection):
    formats: list[RasterFormat] = []
    no_data_value: float = -9999

    _unique = field_validator("formats")(_unique)

    @field_validator("no_data_value", mode="before")
    @classmethod
    def _finite_number(cls, value):
        return finite_float32(value, "model_simulation_output.raster_series.no_data_value")

    @model_validator(mode="after")
    def _formats_when_enabled(self) -> Self:
        if self.enabled() and not self.formats:
            raise ValueError("raster_series enables variables but lists no format.")
        return self


class Aggregation(StrEnum):
    """How the time series values are aggregated in space."""

    POINT = "point"
    SUBCATCHMENT = "subcatchment"
    ZONES = "zones"


class TimeSeriesOutput(_VariableSelection):
    """Time series selection.

    ``aggregation`` chooses the areas the values are averaged over: ``point``
    (the cells sharing each sample id, as before), ``subcatchment`` (the
    catchment upstream of each sample over the LDD) or ``zones`` (the areas
    of the ``rasters.zones`` raster, whose ids are remapped to ``1..N`` and
    recorded in ``zones_mapping.csv``).
    """

    formats: list[TimeSeriesFormat] = []
    aggregation: Aggregation = Aggregation.POINT

    _unique = field_validator("formats")(_unique)

    @model_validator(mode="after")
    def _formats_when_enabled(self) -> Self:
        if self.enabled() and not self.formats:
            raise ValueError("time_series_samples enables variables but lists no format.")
        return self


class SimulationOutput(_Strict):
    dir_path: str
    raster_series: RasterSeriesOutput = RasterSeriesOutput()
    time_series_samples: TimeSeriesOutput = TimeSeriesOutput()


class ModelConfigurationFileV1(_Strict):
    """The configuration file, format 1.0."""

    version: Literal["1.0"]
    metadata: Metadata = Metadata()
    simulation_period: SimulationPeriod
    raster_series: RasterSeries
    rasters: Rasters
    lookup_tables: LookupTables
    raster_info: RasterInfo
    model_calibration_parameters: CalibrationParameters
    model_initial_soil_conditions: InitialSoilConditions
    model_constants: Constants
    model_simulation_output: SimulationOutput
    modflow: ModflowConfiguration = Field(
        default_factory=ModflowConfiguration
    )

    @model_validator(mode="after")
    def _check_aggregation_inputs(self) -> Self:
        samples = self.model_simulation_output.time_series_samples
        if not samples.enabled():
            return self
        if samples.aggregation is Aggregation.ZONES and not self.rasters.zones:
            raise ValueError("time_series_samples.aggregation 'zones' needs rasters.zones.")
        if samples.aggregation is not Aggregation.ZONES and not self.rasters.samples:
            raise ValueError(
                f"time_series_samples.aggregation '{samples.aggregation.value}' needs rasters.samples."
            )
        return self

    @classmethod
    def from_json(cls, path: PathInput) -> Self:
        """Read a 1.0 file. Duplicated keys are an error in this format.

        :raises ValueError: On duplicated keys.
        """
        import json

        file = as_path(path)
        collector = DuplicateKeyWarning()
        with Path(file).open(encoding="utf-8") as handle:
            data = json.load(handle, object_pairs_hook=collector.hook)
        if collector.duplicates:
            raise ValueError(
                f"{file}: duplicated key(s) {sorted(set(collector.duplicates))} are not allowed "
                "in configuration format 1.0."
            )
        return cls.model_validate(data)

    def resolve_date(self, value: DateOrRef) -> date:
        """Resolve a ``from``/``to`` value, following the period references."""
        if isinstance(value, date):
            return value
        if value.ref == _START_REF:
            return self.simulation_period.start
        return self.simulation_period.finish

    def resolve_paths(self, base_dir: PathInput | None) -> Self:
        """Return a copy whose relative paths are anchored on ``base_dir``."""
        if base_dir is None:
            return self
        base = as_path(base_dir)

        def anchor(value):
            if value is None:
                return None
            path = Path(value)
            return value if path.is_absolute() else str(base / path)

        data = self.model_dump(by_alias=True, mode="json")
        data["rasters"] = {k: anchor(v) for k, v in data["rasters"].items()}
        data["lookup_tables"] = {k: anchor(v) for k, v in data["lookup_tables"].items()}
        data["model_simulation_output"]["dir_path"] = anchor(
            data["model_simulation_output"]["dir_path"]
        )
        data["modflow"] = (
            self.modflow
            .resolve_paths(base_dir)
            .model_dump(mode="json")
        )
        for name, spec in data["raster_series"].items():
            if isinstance(spec, list):
                for entry in spec:
                    entry["file_path"] = anchor(entry["file_path"])
            elif "monthly" in spec:
                for entry in spec["monthly"]:
                    entry["file_path"] = anchor(entry["file_path"])
                spec["yearly_file_path"] = anchor(spec.get("yearly_file_path"))
            else:
                spec["dir_path"] = anchor(spec["dir_path"])
        return type(self).model_validate(data)

    def to_dict(self) -> dict:
        """The JSON document (ISO dates, ``$ref`` objects kept)."""
        return self.model_dump(by_alias=True, mode="json", exclude_none=True)

    # ----- conversions -----------------------------------------------------

    @classmethod
    def from_legacy(cls, legacy: ModelConfigurationFile, metadata: dict | None = None) -> Self:
        """Build a 1.0 configuration equivalent to a legacy one.

        Directory series become ``dir_path``/``files_prefix`` entries, the
        period keeps its dates, the legacy time-series flag becomes the
        ``time_series_samples`` selection (CSV only, as the legacy run writes),
        and the raster formats follow ``RASTER_FILE_FORMAT``.
        """
        rff = legacy.raster_file_format
        formats = []
        if rff.map_raster_series:
            formats.append(RasterFormat.PCRASTER_MAP)
        if rff.tiff_raster_series:
            formats.append(RasterFormat.GEOTIFF)
        flags = {name: getattr(legacy.generate_file, name) for name in VARIABLE_IDS}
        tss = legacy.generate_file.tss
        data = {
            "version": VERSION,
            "metadata": metadata or {},
            "simulation_period": {
                "start": legacy.sim_time.start.isoformat(),
                "finish": legacy.sim_time.end.isoformat(),
                **(
                    {"alignment": legacy.sim_time.alignment.isoformat()}
                    if legacy.sim_time.alignment
                    else {}
                ),
            },
            "modflow": legacy.modflow.model_dump(
                mode="json",
                exclude_none=True,
            ),
            "raster_series": {
                "precipitation": {
                    "dir_path": legacy.directories.prec,
                    "files_prefix": legacy.filename_prefixes.prec_prefix,
                },
                "etp": {
                    "dir_path": legacy.directories.etp,
                    "files_prefix": legacy.filename_prefixes.etp_prefix,
                },
                "kp": {
                    "dir_path": legacy.directories.kp,
                    "files_prefix": legacy.filename_prefixes.kp_prefix,
                },
                "ndvi": {
                    "dir_path": legacy.directories.ndvi,
                    "files_prefix": legacy.filename_prefixes.ndvi_prefix,
                },
                "landuse": {
                    "dir_path": legacy.directories.landuse,
                    "files_prefix": legacy.filename_prefixes.landuse_prefix,
                },
            },
            "rasters": {
                k: v for k, v in legacy.rasters.model_dump(by_alias=True).items() if v is not None
            },
            "lookup_tables": {
                "rainy_days": legacy.tables.rainydays,
                "a_i": legacy.tables.a_i,
                "a_o": legacy.tables.a_o,
                "a_s": legacy.tables.a_s,
                "a_v": legacy.tables.a_v,
                "manning": legacy.tables.manning,
                "bulk_density": legacy.tables.bulk_density,
                "k_sat": legacy.tables.k_sat,
                "t_fcap": legacy.tables.t_fcap,
                "t_sat": legacy.tables.t_sat,
                "t_wp": legacy.tables.t_wp,
                "rootzone_depth": legacy.tables.rootzone_depth,
                "kc_min": legacy.tables.k_c_min,
                "kc_max": legacy.tables.k_c_max,
            },
            "raster_info": {"grid_size": legacy.grid.grid},
            "model_calibration_parameters": legacy.calibration.model_dump(by_alias=True),
            "model_initial_soil_conditions": legacy.initial_soil_conditions.model_dump(
                by_alias=True
            ),
            "model_constants": legacy.constants.model_dump(by_alias=True),
            "model_simulation_output": {
                "dir_path": legacy.directories.output,
                "raster_series": {
                    **flags,
                    # The formats follow RASTER_FILE_FORMAT regardless of which
                    # variables are enabled: format 1.0 allows formats without
                    # enabled variables, and the round trip through to_legacy()
                    # must recover map_raster_series/tiff_raster_series either way.
                    "formats": [f.value for f in formats],
                    "no_data_value": rff.no_data_value,
                },
                "time_series_samples": {
                    **{name: tss and flag for name, flag in flags.items()},
                    "formats": [TimeSeriesFormat.CSV.value] if tss and any(flags.values()) else [],
                },
            },
        }
        return cls.model_validate(data)

    def to_legacy(self) -> ModelConfigurationFile:
        """Build the legacy equivalent, when every series is a directory series.

        :raises ValueError: If a series is not given as a directory with a
            prefix, or the outputs use a combination the legacy file cannot
            express (time series without their raster series, formats other
            than CSV for the tables).
        """
        series = {}
        for name in SERIES_NAMES:
            spec = getattr(self.raster_series, name)
            if not isinstance(spec, DirectoryRasterSeries):
                raise ValueError(
                    f"raster_series.{name} is not a directory series; the legacy format "
                    "only expresses directory series."
                )
            series[name] = spec
        out = self.model_simulation_output
        raster_flags = {name: getattr(out.raster_series, name) for name in VARIABLE_IDS}
        tss_flags = {name: getattr(out.time_series_samples, name) for name in VARIABLE_IDS}
        if any(tss_flags[name] and not raster_flags[name] for name in VARIABLE_IDS):
            raise ValueError(
                "the legacy format cannot enable a time series without its raster series."
            )
        if out.time_series_samples.formats not in ([], [TimeSeriesFormat.CSV]):
            raise ValueError("the legacy format only writes CSV time series.")
        if out.time_series_samples.aggregation is not Aggregation.POINT:
            raise ValueError("the legacy format only samples the time series at points.")
        if self.rasters.zones:
            raise ValueError("the legacy format has no zones raster.")
        tss = any(tss_flags.values())
        if tss and any(raster_flags[name] and not tss_flags[name] for name in VARIABLE_IDS):
            raise ValueError(
                "the legacy format writes the time series of every enabled variable or none."
            )
        data = {
            "SIM_TIME": {
                "start": self.simulation_period.start.strftime("%d/%m/%Y"),
                "end": self.simulation_period.finish.strftime("%d/%m/%Y"),
                "alignment": (
                    self.simulation_period.alignment.strftime("%d/%m/%Y")
                    if self.simulation_period.alignment
                    else None
                ),
            },
            "DIRECTORIES": {
                "output": out.dir_path,
                "etp": series["etp"].dir_path,
                "prec": series["precipitation"].dir_path,
                "ndvi": series["ndvi"].dir_path,
                "kp": series["kp"].dir_path,
                "landuse": series["landuse"].dir_path,
            },
            "FILENAME_PREFIXES": {
                "etp_prefix": series["etp"].files_prefix,
                "prec_prefix": series["precipitation"].files_prefix,
                "ndvi_prefix": series["ndvi"].files_prefix,
                "kp_prefix": series["kp"].files_prefix,
                "landuse_prefix": series["landuse"].files_prefix,
            },
            "RASTERS": self.rasters.model_dump(exclude={"zones"}),
            "MODFLOW": self.modflow.model_dump(
                mode="json",
                exclude_none=True,
            ),
            "TABLES": {
                "rainydays": self.lookup_tables.rainy_days,
                "a_i": self.lookup_tables.a_i,
                "a_o": self.lookup_tables.a_o,
                "a_s": self.lookup_tables.a_s,
                "a_v": self.lookup_tables.a_v,
                "manning": self.lookup_tables.manning,
                "bulk_density": self.lookup_tables.bulk_density,
                "k_sat": self.lookup_tables.k_sat,
                "t_fcap": self.lookup_tables.t_fcap,
                "t_sat": self.lookup_tables.t_sat,
                "t_wp": self.lookup_tables.t_wp,
                "rootzone_depth": self.lookup_tables.rootzone_depth,
                "k_c_min": self.lookup_tables.kc_min,
                "k_c_max": self.lookup_tables.kc_max,
            },
            "GRID": {"grid": self.raster_info.grid_size},
            "CALIBRATION": self.model_calibration_parameters.model_dump(),
            "INITIAL_SOIL_CONDITIONS": self.model_initial_soil_conditions.model_dump(),
            "CONSTANTS": self.model_constants.model_dump(),
            "GENERATE_FILE": {**raster_flags, "tss": tss},
            "RASTER_FILE_FORMAT": {
                "map_raster_series": RasterFormat.PCRASTER_MAP in out.raster_series.formats,
                "tiff_raster_series": RasterFormat.GEOTIFF in out.raster_series.formats,
                "no_data_value": out.raster_series.no_data_value,
            },
        }
        return ModelConfigurationFile.model_validate(data)
