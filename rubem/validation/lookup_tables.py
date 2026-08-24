"""Content checks of the lookup tables the model reads with PCRaster.

A PCRaster lookup table is a whitespace-separated text file whose last column
is the value and whose preceding columns are keys; a key is a single number or
an interval such as ``[1,3]``, ``<1,3]`` or ``[1,>``. The model's tables use
one key column (a land use or soil class, or a month).
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


def read_lookup_table(path) -> list[tuple[tuple[str, ...], float]]:
    """Return the ``(keys, value)`` rows of a PCRaster lookup table.

    :param path: The table file.
    :raises LookupTableError: On an empty table, a row without a value, or a
        value or key that is neither a number nor an interval.
    """
    rows = []
    text = Path(path).read_text(encoding="utf8")
    for number, line in enumerate(text.splitlines(), start=1):
        columns = line.split()
        if not columns:
            continue
        if len(columns) < 2:
            raise LookupTableError(f"{path}: line {number} has no value column: {line!r}")
        *keys, value = columns
        if not _NUMBER.match(value):
            raise LookupTableError(f"{path}: line {number} has a non-numeric value {value!r}")
        for key in keys:
            if not (_NUMBER.match(key) or _INTERVAL.match(key)):
                raise LookupTableError(f"{path}: line {number} has an invalid key {key!r}")
        rows.append((tuple(keys), float(value)))
    if not rows:
        raise LookupTableError(f"{path}: the lookup table is empty")
    return rows


def _values_by_key(path) -> dict[tuple[str, ...], float]:
    return dict(read_lookup_table(path))


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
        months = {str(month) for month in range(1, 13)}
        keys = {" ".join(k) for k in rainy_days}
        missing = sorted(months - keys, key=int)
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
    try:
        tables = [_values_by_key(path) for path in paths]
    except (OSError, LookupTableError) as e:
        problems.append(
            _problem(
                "Area fraction lookup table cannot be read.", str(e), str(e).split(":")[0], True
            )
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
