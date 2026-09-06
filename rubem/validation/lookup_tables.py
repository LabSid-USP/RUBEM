"""Content checks of the lookup tables the model reads with PCRaster.

A PCRaster lookup table is a whitespace-separated text file whose last column
is the value and whose preceding columns are keys; a key is a single number or
an interval such as ``[1,3]``, ``<1,3]`` or ``[1,>``. The model's tables use
one key column (a land use or soil class, or a month).

:func:`check_lookup_tables` checks each table on its own and the relations
between tables; :func:`check_runoff_coefficient_domain` additionally checks the
domain of the weighted runoff coefficient ``C_wp <= 1`` (supplement S5 to S9)
for every pair of a land use class and a soil class, which also needs the
calibration weights ``w1``, ``w2`` and ``w3``.
"""

import logging
import math
import re
from collections.abc import Iterable
from pathlib import Path

from ..configuration._problems import Problem

logger = logging.getLogger(__name__)

_NUMBER = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")
_INTERVAL = re.compile(r"^[\[<][^,]*,[^,]*[\]>]$")


class LookupTableError(ValueError):
    """The lookup table cannot be parsed."""


def _interval_bounds_are_numeric(key: str) -> bool:
    """Whether the bounds present in an interval key such as ``[1,3]`` or ``<1,>`` are numeric.

    At least one bound must be given (``[,]`` carries no information and is
    rejected); a bound that is present must be a number.
    """
    low_text, high_text = key[1:-1].split(",")
    low_text, high_text = low_text.strip(), high_text.strip()
    if not low_text and not high_text:
        return False
    return (not low_text or _NUMBER.match(low_text) is not None) and (
        not high_text or _NUMBER.match(high_text) is not None
    )


def read_lookup_table(path) -> list[tuple[tuple[str, ...], float]]:
    """Return the ``(keys, value)`` rows of a PCRaster lookup table.

    :param path: The table file.
    :raises LookupTableError: On an empty table, a row without a value, a row
        with more than one key column, a value or key that is neither a
        number nor an interval, or an interval key without a numeric bound.
    """
    rows = []
    text = Path(path).read_text(encoding="utf8")
    for number, line in enumerate(text.splitlines(), start=1):
        columns = line.split()
        if not columns:
            continue
        if len(columns) < 2:
            raise LookupTableError(f"{path}: line {number} has no value column: {line!r}")
        if len(columns) > 2:
            raise LookupTableError(f"{path}: line {number} has more than one key column: {line!r}")
        key, value = columns
        if not _NUMBER.match(value):
            raise LookupTableError(f"{path}: line {number} has a non-numeric value {value!r}")
        if not (_NUMBER.match(key) or _INTERVAL.match(key)):
            raise LookupTableError(f"{path}: line {number} has an invalid key {key!r}")
        if _INTERVAL.match(key) and not _interval_bounds_are_numeric(key):
            raise LookupTableError(
                f"{path}: line {number} has an interval key with invalid bounds {key!r}"
            )
        rows.append(((key,), float(value)))
    if not rows:
        raise LookupTableError(f"{path}: the lookup table is empty")
    return rows


def _in_interval(value: float, interval: str) -> bool:
    """Whether ``value`` lies in a PCRaster key interval such as ``[1,3]`` or ``<1,>``."""
    low_text, high_text = interval[1:-1].split(",")
    low_ok = (
        True
        if not low_text.strip()
        else (value >= float(low_text) if interval[0] == "[" else value > float(low_text))
    )
    high_ok = (
        True
        if not high_text.strip()
        else (value <= float(high_text) if interval[-1] == "]" else value < float(high_text))
    )
    return low_ok and high_ok


def _canonical(key: str) -> str:
    """Canonical spelling of a key, so that ``1``, ``01`` and ``1.0`` are one class.

    Interval keys are returned unchanged.
    """
    if not _NUMBER.match(key):
        return key
    number = float(key)
    return str(int(number)) if number.is_integer() else repr(number)


def _values_by_key(path) -> dict[tuple[str, ...], float]:
    return {
        tuple(_canonical(key) for key in keys): value for keys, value in read_lookup_table(path)
    }


