"""Checks of the MODFLOW inputs and runtime, run before a coupled simulation.

:func:`check_modflow_inputs` is called by
:class:`~rubem.configuration.model_configuration.ModelConfiguration` when the
MODFLOW section is enabled. The files the run reads must exist and the
MODFLOW runtime must be installed whatever ``validate_input`` says: without
them the coupled run cannot start, and a calibration would only find out in
its workers. The content of the rasters and tables is checked with
``validate_input``, as the other inputs are.

The content checks read every raster the way the run does, through
:func:`~rubem.file._readers.read_field` on the clone of the configuration, so
they make that clone the PCRaster clone of the process (the one the model sets
again when it starts). PCRaster reads a map of another size on the clone
without complaint, so the geometry of every raster is compared with the
clone's first. Layers are named by their configured number, 1 being the top
layer. The cross-field rules of the section (layer numbers, LAYCON of the
wetting layers, storage keys) are checked by
:class:`~rubem.configuration.modflow_configuration.ModflowSettings` itself.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from .._deps import groundwater_deps_message, missing_groundwater_deps, missing_runtime_deps
from ..configuration._problems import Problem
from ..configuration.modflow_configuration import ConductivityLookup, transform_paths
from ..file._readers import FieldScale, is_geotiff, read_field, set_clone
from .lookup_tables import _INTERVAL, _NUMBER, LookupTableError, _in_interval, read_lookup_table

if TYPE_CHECKING:
    from ..configuration.input_raster_files import InputRasterFiles
    from ..configuration.input_table_files import InputTableFiles
    from ..configuration.modflow_configuration import ModflowSettings

_BOUNDARY_VALUES = (-1, 0, 1)
_RASTER_IMPLICATION = "The simulation cannot run with this raster."
_TABLE_IMPLICATION = "The simulation cannot run with this table."
_PACKAGE_STRESS_KEYS = {"river": ("stage", "bottom"), "ghb": ("head",), "drain": ("elevation",)}


def check_modflow_inputs(
    settings: ModflowSettings,
    raster_files: InputRasterFiles,
    validate_input: bool,
    *,
    tables: InputTableFiles | None = None,
) -> list[Problem]:
    """Check the inputs of an enabled MODFLOW section and the MODFLOW runtime.

    Always, blocking: every file the run reads exists and is not empty (the
    files of a disabled package, of disabled wetting and of a disabled
    root-depth coupling are not read); the PCRaster MODFLOW extension and the
    ``mf2005`` executable are available (see
    :func:`~rubem._deps.missing_groundwater_deps`).

    With ``validate_input``, when every file exists and PCRaster is installed:

    - blocking: a raster that cannot be read or does not share the clone
      geometry; boundary values other than -1, 0 and 1; a model top or layer
      bottom missing on a column active in any layer, or a bottom not strictly
      below the top of its layer there; an initial head, conductivity or (in
      a transient run) storage map missing on an active cell of its layer; an
      initial head below the layer bottom in every active cell; a conductivity
      class map that is not nominal, or a class on an active cell without a
      positive value in the table; an enabled package layer without a cell of
      positive conductance inside the boundary of the layer (the PCRaster
      MODFLOW extension aborts the process on it); a package head or
      elevation missing on a cell of the package; with the root-depth
      coupling, a minimum root depth table that does not cover the soil
      classes or whose value is not in ``(0, Zr]``;
    - warning: an initial head below the layer bottom in some active cells;
      river cells whose bed lies outside the elevation interval of their layer.

    :param settings: The MODFLOW section, paths already anchored.
    :type settings: ModflowSettings
    :param raster_files: The input rasters of the configuration (clone, soil).
    :type raster_files: InputRasterFiles
    :param validate_input: Whether to check the content of the inputs.
    :type validate_input: bool
    :param tables: The lookup tables of the configuration; their rootzone
        depth (Zr) bounds the minimum root depth. Defaults to ``None``, which
        skips that comparison.
    :type tables: InputTableFiles | None
    :returns: The problems found, blocking ones flagged.
    :rtype: list[Problem]
    """
    problems = _check_files(settings)
    files_unusable = bool(problems)
    missing = missing_groundwater_deps()
    if missing:
        problems.append(
            Problem(
                description="MODFLOW runtime is not available.",
                reason=groundwater_deps_message(missing),
                implication="The coupled simulation cannot start.",
                blocking=True,
            )
        )
    if not validate_input or files_unusable or "pcraster" in missing_runtime_deps():
        return problems
    return problems + _ContentChecks(settings, raster_files, tables).run()


def _read_files(settings: ModflowSettings) -> list[str]:
    """The files the coupled run reads, in the order of the section, without repeats."""
    document = settings.model_dump(mode="json")
    if not settings.wetting.enabled:
        document.pop("wetting")
    for package in ("river", "ghb", "drain"):
        if not getattr(settings, package).enabled:
            document.pop(package)
    if not settings.coupling.dynamic_root_depth.enabled:
        document.pop("coupling")
    files: list[str] = []

    def collect(path: str) -> str:
        if path not in files:
            files.append(path)
        return path

    transform_paths(document, collect)
    return files


def _check_files(settings: ModflowSettings) -> list[Problem]:
    problems = []
    for path in _read_files(settings):
        file = Path(path)
        if not file.is_file():
            problems.append(
                Problem(
                    description="MODFLOW input file does not exist.",
                    reason="The MODFLOW section names this file and the coupled run reads it.",
                    implication="The simulation cannot run without it.",
                    file=path,
                    blocking=True,
                )
            )
        elif file.stat().st_size <= 0:
            problems.append(
                Problem(
                    description="MODFLOW input file is empty.",
                    reason="The MODFLOW section names this file and the coupled run reads it.",
                    implication="The simulation cannot run with it.",
                    file=path,
                    blocking=True,
                )
            )
    return problems


def _first_cell(cells: np.ndarray) -> str:
    row, column = (int(index) + 1 for index in np.argwhere(cells)[0])
    return f"row {row}, column {column}"


def _numbers(values) -> list:
    """Values for a message: integers without a decimal part, the rest as floats."""
    return [int(value) if float(value).is_integer() else float(value) for value in values]


def _table_value(rows, value: float) -> float | None:
    """The value of the first row of a lookup table whose key matches ``value``."""
    for (key,), result in rows:
        if _NUMBER.match(key) and float(key) == value:
            return result
        if _INTERVAL.match(key) and _in_interval(value, key):
            return result
    return None


def _blocking(description: str, reason: str, file, implication=_RASTER_IMPLICATION) -> Problem:
    return Problem(
        description=description,
        reason=reason,
        implication=implication,
        file=str(file) if file is not None else None,
        blocking=True,
    )


class _ContentChecks:
    """The content rules of :func:`check_modflow_inputs`; rasters are read once."""

    def __init__(self, settings, raster_files, tables) -> None:
        self.settings = settings
        self.raster_files = raster_files
        self.tables = tables
        self.problems: list[Problem] = []
        self.fields: dict = {}
        self.arrays: dict = {}
        self.clone_geometry = None
        self.active: dict[int, np.ndarray] = {}
        self.bottoms: dict[int, np.ndarray | None] = {}
        self.tops: dict[int, np.ndarray | None] = {}

    def run(self) -> list[Problem]:
        from ..configuration.output_raster_base import read_raster_geometry, reference_crs

        clone = self.raster_files.clone
        set_clone(
            clone,
            projection=reference_crs(clone, self.raster_files.georeference, self.raster_files.dem),
        )
        cols, rows, transform, _ = read_raster_geometry(clone)
        self.clone_geometry = (cols, rows, transform)
        self.shape = (rows, cols)
        if not self._check_boundaries():
            return self.problems
        self._check_geometry()
        for number in range(1, len(self.settings.layers) + 1):
            self._check_layer(number)
        for package in ("river", "ghb", "drain"):
            if getattr(self.settings, package).enabled:
                self._check_package(package)
        if self.settings.coupling.dynamic_root_depth.enabled:
            self._check_minimum_root_depth()
        return self.problems

    # ----- reading ------------------------------------------------------------

    def _label(self, number: int) -> str:
        return f"layer {number} ({self.settings.layers[number - 1].name})"

    def _field(self, path: str, scale: FieldScale = FieldScale.SCALAR):
        """The raster as a field on the clone, or ``None`` once its problem is reported."""
        key = (path, scale)
        if key in self.fields:
            return self.fields[key]
        from ..configuration.output_raster_base import read_raster_geometry

        field = None
        try:
            cols, rows, transform, _ = read_raster_geometry(path)
            clone_cols, clone_rows, clone_transform = self.clone_geometry
            if (cols, rows) != (clone_cols, clone_rows) or not all(
                abs(a - b) <= 1e-9 * max(1.0, abs(a))
                for a, b in zip(transform, clone_transform, strict=True)
            ):
                self.problems.append(
                    _blocking(
                        "MODFLOW raster does not share the clone geometry.",
                        f"{cols}x{rows} cells with transform {transform}; the clone has "
                        f"{clone_cols}x{clone_rows} with {clone_transform}.",
                        path,
                    )
                )
            else:
                field = read_field(path, scale)
        except (OSError, RuntimeError, ValueError) as error:
            self.problems.append(_blocking("MODFLOW raster cannot be read.", str(error), path))
        self.fields[key] = field
        return field

    def _values(self, source) -> np.ndarray | None:
        """A scalar raster (missing cells as NaN), or a number spread over the clone."""
        if source is None:
            return None
        if not isinstance(source, str):
            return np.full(self.shape, float(source))
        if source not in self.arrays:
            import pcraster as pcr

            field = self._field(source)
            self.arrays[source] = (
                None if field is None else pcr.pcr2numpy(pcr.scalar(field), np.nan)
            )
        return self.arrays[source]

    def _require_finite(self, values, cells, description: str, where: str, file) -> bool:
        """Report ``values`` missing on ``cells``; ``where`` names the cells."""
        invalid = cells & ~np.isfinite(values)
        if not invalid.any():
            return True
        self.problems.append(
            _blocking(
                description,
                f"{int(invalid.sum())} of {int(cells.sum())} {where}, the first at "
                f"{_first_cell(invalid)}.",
                file,
            )
        )
        return False

    # ----- layers -------------------------------------------------------------

    def _check_boundaries(self) -> bool:
        readable = True
        for number, item in enumerate(self.settings.layers, start=1):
            values = self._values(item.boundary)
            if values is None:
                readable = False
                continue
            finite = np.isfinite(values)
            invalid = sorted(set(values[finite].tolist()) - set(_BOUNDARY_VALUES))
            if invalid:
                self.problems.append(
                    _blocking(
                        f"MODFLOW boundary of {self._label(number)} has invalid values.",
                        "Values other than -1 (constant head), 0 (inactive) and 1 (active): "
                        f"{_numbers(invalid[:10])}.",
                        item.boundary,
                    )
                )
            self.active[number] = finite & (values != 0)
        return readable

    def _check_geometry(self) -> None:
        domain = np.logical_or.reduce(list(self.active.values()))
        layers = self.settings.layers
        surfaces = [("MODFLOW model top", self.settings.top)] + [
            (f"MODFLOW bottom of {self._label(number)}", item.bottom)
            for number, item in enumerate(layers, start=1)
        ]
        values = []
        for label, path in surfaces:
            surface = self._values(path)
            if surface is not None and not self._require_finite(
                surface,
                domain,
                f"{label} has missing values on active columns.",
                "columns active in a layer",
                path,
            ):
                surface = None
            values.append(surface)
        for number in range(1, len(layers) + 1):
            self.tops[number], self.bottoms[number] = values[number - 1], values[number]
            upper, lower = values[number - 1], values[number]
            if upper is None or lower is None:
                continue
            invalid = domain & ~(lower < upper)
            if invalid.any():
                above = "the model top" if number == 1 else f"the bottom of layer {number - 1}"
                self.problems.append(
                    _blocking(
                        f"MODFLOW bottom of {self._label(number)} is not below the top of "
                        "the layer.",
                        f"The top of the layer is {above}; {int(invalid.sum())} cell(s) of the "
                        f"columns active in a layer are not strictly below it, the first at "
                        f"{_first_cell(invalid)}.",
                        layers[number - 1].bottom,
                    )
                )

    def _check_layer(self, number: int) -> None:
        item = self.settings.layers[number - 1]
        active = self.active[number]
        label = self._label(number)
        where = "active cells of the layer"
        head = self._values(item.initial_head)
        if head is not None and self._require_finite(
            head,
            active,
            f"MODFLOW initial head of {label} has missing values on active cells.",
            where,
            item.initial_head,
        ):
            self._check_head_above_bottom(number, head)
        properties = [
            ("vertical conductivity", item.vertical_conductivity),
            ("horizontal conductivity", item.horizontal_conductivity),
        ]
        if not self.settings.dis.steady_state:
            properties += [
                ("specific storage", item.specific_storage),
                ("specific yield", item.specific_yield),
            ]
        for name, source in properties:
            if isinstance(source, ConductivityLookup):
                self._check_conductivity_classes(number, source)
            elif isinstance(source, str):
                values = self._values(source)
                if values is not None:
                    self._require_finite(
                        values,
                        active,
                        f"MODFLOW {name} of {label} has missing values on active cells.",
                        where,
                        source,
                    )

    def _check_head_above_bottom(self, number: int, head: np.ndarray) -> None:
        bottom = self.bottoms.get(number)
        if bottom is None:
            return
        cells = self.active[number] & np.isfinite(bottom)
        below = cells & (head < bottom)
        count, total = int(below.sum()), int(cells.sum())
        if not count:
            return
        item = self.settings.layers[number - 1]
        reason = (
            f"{count} of {total} active cells have an initial head below the bottom of the "
            f"layer, the first at {_first_cell(below)}."
        )
        if count == total:
            self.problems.append(
                _blocking(
                    f"MODFLOW initial head of {self._label(number)} is below the layer bottom "
                    "in every active cell.",
                    reason,
                    item.initial_head,
                    implication="MODFLOW would start with the whole layer dry.",
                )
            )
            return
        self.problems.append(
            Problem(
                description=f"MODFLOW initial head of {self._label(number)} is below the layer "
                "bottom in some active cells.",
                reason=reason,
                implication="MODFLOW starts with those cells dry.",
                file=item.initial_head,
            )
        )

    def _check_conductivity_classes(self, number: int, lookup: ConductivityLookup) -> None:
        import pcraster as pcr

        label = self._label(number)
        field = self._field(lookup.map, FieldScale.NOMINAL)
        if field is None:
            return
        if not is_geotiff(lookup.map) and field.dataType() != pcr.Nominal:
            self.problems.append(
                _blocking(
                    f"MODFLOW horizontal conductivity classes of {label} must be a nominal map.",
                    f"The map has the {field.dataType()} value scale; its classes are looked "
                    "up in the table.",
                    lookup.map,
                )
            )
            return
        classes = pcr.pcr2numpy(pcr.scalar(field), np.nan)
        active = self.active[number]
        if not self._require_finite(
            classes,
            active,
            f"MODFLOW horizontal conductivity classes of {label} have missing values on "
            "active cells.",
            "active cells of the layer",
            lookup.map,
        ):
            return
        try:
            rows = read_lookup_table(lookup.table)
        except (OSError, LookupTableError) as error:
            self.problems.append(
                _blocking(
                    f"MODFLOW horizontal conductivity table of {label} cannot be read.",
                    str(error),
                    lookup.table,
                    implication=_TABLE_IMPLICATION,
                )
            )
            return
        uncovered, invalid = [], []
        for value in sorted(set(classes[active].tolist())):
            conductivity = _table_value(rows, value)
            if conductivity is None:
                uncovered.append(value)
            elif not (math.isfinite(conductivity) and conductivity > 0):
                invalid.append(value)
        if uncovered:
            self.problems.append(
                _blocking(
                    f"MODFLOW horizontal conductivity table of {label} does not cover the "
                    "classes of its map.",
                    f"Classes on active cells without a row: {_numbers(uncovered)}.",
                    lookup.table,
                    implication=_TABLE_IMPLICATION,
                )
            )
        if invalid:
            self.problems.append(
                _blocking(
                    f"MODFLOW horizontal conductivity table of {label} has non-positive values.",
                    f"Classes on active cells whose conductivity is not positive: "
                    f"{_numbers(invalid)}.",
                    lookup.table,
                    implication=_TABLE_IMPLICATION,
                )
            )

    # ----- packages -----------------------------------------------------------

    def _package_cells(self, entry) -> np.ndarray | None:
        """The cells of positive conductance (inside the mask, for a river), any layer."""
        conductance = self._values(entry.conductance)
        mask = self._values(getattr(entry, "mask", None))
        if conductance is None or (getattr(entry, "mask", None) and mask is None):
            return None
        cells = np.isfinite(conductance) & (conductance > 0)
        if mask is not None:
            cells &= np.isfinite(mask) & (mask > 0)
        return cells

    def _check_package(self, package: str) -> None:
        for entry in getattr(self.settings, package).entries:
            cells = self._package_cells(entry)
            if cells is None:
                continue
            used = np.zeros(self.shape, dtype=bool)
            for number in entry.layers:
                layer_cells = cells & self.active[number]
                if not layer_cells.any():
                    self.problems.append(
                        _blocking(
                            f"MODFLOW {package} package has no cell in {self._label(number)}.",
                            "No active cell of the layer has a positive conductance"
                            + (" inside the mask" if getattr(entry, "mask", None) else "")
                            + "; cells outside the boundary of the layer do not count.",
                            entry.conductance if isinstance(entry.conductance, str) else entry.mask,
                            implication="The PCRaster MODFLOW extension aborts the process "
                            "when it reads a package layer without cells.",
                        )
                    )
                used |= layer_cells
            complete = True
            for key in _PACKAGE_STRESS_KEYS[package]:
                path = getattr(entry, key)
                values = self._values(path)
                complete &= values is not None and self._require_finite(
                    values,
                    used,
                    f"MODFLOW {package} {key} has missing values on the cells of the package.",
                    "cells of the package",
                    path,
                )
            if package == "river" and complete:
                self._check_riverbed(entry, cells)

    def _check_riverbed(self, entry, cells: np.ndarray) -> None:
        bed = self._values(entry.bottom)
        for number in entry.layers:
            bottom, top = self.bottoms.get(number), self.tops.get(number)
            if bottom is None or top is None:
                continue
            river = cells & self.active[number]
            below = river & (bed < bottom)
            above = river & (bed > top)
            outside = int(below.sum() + above.sum())
            if not outside:
                continue
            self.problems.append(
                Problem(
                    description="MODFLOW river bed lies outside the elevation interval of its "
                    "layer.",
                    reason=f"{outside} of {int(river.sum())} river cells of layer {number} have "
                    "their bed outside the layer's elevation interval: "
                    f"{int(below.sum())} below the layer bottom, {int(above.sum())} above the "
                    "layer top.",
                    implication="The river exchange of those cells is computed in a layer "
                    "that does not hold the riverbed; moving them to another layer (a second "
                    "river entry with its own mask) is a modelling decision.",
                    file=entry.bottom,
                )
            )

    # ----- coupling -----------------------------------------------------------

    def _check_minimum_root_depth(self) -> None:
        import pcraster as pcr

        label = "Minimum root depth (Dpz_min)"
        path = self.settings.coupling.dynamic_root_depth.minimum_depth_table
        try:
            rows = read_lookup_table(path)
        except (OSError, LookupTableError) as error:
            self.problems.append(
                _blocking(
                    f"{label} lookup table cannot be read.",
                    str(error),
                    path,
                    implication=_TABLE_IMPLICATION,
                )
            )
            return
        soil = self._field(self.raster_files.soil, FieldScale.NOMINAL)
        if soil is None:
            return
        values = pcr.pcr2numpy(pcr.scalar(soil), np.nan)
        classes = sorted(set(values[np.isfinite(values)].tolist()))
        depths = {value: _table_value(rows, value) for value in classes}
        uncovered = [value for value, depth in depths.items() if depth is None]
        if uncovered:
            self.problems.append(
                _blocking(
                    f"{label} lookup table does not cover the soil classes.",
                    f"Soil classes without a row: {_numbers(uncovered)}.",
                    path,
                    implication=_TABLE_IMPLICATION,
                )
            )
        non_positive = [
            (value, depth)
            for value, depth in depths.items()
            if depth is not None and not (math.isfinite(depth) and depth > 0)
        ]
        if non_positive:
            self.problems.append(
                _blocking(
                    f"{label} lookup table has non-positive values.",
                    "Values <= 0: "
                    + "; ".join(
                        f"soil class {_numbers([value])[0]}: {depth:g}"
                        for value, depth in non_positive
                    )
                    + ".",
                    path,
                    implication=_TABLE_IMPLICATION,
                )
            )
        exceeding = self._above_rootzone_depth(depths)
        if exceeding:
            self.problems.append(
                _blocking(
                    f"{label} exceeds the rootzone depth (Zr).",
                    "; ".join(
                        f"soil class {_numbers([value])[0]}: Dpz_min {depth:g} > Zr {zr:g}"
                        for value, depth, zr in exceeding
                    )
                    + ".",
                    path,
                    implication=_TABLE_IMPLICATION,
                )
            )

    def _above_rootzone_depth(self, depths: dict) -> list[tuple[float, float, float]]:
        """The soil classes whose minimum root depth exceeds Zr (unreadable Zr: none)."""
        if self.tables is None:
            return []
        try:
            rows = read_lookup_table(self.tables.rootzone_depth)
        except (OSError, LookupTableError):
            return []  # Reported by check_lookup_tables.
        exceeding = []
        for value, depth in depths.items():
            zr = _table_value(rows, value)
            if depth is not None and zr is not None and depth > zr:
                exceeding.append((value, depth, zr))
        return exceeding
