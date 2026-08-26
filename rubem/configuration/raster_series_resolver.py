"""Resolution of the raster series to one file path per simulated step.

A resolver answers "which raster does step ``n`` read?" for one series. The
legacy configuration only has directory series (one 8.3-named file per step);
format 1.0 adds dated entries and monthly sets. A step without a raster is
answered with a :class:`MissingStep` marker rather than an exception, so that
the run can decide: the NDVI and land use series fall back to the previous
raster, the precipitation, ETP and Kp series cannot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dateutil.relativedelta import relativedelta

from .._paths import PathInput, as_path
from ..file._naming import get_raster_series_filepath
from ._problems import Problem

SERIES_NAMES = ("precipitation", "etp", "kp", "ndvi", "landuse")
STRICT_SERIES = frozenset({"precipitation", "etp", "kp"})
FALLBACK_SERIES = frozenset({"ndvi", "landuse"})


@dataclass(frozen=True)
class MissingStep:
    """A step the series has no raster for."""

    series: str
    step: int
    reason: str

    def __str__(self) -> str:
        return f"{self.series} series has no raster for step {self.step}: {self.reason}"


def step_to_date(step: int, alignment: date) -> date:
    """The first day of the month simulated at ``step`` (step 1 is the alignment month)."""
    if step < 1:
        raise ValueError(f"steps start at 1, got {step}.")
    return date(alignment.year, alignment.month, 1) + relativedelta(months=step - 1)


def date_to_step(day: date, alignment: date) -> int:
    """The step whose month contains ``day``."""
    return (day.year - alignment.year) * 12 + (day.month - alignment.month) + 1


class DirectorySeriesResolver:
    """One raster per step in a directory: PCRaster 8.3 names or GeoTIFF files.

    The format is detected from the files present (``<prefix>`` plus the 8.3
    step suffix, or the GeoTIFF names of the model outputs); a directory that
    mixes both formats for the same prefix is refused.
    """

    def __init__(self, series: str, directory: PathInput, prefix: str) -> None:
        self.series = series
        # Absolutised once, here: a later change of the working directory must
        # not move where a relative directory resolves to.
        self.directory = str(as_path(directory).absolute())
        self.prefix = prefix
        self.format = self.__detect_format()

    def __detect_format(self) -> str:
        from ..file._naming import geotiff_series_pattern, raster_series_pattern

        base = Path(self.directory)
        if not base.is_dir():
            return "map"
        names = [entry.name for entry in base.iterdir() if entry.is_file()]
        maps = any(raster_series_pattern(self.prefix).match(name) for name in names)
        geotiffs = (
            any(geotiff_series_pattern(self.prefix).match(name) for name in names)
            if len(self.prefix) < 10
            else False
        )
        if maps and geotiffs:
            raise ValueError(
                f"The {self.series} series in {base} mixes PCRaster maps and GeoTIFF files "
                f"for the prefix '{self.prefix}'."
            )
        return "geotiff" if geotiffs else "map"

    def path_for_step(self, step: int) -> str | MissingStep:
        if self.format == "geotiff":
            from ..file._readers import geotiff_series_member

            member = geotiff_series_member(self.directory, self.prefix, step)
            if member is None:
                return MissingStep(
                    self.series, step, f"no GeoTIFF for step {step} in {self.directory}"
                )
            return str(member)
        path = get_raster_series_filepath(self.directory, self.prefix, step)
        if not Path(path).is_file():
            return MissingStep(self.series, step, f"{path} does not exist")
        return path

    def __repr__(self) -> str:
        return f"DirectorySeriesResolver({self.series!r}, {self.directory!r}, {self.prefix!r})"


class DatedSeriesResolver:
    """Rasters valid over date ranges (both bounds inclusive, whole months)."""

    def __init__(
        self,
        series: str,
        entries: list[tuple[str, date, date]],
        alignment: date,
    ) -> None:
        self.series = series
        self.alignment = alignment
        # Bounds are resolved by month (path_for_step below), so they are
        # normalised to the first of the month before the inversion and
        # overlap checks: two entries sharing a month must collide even when
        # their raw dates do not, and the entries are sorted by start so that
        # disjoint entries given out of order are not mistaken for overlapping.
        normalised = []
        for path, start, end in entries:
            start = date(start.year, start.month, 1)
            end = date(end.year, end.month, 1)
            if start > end:
                raise ValueError(
                    f"{series} series entry {path} has from ({start}) after to ({end})."
                )
            normalised.append((str(as_path(path)), start, end))
        normalised.sort(key=lambda entry: entry[1])
        for (_, _, end), (path, start, _) in zip(normalised, normalised[1:]):
            if start <= end:
                raise ValueError(
                    f"{series} series entries overlap: {path} starts on {start}, before the "
                    f"previous entry ends ({end})."
                )
        self.entries = normalised

    def __repr__(self) -> str:
        return f"DatedSeriesResolver({self.series!r}, {len(self.entries)} entries)"

    def path_for_step(self, step: int) -> str | MissingStep:
        day = step_to_date(step, self.alignment)
        for path, start, end in self.entries:
            if start <= day <= end:
                return path
        return MissingStep(self.series, step, f"no entry covers {day:%Y-%m}")


class MonthlySeriesResolver:
    """Twelve rasters repeated every year, optionally replaced from a year on."""

    def __init__(
        self,
        series: str,
        monthly: dict[int, str],
        alignment: date,
        yearly_from: int | None = None,
        yearly_file_path: PathInput | None = None,
    ) -> None:
        if sorted(monthly) != list(range(1, 13)):
            raise ValueError(f"{series} series needs the twelve months, got {sorted(monthly)}.")
        if (yearly_from is None) != (yearly_file_path is None):
            raise ValueError(f"{series} series needs yearly_from and yearly_file_path together.")
        self.series = series
        self.alignment = alignment
        self.monthly = {month: str(as_path(path)) for month, path in monthly.items()}
        self.yearly_from = yearly_from
        self.yearly_file_path = str(as_path(yearly_file_path)) if yearly_file_path else None

    def __repr__(self) -> str:
        return (
            f"MonthlySeriesResolver({self.series!r}, 12 rasters, yearly_from={self.yearly_from!r})"
        )

    def path_for_step(self, step: int) -> str | MissingStep:
        day = step_to_date(step, self.alignment)
        if self.yearly_from is not None and day.year >= self.yearly_from:
            return self.yearly_file_path
        return self.monthly[day.month]


def check_coverage(
    resolvers: dict[str, DirectorySeriesResolver | DatedSeriesResolver | MonthlySeriesResolver],
    first_step: int,
    last_step: int,
) -> list[Problem]:
    """Report the steps each series cannot provide within the simulated window.

    Precipitation, ETP and Kp gaps are blocking; NDVI and land use need the
    first step (blocking) and later gaps are reported (the run reuses the
    previous raster). Paths returned by dated and monthly resolvers must exist.
    """
    problems: list[Problem] = []
    for name, resolver in resolvers.items():
        missing = []
        for step in range(first_step, last_step + 1):
            answer = resolver.path_for_step(step)
            if isinstance(answer, MissingStep) or not Path(answer).is_file():
                missing.append(step)
        if not missing:
            continue
        if name in STRICT_SERIES:
            problems.append(
                Problem(
                    description=f"The {name} raster series is incomplete.",
                    reason=f"Missing steps {missing} of the required {first_step}-{last_step}.",
                    implication="The simulation cannot run without these rasters.",
                    blocking=True,
                )
            )
            continue
        if first_step in missing:
            problems.append(
                Problem(
                    description=f"The {name} raster series lacks the first step.",
                    reason=f"Step {first_step} is missing.",
                    implication="The simulation cannot start without it.",
                    blocking=True,
                )
            )
        later = [step for step in missing if step != first_step]
        if later:
            problems.append(
                Problem(
                    description=f"The {name} raster series has gaps.",
                    reason=f"Missing steps {later} of the required {first_step}-{last_step}.",
                    implication="The run reuses the previous raster for each missing step.",
                )
            )
    return problems


def resolvers_from_legacy(raster_series) -> dict[str, DirectorySeriesResolver]:
    """Directory resolvers for a legacy :class:`InputRasterSeries`."""
    return {
        name: DirectorySeriesResolver(
            name,
            getattr(raster_series, f"{name}_directory"),
            getattr(raster_series, f"{name}_filename_prefix"),
        )
        for name in SERIES_NAMES
    }


def resolvers_from_v1(file) -> dict:
    """Resolvers for a :class:`ModelConfigurationFileV1`, one per series."""
    from .model_configuration_file_v1 import DirectoryRasterSeries, MonthlyRasterSeries

    period = file.simulation_period
    alignment = period.alignment or period.start
    resolvers = {}
    for name in SERIES_NAMES:
        spec = getattr(file.raster_series, name)
        if isinstance(spec, DirectoryRasterSeries):
            resolvers[name] = DirectorySeriesResolver(name, spec.dir_path, spec.files_prefix)
        elif isinstance(spec, MonthlyRasterSeries):
            resolvers[name] = MonthlySeriesResolver(
                name,
                {entry.month: entry.file_path for entry in spec.monthly},
                alignment,
                spec.yearly_from,
                spec.yearly_file_path,
            )
        else:
            resolvers[name] = DatedSeriesResolver(
                name,
                [
                    (entry.file_path, file.resolve_date(entry.from_), file.resolve_date(entry.to))
                    for entry in spec
                ],
                alignment,
            )
    return resolvers


def check_series_member_crs(file: PathInput, reference_projection: str | None) -> Problem | None:
    """A GeoTIFF series member must share the reference coordinate reference system.

    Mirrors the CRS branch of ``InputRasterFiles.__check_geometry`` for the
    static rasters. ``reference_projection`` is the clone's own CRS, else the
    georeference's, else the DEM's (see
    :func:`~rubem.configuration.output_raster_base.reference_crs`); the check
    is skipped when it or the member's own CRS is empty, matching the same
    "unknown CRS is not a mismatch" rule.
    """
    from ..file._readers import is_geotiff

    if not reference_projection or not is_geotiff(file):
        return None
    from .output_raster_base import read_raster_geometry, same_crs

    _, _, _, projection = read_raster_geometry(file)
    if projection and not same_crs(projection, reference_projection):
        return Problem(
            description="Input raster series member has another coordinate reference system.",
            reason="The reference coordinate reference system (the clone's own, else the "
            "georeference's, else the DEM's) is different.",
            implication="The simulation cannot run with this raster.",
            file=str(file),
            blocking=True,
        )
    return None


def validate_resolved_series(
    resolvers: dict, first_step: int, last_step: int, reference_projection: str | None = None
) -> list[Problem]:
    """Validate the rasters the resolvers answer over the simulated window.

    Every distinct file is opened once and checked with the data rules and
    the content rules of its series (``kp`` positive, NDVI below one, land use
    integer classes), on top
    of the coverage report of :func:`check_coverage`. A GeoTIFF member whose
    CRS differs from ``reference_projection`` (when given) is a blocking problem.
    """
    from ..validation.raster_content import check_below_one, check_integer_values, check_positive
    from ..validation.raster_data_rules import RasterDataRules
    from ..validation.raster_map_validator import RasterMapValidator
    from ._ranges import raster_ranges
    from .raster_map import RasterMap

    problems = check_coverage(resolvers, first_step, last_step)
    ranges = raster_ranges()
    rules = {
        "etp": RasterDataRules.FORBID_NO_DATA,
        "precipitation": RasterDataRules.FORBID_NO_DATA,
        "ndvi": RasterDataRules.FORBID_NO_DATA,
        "kp": RasterDataRules.FORBID_NO_DATA,
        "landuse": RasterDataRules.FORBID_NO_DATA | RasterDataRules.FORBID_ALL_ZEROES,
    }
    content_rules = {
        "kp": lambda values, no_data, file: check_positive(
            values, no_data, file, "Class A pan coefficient (Kp)"
        ),
        "ndvi": lambda values, no_data, file: check_below_one(values, no_data, file, "NDVI"),
        "landuse": lambda values, no_data, file: check_integer_values(
            values, no_data, file, "Land use"
        ),
    }
    for name, resolver in resolvers.items():
        files = []
        for step in range(first_step, last_step + 1):
            answer = resolver.path_for_step(step)
            if not isinstance(answer, MissingStep) and answer not in files:
                files.append(answer)
        for file in files:
            if not Path(file).is_file():
                continue  # Already reported by the coverage check.
            crs_problem = check_series_member_crs(file, reference_projection)
            if crs_problem is not None:
                problems.append(crs_problem)
            with RasterMap(file, ranges[name], rules[name]) as raster:
                valid, errors = RasterMapValidator().validate(raster)
                rule = content_rules.get(name)
                if rule is not None:
                    band = raster.bands[0]
                    problem = rule(band.data_array, band.no_data_value, file)
                    if problem is not None:
                        problems.append(problem)
            if not valid:
                problems.append(
                    Problem(
                        description="Raster file data validation failed.",
                        reason=f"Data rules violation(s): {[str(error) for error in errors]}",
                        implication="This may lead to unexpected results.",
                        file=file,
                    )
                )
    return problems