def _problem(description: str, reason: str, path, blocking: bool) -> Problem:
    return Problem(
        description=description,
        reason=reason,
        implication="The simulation cannot run with this table."
        if blocking
        else "This may lead to unexpected results.",
        file=str(path),
        blocking=blocking,
    )


def _check_positive(label: str, path, problems: list[Problem]) -> dict | None:
    try:
        values = _values_by_key(path)
    except (OSError, LookupTableError) as e:
        problems.append(_problem(f"{label} lookup table cannot be read.", str(e), path, True))
        return None
    bad = [k for k, v in values.items() if not (math.isfinite(v) and v > 0)]
    if bad:
        problems.append(
            _problem(
                f"{label} lookup table has non-positive values.",
                f"Keys with values <= 0: {[' '.join(k) for k in bad]}.",
                path,
                True,
            )
        )
    return values


def _check_pair(
    label: str,
    first_path,
    second_path,
    relation,
    relation_text: str,
    problems: list[Problem],
    blocking: bool = True,
) -> None:
    try:
        first = _values_by_key(first_path)
        second = _values_by_key(second_path)
    except (OSError, LookupTableError):
        return  # Already reported by the single-table checks.
    missing = sorted(set(first) ^ set(second))
    if missing:
        problems.append(
            _problem(
                f"{label} lookup tables do not share their keys.",
                f"Keys present in only one of the tables: {[' '.join(k) for k in missing]}.",
                second_path,
                True,
            )
        )
    bad = [k for k in first if k in second and not relation(first[k], second[k])]
    if bad:
        problems.append(
            _problem(
                f"{label} lookup tables violate {relation_text}.",
                f"Keys: {[' '.join(k) for k in bad]}.",
                second_path,
                blocking,
            )
        )


def check_lookup_tables(tables) -> list[Problem]:
    """Check the content of the model's lookup tables.

    Blocking: unreadable tables; ``dg``, ``Zr``, ``Tsat``, ``manning`` and the
    rainy days must be positive; ``Tcc > Tw`` for every class, with the same
    classes in both tables; the rainy days table must cover the twelve
    months. Warning: ``kc_max < kc_min`` for a class, and the area fractions
    ``a_i``, ``a_o``, ``a_s`` and ``a_v`` of a land use class not adding up
    to one.

    :param tables: An :class:`~rubem.configuration.input_table_files.InputTableFiles`.
    :return: The problems found, blocking ones flagged.
    """
    problems: list[Problem] = []

    rainy_days = _check_positive("Rainy days", tables.rainy_days, problems)
    if rainy_days is not None:
        months = set(range(1, 13))
        covered: set[float] = set()
        for key in rainy_days:
            if len(key) != 1:
                continue
            (item,) = key
            if _NUMBER.match(item):
                covered.add(float(item))
            elif _INTERVAL.match(item):
                covered.update(month for month in months if _in_interval(month, item))
        missing = sorted(months - covered)
        if missing:
            problems.append(
                _problem(
                    "Rainy days lookup table does not cover every month.",
                    f"Missing months: {missing}.",
                    tables.rainy_days,
                    True,
                )
            )

    _check_positive("Manning's roughness coefficient", tables.manning, problems)
    _check_positive("Bulk density (dg)", tables.bulk_density, problems)
    _check_positive("Rootzone depth (Zr)", tables.rootzone_depth, problems)
    _check_positive("Saturated content (Tsat)", tables.t_sat, problems)
    for label, path in (
        ("Saturated hydraulic conductivity (Kr)", tables.k_sat),
        ("Field capacity (Tcc)", tables.t_fcap),
        ("Wilting point (Tw)", tables.t_wp),
        ("Minimum crop coefficient (kc_min)", tables.kc_min),
        ("Maximum crop coefficient (kc_max)", tables.kc_max),
    ):
        _check_readable(label, path, problems)

    _check_pair(
        "Field capacity (Tcc) and wilting point (Tw)",
        tables.t_fcap,
        tables.t_wp,
        lambda tcc, tw: tcc > tw,
        "Tcc > Tw",
        problems,
    )
    # Reported, not blocking: published datasets carry classes whose kc_max is
    # below kc_min (the regression fixture has one), and the legacy loader
    # must keep running them. The strict v1.0 loader blocks on it.
    _check_pair(
        "Maximum (kc_max) and minimum (kc_min) crop coefficient",
        tables.kc_max,
        tables.kc_min,
        lambda kc_max, kc_min: kc_max >= kc_min,
        "kc_max >= kc_min",
        problems,
        blocking=False,
    )
    _check_fractions(
        (tables.a_i, tables.a_o, tables.a_s, tables.a_v),
        problems,
    )
    return problems


