"""Groundwater flow of the coupled run, through the PCRaster MODFLOW extension.

RUBEM recharge feeds the MODFLOW RCH package every step (one RUBEM step is one
stress period) and the aquifer-to-river RIV leakage comes back as the baseflow
of the step. General head boundaries (GHB), drains (DRN) and BCF rewetting
shape the heads only.

The configuration numbers the layers from the top down, like MODFLOW; the
extension numbers them from the bottom up, and
:meth:`~rubem.configuration.modflow_configuration.ModflowSettings.pcraster_layer`
converts. The layers are also given to the extension in its own order, bottom
layer first: it writes the LAYCON of each ``setConductivity`` call to the BCF
file in call order, whatever layer number the call names. Every result is
keyed by the configured (top-down) number.

The inputs are read once, in :meth:`ModflowGroundwater.initialize`, and the
stress packages are set once: the extension keeps them for every later run.
The value rules live in :mod:`rubem.validation.modflow_inputs`; the module
only refuses what the extension cannot be given at all (missing values on the
cells it uses, a geometry that is not stacked), because the extension ends the
whole process instead of raising on those.
"""

from __future__ import annotations

import logging
import math
import shutil
from dataclasses import dataclass, field
from tempfile import TemporaryDirectory

import numpy as np
import pcraster as pcr
from pcraster._pcraster import Field

from .._deps import ensure_mf2005_on_path, groundwater_deps_message, missing_groundwater_deps
from .._paths import PathInput, as_path
from ..configuration.modflow_configuration import ConductivityLookup, ModflowLayer, ModflowSettings
from ..file._readers import FieldScale, read_field

DRY_HEAD = -999.9
"""Head MODFLOW gives a dry cell (BCF HDRY) [m]."""

_TIME_UNIT_DAYS = 4
_LENGTH_UNIT_METRES = 2
_RECHARGE_TO_HIGHEST_ACTIVE_CELL = 3

_STRESS_PACKAGES = (
    ("river", "setRiver", ("stage", "bottom")),
    ("ghb", "setGeneralHead", ("head",)),
    ("drain", "setDrain", ("elevation",)),
)
"""Package, extension setter and the maps it takes before the conductance."""


def _initialise(clone):
    """Start the PCRaster MODFLOW extension on ``clone``.

    :raises RuntimeError: If the extension is not part of the installed pcraster.
    """
    try:
        from pcraster import initialise
    except ImportError as error:
        raise RuntimeError(groundwater_deps_message(missing_groundwater_deps() or None)) from error
    return initialise(clone)


@dataclass(frozen=True)
class ModflowStepResult:
    """What one stress period gives back to RUBEM; layers are configured numbers.

    :param baseflow_mm: Aquifer-to-river leakage as a depth over the cell [mm/step].
    :param aquifer_to_river_m3_per_day: RIV leakage from the aquifer [m3/day].
    :param river_to_aquifer_m3_per_day: RIV leakage into the aquifer [m3/day].
    :param net_river_leakage_m3_per_day: Signed RIV leakage, positive into the aquifer [m3/day].
    :param water_table_head: Head of the root-depth coupling [m], ``None`` when it is off.
    :param heads: Head per layer [m], when ``output.heads``.
    :param storage: Storage flow per layer [m3/day], when ``output.storage``.
    :param drain_flow: Signed DRN flow per drain layer, negative out of the aquifer
        [m3/day], when ``output.drain_flow``.
    """

    baseflow_mm: Field
    aquifer_to_river_m3_per_day: Field
    river_to_aquifer_m3_per_day: Field
    net_river_leakage_m3_per_day: Field
    water_table_head: Field | None = None
    heads: dict[int, Field] = field(default_factory=dict)
    storage: dict[int, Field] = field(default_factory=dict)
    drain_flow: dict[int, Field] = field(default_factory=dict)


def _period_days(days: float) -> float:
    days = float(days)
    if not math.isfinite(days) or days <= 0:
        raise ValueError(f"A stress period must last a positive number of days, got {days}.")
    return days


def _first_cell(cells: np.ndarray) -> str:
    row, column = np.argwhere(cells)[0] + 1
    return f"row {row}, column {column}"


def _field(values: np.ndarray) -> Field:
    return pcr.numpy2pcr(pcr.Scalar, values, np.nan)


