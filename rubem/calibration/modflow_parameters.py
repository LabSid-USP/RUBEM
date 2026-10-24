"""The MODFLOW parameters a calibration may search, and how a candidate reaches the run.

A configuration that enables MODFLOW offers a few more numbers to calibrate than
the nine of the model. They are named after where they live in the ``modflow``
section, with the layers numbered from the top down as in the configuration:

``modflow.layers.<n>.specific_yield``, ``modflow.layers.<n>.specific_storage``
    The storage of layer ``n`` [-], when the section gives it as a number, the
    run is transient and the LAYCON of the layer reads it (LAYCON 0 reads the
    specific storage, LAYCON 1 the specific yield, LAYCON 2 and 3 both).
``modflow.layers.<n>.kh.<class>``
    The horizontal conductivity of one class of the lookup table of layer
    ``n`` [m/day]; a numeric class key is spelt canonically (``01`` and
    ``1.0`` are class ``1``). Only the row PCRaster reads for a class is named:
    an interval row is not, nor a row whose class an earlier row, numeric or
    interval, already matches.
``modflow.river.<i>.conductance``
    The numeric conductance of river entry ``i`` [m2/day], counted from 1.

A map path is not a number to search, so it has no name. The parameters enter a
search only when ``--bound`` or ``--fix`` names them; see
:func:`rubem.calibration.parameters.decision_space`.

:class:`ModflowCatalog` is plain data, since it travels to the spawned worker
processes, and this module imports no native library.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .._paths import PathInput, as_path
from ..configuration.modflow_configuration import ConductivityLookup, ModflowSettings
from ..validation.lookup_tables import (
    _NUMBER,
    _canonical,
    _first_matching_row,
    read_lookup_table,
)

MODFLOW_PREFIX = "modflow."
"""The prefix of every MODFLOW parameter name."""

_STORAGE_READ = {
    0: ("specific_storage",),
    1: ("specific_yield",),
    2: ("specific_yield", "specific_storage"),
    3: ("specific_yield", "specific_storage"),
}
"""The storage keys the run reads for each LAYCON of a transient run."""


@dataclass(frozen=True)
class ModflowCatalog:
    """The MODFLOW parameters of one configuration and their current values.

    :param values: The current value of every calibratable parameter, by name,
        in the order of the section: layer by layer from the top, then the
        river entries.
    :type values: dict[str, float]

    :param tables: The rows of the conductivity lookup table of each layer that
        has one, by layer number, as ``(key, value)`` pairs with the keys kept
        as they are written.
    :type tables: dict[int, list[tuple[str, float]]]
    """

    values: dict[str, float]
    tables: dict[int, list[tuple[str, float]]]

    @property
    def names(self) -> tuple[str, ...]:
        """The calibratable names, in the order of :attr:`values`.

        :return: The names.
        :rtype: tuple[str, ...]
        """
        return tuple(self.values)

    def domain(self, name: str) -> str:
        """Describe the values a parameter may take, for the messages.

        :param name: A name of the catalog.
        :type name: str

        :return: ``(0, 1]`` for a specific yield, ``(0, inf)`` otherwise.
        :rtype: str
        """
        return "(0, 1]" if name.endswith(".specific_yield") else "(0, inf)"

    def admits(self, name: str, value: float) -> bool:
        """Whether a parameter may take a value.

        Every MODFLOW parameter is strictly positive and finite: a zero
        conductivity or storage would only surface as a run that does not
        converge. A specific yield is a fraction, at most 1.

        :param name: A name of the catalog.
        :type name: str

        :param value: The candidate value.
        :type value: float

        :return: ``True`` when the value lies in the domain of the parameter.
        :rtype: bool
        """
        value = float(value)
        if not math.isfinite(value) or value <= 0.0:
            return False
        return value <= 1.0 or not name.endswith(".specific_yield")

    def apply(
        self,
        document: dict,
        parameters: Mapping[str, float],
        table_dir: PathInput,
        *,
        table_prefix: str = "kh_layer",
    ) -> None:
        """Write the MODFLOW values of a candidate into a format 1.0 document.

        The numbers replace the ones of the ``modflow`` section in place. The
        classes named for a layer are written, with the other rows of its
        table unchanged, into ``<table_dir>/<table_prefix><n>.tbl``, and the
        lookup of the layer is pointed at that file; the configured table is
        never modified. Names outside the ``modflow.`` prefix are ignored, so
        the whole parameter set of a candidate can be given.

        :param document: The configuration document, patched in place.
        :type document: dict

        :param parameters: The parameters of the candidate, by name.
        :type parameters: collections.abc.Mapping[str, float]

        :param table_dir: Directory the rewritten tables are written to; it
            must exist when a class is named.
        :type table_dir: str | os.PathLike[str]

        :param table_prefix: File name of a rewritten table, before the layer
            number. Defaults to ``kh_layer``.
        :type table_prefix: str, optional

        :raises ValueError: If a ``modflow.`` name is not in the catalog.
        """
        named = {
            name: float(value)
            for name, value in parameters.items()
            if name.startswith(MODFLOW_PREFIX)
        }
        unknown = [name for name in named if name not in self.values]
        if unknown:
            raise ValueError(
                f"{', '.join(unknown)} is not a MODFLOW parameter of this configuration; "
                f"the calibratable ones are {', '.join(self.names) or 'none'}."
            )
        if not named:
            return

        section = document["modflow"]
        classes: dict[int, dict[str, float]] = {}
        for name, value in named.items():
            parts = name.split(".")
            if parts[1] == "river":
                section["river"]["entries"][int(parts[2]) - 1]["conductance"] = value
            elif parts[3] == "kh":
                classes.setdefault(int(parts[2]), {})[".".join(parts[4:])] = value
            else:
                section["layers"][int(parts[2]) - 1][parts[3]] = value

        for number, replaced in classes.items():
            path = as_path(table_dir) / f"{table_prefix}{number}.tbl"
            _write_table(path, self.tables[number], replaced)
            section["layers"][number - 1]["horizontal_conductivity"]["table"] = str(path)


def catalog(settings: ModflowSettings) -> ModflowCatalog:
    """Return the MODFLOW parameters a configuration offers to a calibration.

    :param settings: The MODFLOW section, with its paths anchored.
    :type settings: rubem.configuration.modflow_configuration.ModflowSettings

    :return: The calibratable names with their current values, and the rows of
        every conductivity lookup table.
    :rtype: ModflowCatalog

    :raises rubem.validation.lookup_tables.LookupTableError: If a conductivity
        lookup table cannot be parsed.
    :raises OSError: If a conductivity lookup table cannot be read.
    """
    values: dict[str, float] = {}
    tables: dict[int, list[tuple[str, float]]] = {}
    transient = not settings.dis.steady_state
    for number, layer in enumerate(settings.layers, start=1):
        prefix = f"{MODFLOW_PREFIX}layers.{number}"
        for key in _STORAGE_READ[layer.laycon] if transient else ():
            value = getattr(layer, key)
            if isinstance(value, float | int):
                values[f"{prefix}.{key}"] = float(value)
        if isinstance(layer.horizontal_conductivity, ConductivityLookup):
            keyed = read_lookup_table(layer.horizontal_conductivity.table)
            rows = [(keys[0], value) for keys, value in keyed]
            tables[number] = rows
            for index, (key, value) in enumerate(rows):
                # PCRaster reads the first row that matches a class, numeric or
                # interval: a later row of the class never reaches the run.
                if _NUMBER.match(key) and _first_matching_row(keyed, float(key)) == index:
                    values[f"{prefix}.kh.{_canonical(key)}"] = value
    for index, entry in enumerate(settings.river.entries, start=1):
        if isinstance(entry.conductance, float | int):
            values[f"{MODFLOW_PREFIX}river.{index}.conductance"] = float(entry.conductance)
    return ModflowCatalog(values=values, tables=tables)


def _write_table(path: Path, rows: list[tuple[str, float]], replaced: Mapping[str, float]) -> None:
    """Write a lookup table, the first row of each named class carrying its new value."""
    lines = []
    pending = dict(replaced)
    for key, value in rows:
        canonical = _canonical(key) if _NUMBER.match(key) else None
        if canonical in pending:
            value = pending.pop(canonical)
        lines.append(f"{key} {_number(value)}\n")
    path.write_text("".join(lines), encoding="utf8")


def _number(value: float) -> str:
    """Spell a value in positional notation, the shortest that reads back exactly."""
    return np.format_float_positional(float(value), trim="-")