def _check_readable(label: str, path, problems: list[Problem]) -> None:
    try:
        values = _values_by_key(path)
    except (OSError, LookupTableError) as e:
        problems.append(_problem(f"{label} lookup table cannot be read.", str(e), path, True))
        return
    bad = [k for k, v in values.items() if not math.isfinite(v)]
    if bad:
        problems.append(
            _problem(
                f"{label} lookup table has non-finite values.",
                f"Keys: {[' '.join(k) for k in bad]}.",
                path,
                True,
            )
        )


def _check_fractions(paths: Iterable, problems: list[Problem]) -> None:
    paths = list(paths)
    tables = []
    for path in paths:
        try:
            tables.append(_values_by_key(path))
        except (OSError, LookupTableError) as e:
            problems.append(
                _problem("Area fraction lookup table cannot be read.", str(e), path, True)
            )
            return
    keys = set().union(*tables)
    for key in sorted(keys):
        values = [table.get(key) for table in tables]
        if any(value is None for value in values):
            problems.append(
                _problem(
                    "Area fraction lookup tables do not share their keys.",
                    f"Key {' '.join(key)!r} is missing from at least one of a_i, a_o, a_s, a_v.",
                    list(paths)[-1],
                    True,
                )
            )
            continue
        if any(not 0 <= value <= 1 for value in values):
            problems.append(
                _problem(
                    "Area fractions must lie between 0 and 1.",
                    f"Key {' '.join(key)!r}: {values}.",
                    list(paths)[-1],
                    True,
                )
            )
        elif not math.isclose(sum(values), 1.0, abs_tol=1e-6):
            problems.append(
                _problem(
                    "Area fractions of a land use class do not add up to 1.",
                    f"Key {' '.join(key)!r}: a_i + a_o + a_s + a_v = {sum(values):.6f}.",
                    list(paths)[-1],
                    False,
                )
            )


def _class_name(key: tuple[str, ...]) -> str:
    return " ".join(key)


def _readable_soil_classes(path, problems: list[Problem]) -> dict[tuple[str, ...], float]:
    """The soil classes usable in S9, reporting the ones whose wilting point is not below 1."""
    values = _values_by_key(path)
    usable: dict[tuple[str, ...], float] = {}
    for key in sorted(values):
        t_w = values[key]
        if not math.isfinite(t_w):
            continue  # Reported by check_lookup_tables.
        if t_w >= 1:
            problems.append(
                Problem(
                    description="Wilting point (Tw) is not below 1.",
                    reason=(
                        f"Soil class {_class_name(key)} has Tw = {t_w:g}, so the soil term "
                        "Tw / (1 - Tw) of the permeable runoff coefficient C_per (S9) is "
                        "infinite at Tw = 1 and negative above it."
                    ),
                    implication=(
                        "The weighted runoff coefficient C_wp cannot be evaluated for this "
                        "soil class."
                    ),
                    file=str(path),
                    blocking=True,
                )
            )
            continue
        usable[key] = t_w
    return usable