def _storage_sources(layer: ModflowLayer) -> tuple:
    """The BCF ``Sf1`` and ``Sf2`` sources of a layer, by its LAYCON."""
    if layer.laycon == 0:
        return layer.specific_storage, layer.specific_storage
    if layer.laycon == 1:
        return layer.specific_yield, layer.specific_yield
    return layer.specific_storage, layer.specific_yield


class ModflowGroundwater:
    """One MODFLOW model kept for the whole run.

    :param settings: The enabled MODFLOW section, paths resolved.
    :type settings: ModflowSettings
    :param cell_area_m2: Area of a RUBEM cell [m2]. Its square root gives the
        MODFLOW row and column widths whatever the units of the clone, and it
        converts the leakage [m3/day] into a depth [mm/step].
    :type cell_area_m2: float
    :param run_directory: Directory MODFLOW runs in; its files (``pcrmf.*``)
        land there. Created by :meth:`initialize` when absent.
    :type run_directory: str | os.PathLike
    :param logger: Logger of the run; the module logger by default.
    :type logger: logging.Logger | None
    :raises ValueError: If the section is not enabled or the area is not a
        positive number.
    """

    def __init__(
        self,
        settings: ModflowSettings,
        cell_area_m2: float,
        run_directory: PathInput,
        logger: logging.Logger | None = None,
    ) -> None:
        if not settings.enabled:
            raise ValueError("The MODFLOW section is not enabled.")
        area = float(cell_area_m2)
        if not math.isfinite(area) or area <= 0:
            raise ValueError(f"The cell area must be finite and positive, got {cell_area_m2} m2.")
        self.settings = settings
        self.cell_area_m2 = area
        self.run_directory = as_path(run_directory)
        self.logger = logger or logging.getLogger(__name__)
        self.mf = None
        self._period = 0
        self._shape: tuple[int, int] = (0, 0)
        self._boundaries: dict[int, Field] = {}
        self._active: dict[int, np.ndarray] = {}
        self._surfaces: list[Field] = []
        self._cells: dict[tuple[str, int], int] = {}

    # ----- initialization -----------------------------------------------------

    def initialize(self, first_period_days: float) -> None:
        """Start the extension and give it every package, once.

        The clone must be set. The packages go in the order the extension
        expects: DIS, BAS, BCF, wetting, solver, then RIV, GHB and DRN.

        :param first_period_days: Length of the first stress period [days].
        :type first_period_days: float
        :raises RuntimeError: If the model is already initialized, or the
            extension or ``mf2005`` is not available.
        :raises ValueError: If an input misses values on cells the extension
            uses, or the layers are not stacked.
        """
        if self.mf is not None:
            raise RuntimeError("The MODFLOW model is already initialized.")
        days = _period_days(first_period_days)
        if ensure_mf2005_on_path() is None:
            raise RuntimeError(groundwater_deps_message(missing_groundwater_deps() or None))
        self.run_directory.mkdir(parents=True, exist_ok=True)
        clone = pcr.clone()
        self._shape = (clone.nrRows(), clone.nrCols())
        self._read_boundaries()
        surfaces = self._read_surfaces()

        self.mf = _initialise(clone)
        self.logger.info(
            "Starting MODFLOW with %d layer(s) in %s.",
            len(self.settings.layers),
            self.run_directory,
        )
        self._set_dis(surfaces, days)
        self._set_bas()
        self._set_bcf()
        self._set_wetting()
        self._set_solver()
        self._set_stress_packages()

    def _label(self, number: int) -> str:
        return f"layer {number} ({self.settings.layers[number - 1].name})"

    def _bottom_up(self):
        """``(extension number, configured number, layer)``, bottom layer first.

        The extension takes the per-layer calls in this order: it appends the
        LAYCON of each ``setConductivity`` call to the BCF file in call order,
        so a top-down loop gives the top layer the LAYCON of the base.
        """
        for target in range(1, len(self.settings.layers) + 1):
            number = self.settings.user_layer(target)
            yield target, number, self.settings.layers[number - 1]

    def _read_boundaries(self) -> None:
        for number, layer in enumerate(self.settings.layers, start=1):
            boundary = pcr.cover(
                pcr.nominal(read_field(layer.boundary, FieldScale.NOMINAL)), pcr.nominal(0)
            )
            self._boundaries[number] = boundary
            self._active[number] = pcr.pcr2numpy(boundary, 0) != 0

    def _read_surfaces(self) -> list[Field]:
        """The layer surfaces from the bottom up: each bottom from the base, then the top.

        DIS needs elevations over the whole clone. A column inactive in every
        layer takes synthetic 1 m layers (elevations 0, 1, 2, ...); the
        elevations of the groundwater domain are never filled.
        """
        layers = self.settings.layers
        domain = np.logical_or.reduce(list(self._active.values()))
        sources = [
            (f"The bottom of {self._label(number)}", layers[number - 1].bottom)
            for number in range(len(layers), 0, -1)
        ]
        sources.append(("The model top", self.settings.top))
        surfaces = []
        below = None
        for index, (what, path) in enumerate(sources):
            values = self._values(path)
            self._require(values, domain, what, path, "active columns")
            values = np.where(domain, values, float(index))
            if below is not None and (stacked := domain & (values <= below)).any():
                raise ValueError(
                    f"{what} ({path}) is not above the surface under it in "
                    f"{int(stacked.sum())} active columns, the first at {_first_cell(stacked)}."
                )
            surfaces.append(_field(values))
            below = values
        self._surfaces = surfaces
        return surfaces

    def _set_dis(self, surfaces: list[Field], days: float) -> None:
        self.mf.createBottomLayer(surfaces[0], surfaces[1])
        for surface in surfaces[2:]:
            self.mf.addLayer(surface)
        # RUBEM's metric square cells, even when the clone is in degrees: the
        # rasters are not reprojected.
        width = math.sqrt(self.cell_area_m2)
        rows, cols = self._shape
        self.mf.setRowWidth([width] * rows)
        self.mf.setColumnWidth([width] * cols)
        dis = self.settings.dis
        self.mf.setDISParameter(
            _TIME_UNIT_DAYS,
            _LENGTH_UNIT_METRES,
            days,
            dis.nstp,
            dis.tsmult,
            int(dis.steady_state),
        )

    def _set_bas(self) -> None:
        for target, number, layer in self._bottom_up():
            self.mf.setBoundary(self._boundaries[number], target)
            head = self._complete(
                layer.initial_head,
                self._active[number],
                0.0,
                f"The initial head of {self._label(number)}",
            )
            self.mf.setInitialHead(head, target)

    def _set_bcf(self) -> None:
        self.mf.setDryHead(DRY_HEAD)
        transient = not self.settings.dis.steady_state
        for target, number, layer in self._bottom_up():
            active = self._active[number]
            label = self._label(number)
            self.mf.setConductivity(
                layer.laytype,
                self._complete(
                    layer.horizontal_conductivity,
                    active,
                    1.0,
                    f"The horizontal conductivity of {label}",
                ),
                self._complete(
                    layer.vertical_conductivity,
                    active,
                    1.0,
                    f"The vertical conductivity of {label}",
                ),
                target,
                layer.compute_conductivity,
            )
            if transient:
                primary, secondary = _storage_sources(layer)
                self.mf.setStorage(
                    self._complete(primary, active, 0.0, f"The primary storage of {label}"),
                    self._complete(secondary, active, 0.0, f"The secondary storage of {label}"),
                    target,
                )

    def _set_wetting(self) -> None:
        layers = self.settings.wetting_layers()
        if not layers:
            return
        wetting = self.settings.wetting
        self.mf.setWettingParameter(wetting.wetfct, wetting.iwetit, wetting.ihdwet)
        # A missing WETDRY value is 0: that cell is never rewetted.
        wetdry = self._complete(wetting.map, None, 0.0, "The WETDRY map")
        for target in sorted(self.settings.pcraster_layer(number) for number in layers):
            self.mf.setWetting(wetdry, target)

    def _set_solver(self) -> None:
        solver = self.settings.solver
        self.mf.setPCG(
            solver.mxiter,
            solver.iter1,
            solver.npcond,
            solver.hclose,
            solver.rclose,
            solver.relax,
            solver.nbpol,
            solver.damp,
        )

    def _set_stress_packages(self) -> None:
        """Set RIV, GHB and DRN once, with zero conductance outside their cells.

        A cell of a package layer has a positive conductance, lies inside the
        mask (a river) and is inside the boundary of the layer. A layer
        without cells is not given to the extension, and its getter is never
        called (the extension ends the process on that call).
        """
        for package, setter, keys in _STRESS_PACKAGES:
            settings = getattr(self.settings, package)
            if not settings.enabled:
                continue
            for entry in settings.entries:
                conductance = self._values(entry.conductance)
                cells = np.isfinite(conductance) & (conductance > 0)
                mask = getattr(entry, "mask", None)
                if mask is not None:
                    mask_values = self._values(mask)
                    cells &= np.isfinite(mask_values) & (mask_values > 0)
                maps = {key: self._values(getattr(entry, key)) for key in keys}
                for number in entry.layers:
                    self._set_package_layer(
                        package, setter, entry, number, conductance, cells, maps
                    )

    def _set_package_layer(self, package, setter, entry, number, conductance, cells, maps) -> None:
        layer_cells = cells & self._active[number]
        count = int(layer_cells.sum())
        self._cells[(package, number)] = count
        if not count:
            self.logger.warning(
                "The MODFLOW %s package has no cell in %s; that layer is left out.",
                package,
                self._label(number),
            )
            return
        stress = [
            self._fill(
                values,
                layer_cells,
                0.0,
                f"The {package} {key} of {self._label(number)}",
                getattr(entry, key),
            )
            for key, values in maps.items()
        ]
        getattr(self.mf, setter)(
            *stress,
            _field(np.where(layer_cells, conductance, 0.0)),
            self.settings.pcraster_layer(number),
        )

    # ----- reading ------------------------------------------------------------

    def _values(self, source) -> np.ndarray:
        """A raster, a class lookup or a number as values over the clone (missing: NaN)."""
        if isinstance(source, ConductivityLookup):
            return pcr.pcr2numpy(self._lookup(source), np.nan)
        if isinstance(source, str):
            return pcr.pcr2numpy(pcr.scalar(read_field(source, FieldScale.SCALAR)), np.nan)
        return np.full(self._shape, float(source))

    def _lookup(self, source: ConductivityLookup) -> Field:
        """The table value of each class, read from a fresh copy of the table.

        PCRaster caches lookup tables by file name, and a calibration rewrites
        the table between the runs of one process.
        """
        classes = read_field(source.map, FieldScale.NOMINAL)
        with TemporaryDirectory(prefix="kh_", dir=self.run_directory) as directory:
            snapshot = as_path(directory) / "conductivity.tbl"
            shutil.copyfile(source.table, snapshot)
            return pcr.lookupscalar(str(snapshot), pcr.nominal(classes))

    def _complete(self, source, required, fill: float, what: str) -> Field:
        return self._fill(self._values(source), required, fill, what, source)

    def _fill(self, values, required, fill: float, what: str, source) -> Field:
        """``values`` with its missing cells filled; ``required`` cells may not be missing."""
        if required is not None:
            self._require(values, required, what, source, "cells it is used on")
        return _field(np.where(np.isfinite(values), values, fill))

    @staticmethod
    def _require(values, cells, what: str, source, where: str) -> None:
        missing = cells & ~np.isfinite(values)
        if missing.any():
            file = source.map if isinstance(source, ConductivityLookup) else source
            raise ValueError(
                f"{what} ({file}) has missing values on {int(missing.sum())} {where}, "
                f"the first at {_first_cell(missing)}."
            )

    # ----- stress periods -----------------------------------------------------

    def run_step(self, recharge_mm: Field, days_in_period: float) -> ModflowStepResult:
        """Run one stress period with the recharge of the RUBEM step.

        The water-table head is the head of this period; the root-depth
        coupling applies it to the next step.

        :param recharge_mm: Recharge of the step [mm/step]; missing cells get none.
        :type recharge_mm: Field
        :param days_in_period: Length of the step [days].
        :type days_in_period: float
        :rtype: ModflowStepResult
        :raises RuntimeError: If the model is not initialized, or MODFLOW does
            not converge (the next run of the extension would end the process).
        """
        if self.mf is None:
            raise RuntimeError("initialize() must run before the first MODFLOW step.")
        days = _period_days(days_in_period)
        self._period += 1
        dis = self.settings.dis
        if not dis.steady_state:
            self.mf.updateDISParameter(days, dis.nstp, dis.tsmult)
        recharge = pcr.cover(pcr.scalar(recharge_mm) / (1000.0 * days), pcr.scalar(0.0))
        self.mf.setRecharge(recharge, _RECHARGE_TO_HIGHEST_ACTIVE_CELL)
        self.mf.run(str(self.run_directory))
        if not self.mf.converged():
            raise RuntimeError(
                f"MODFLOW did not converge in stress period {self._period}; "
                f"see {self.run_directory / 'pcrmf.lst'}."
            )

        net, aquifer_to_river, river_to_aquifer = self._river_exchange()
        output = self.settings.output
        root_depth = self.settings.coupling.dynamic_root_depth.enabled
        heads = self._by_layer(self.mf.getHeads) if output.heads or root_depth else {}
        return ModflowStepResult(
            baseflow_mm=aquifer_to_river * days * 1000.0 / self.cell_area_m2,
            aquifer_to_river_m3_per_day=aquifer_to_river,
            river_to_aquifer_m3_per_day=river_to_aquifer,
            net_river_leakage_m3_per_day=net,
            water_table_head=self._water_table_head(heads) if root_depth else None,
            heads=heads if output.heads else {},
            storage=self._by_layer(self.mf.getStorage) if output.storage else {},
            drain_flow=self._drain_flow() if output.drain_flow else {},
        )

    def _by_layer(self, getter) -> dict[int, Field]:
        return {
            number: pcr.scalar(getter(self.settings.pcraster_layer(number)))
            for number in range(1, len(self.settings.layers) + 1)
        }

    def _layers_with_cells(self, package: str) -> list[int]:
        return [
            number for (name, number), count in self._cells.items() if name == package and count
        ]

    def _river_exchange(self) -> tuple[Field, Field, Field]:
        """Net, aquifer-to-river and river-to-aquifer leakage summed over the river layers."""
        zero = pcr.spatial(pcr.scalar(0.0))
        net, aquifer_to_river, river_to_aquifer = zero, zero, zero
        for number in self._layers_with_cells("river"):
            leakage = pcr.scalar(self.mf.getRiverLeakage(self.settings.pcraster_layer(number)))
            net = net + leakage
            # Negative leakage leaves the aquifer: that is the baseflow.
            aquifer_to_river = aquifer_to_river + pcr.max(-leakage, 0.0)
            river_to_aquifer = river_to_aquifer + pcr.max(leakage, 0.0)
        return net, aquifer_to_river, river_to_aquifer

    def _drain_flow(self) -> dict[int, Field]:
        if not self.settings.drain.enabled:
            return {}
        with_cells = set(self._layers_with_cells("drain"))
        return {
            number: (
                pcr.scalar(self.mf.getDrain(self.settings.pcraster_layer(number)))
                if number in with_cells
                else pcr.spatial(pcr.scalar(0.0))
            )
            for entry in self.settings.drain.entries
            for number in entry.layers
        }

    def _water_table_head(self, heads: dict[int, Field]) -> Field:
        """The head of the root-depth coupling, by the configured method.

        ``layer`` takes that layer; the other methods take, cell by cell, the
        first valid head from the top down (dry and inactive cells are not
        valid); ``highest_unconfined`` also skips confined layers (LAYCON 0)
        and convertible ones (LAYCON 2 and 3) where the head is above the top
        of the layer.
        """
        water_table = self.settings.coupling.dynamic_root_depth.water_table
        if water_table.method == "layer":
            return self._valid_head(water_table.layer, heads)
        selected = None
        for number, layer in enumerate(self.settings.layers, start=1):
            if water_table.method == "highest_unconfined" and layer.laycon == 0:
                continue
            candidate = self._valid_head(number, heads)
            if water_table.method == "highest_unconfined" and layer.laycon in (2, 3):
                top = self._surfaces[self.settings.pcraster_layer(number)]
                candidate = pcr.ifthen(candidate <= top, candidate)
            selected = candidate if selected is None else pcr.cover(selected, candidate)
        return selected

    def _valid_head(self, number: int, heads: dict[int, Field]) -> Field:
        head = heads[number]
        valid = pcr.defined(head) & (self._boundaries[number] != 0) & (head != DRY_HEAD)
        return pcr.ifthen(valid, head)