def check_runoff_coefficient_domain(tables, w1, w2, w3) -> list[Problem]:
    """Check that the weighted runoff coefficient stays inside its domain.

    The actual runoff coefficient is ``C_SR = C_wp P_MD / (C_wp P_MD - RCD C_wp + RCD)``
    (S5); its denominator ``C_wp P_MD + RCD (1 - C_wp)`` stays non-negative for every
    ``P_MD >= 0`` and ``RCD >= 1`` only while ``C_wp <= 1``, and vanishes there only in
    the corner ``C_wp = 1`` with ``P_MD = 0``. With ``A = a_i + a_o`` (S8),
    ``C_wp = (1 - A) C_per + A 0.09 exp(2.4 A)`` (S6 and S7) and
    ``C_per = w1 0.02 / n + w2 T_w / (1 - T_w) + w3 S / (10 + S)`` (S9), every term
    but the slope one comes from the lookup tables and the calibration weights. The
    slope-free part is

        ``B = (1 - A) (w1 0.02 / n + w2 T_w / (1 - T_w)) + A 0.09 exp(2.4 A)``

    and the slope term adds a value in ``[0, (1 - A) w3)``.

    Blocking: ``B >= 1`` for a pair of a land use class and a soil class, and a
    wilting point ``T_w >= 1``. Warning: ``B < 1 <= B + (1 - A) w3``, where the
    coefficient reaches 1 above the slope ``S* = 10 r / (1 - r)`` with
    ``r = (1 - B) / ((1 - A) w3)``.

    Land use classes with ``A >= 1`` (fully impervious or open water) carry no
    permeable term and are skipped, as are classes whose roughness or area
    fractions are outside their own domain: those are reported by
    :func:`check_lookup_tables`.

    :param tables: An :class:`~rubem.configuration.input_table_files.InputTableFiles`.
    :param w1: Land use factor weight.
    :param w2: Soil factor weight.
    :param w3: Slope factor weight.
    :return: The problems found, blocking ones flagged.
    """
    problems: list[Problem] = []
    try:
        manning = _values_by_key(tables.manning)
        impervious = _values_by_key(tables.a_i)
        open_water = _values_by_key(tables.a_o)
        soils = _readable_soil_classes(tables.t_wp, problems)
    except (OSError, LookupTableError):
        return problems  # Already reported by check_lookup_tables.

    for land_use in sorted(set(manning) & set(impervious) & set(open_water)):
        roughness = manning[land_use]
        fractions = (impervious[land_use], open_water[land_use])
        if not math.isfinite(roughness) or roughness <= 0:
            continue  # Reported by check_lookup_tables.
        if not all(math.isfinite(value) and 0 <= value <= 1 for value in fractions):
            continue  # Reported by check_lookup_tables.
        area = sum(fractions)
        if area >= 1:
            continue
        impervious_term = area * 0.09 * math.exp(2.4 * area)
        slope_room = (1 - area) * w3
        for soil, t_w in soils.items():
            b = (1 - area) * (w1 * 0.02 / roughness + w2 * t_w / (1 - t_w)) + impervious_term
            if b >= 1:
                problems.append(
                    Problem(
                        description="Weighted runoff coefficient exceeds 1.",
                        reason=(
                            f"Land use class {_class_name(land_use)} and soil class "
                            f"{_class_name(soil)}: C_wp is {b:.4f} without the slope term "
                            "of S9, at or above 1 whatever the slope."
                        ),
                        implication=(
                            "The denominator of the actual runoff coefficient C_SR (S5) "
                            "crosses zero: the coefficient becomes negative or infinite and "
                            "the surface runoff exceeds the precipitation."
                        ),
                        file=str(tables.manning),
                        blocking=True,
                    )
                )
            elif b + slope_room >= 1:
                ratio = (1 - b) / slope_room
                threshold = (
                    "only in the limit of an infinite slope"
                    if ratio >= 1
                    else f"above the slope {10 * ratio / (1 - ratio):.4f}"
                )
                problems.append(
                    Problem(
                        description="Weighted runoff coefficient may exceed 1 on steep cells.",
                        reason=(
                            f"Land use class {_class_name(land_use)} and soil class "
                            f"{_class_name(soil)}: C_wp is {b:.4f} without the slope term of "
                            f"S9 and the slope term adds up to {slope_room:.4f}, so C_wp "
                            f"reaches 1 {threshold}, in the slope units the model computes "
                            "(PCRaster slope of the DEM)."
                        ),
                        implication=(
                            "On those cells the denominator of the actual runoff coefficient "
                            "C_SR (S5) crosses zero and the surface runoff can exceed the "
                            "precipitation."
                        ),
                        file=str(tables.manning),
                        blocking=False,
                    )
                )
    return problems
