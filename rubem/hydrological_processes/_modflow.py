"""Groundwater module based on the PCRaster MODFLOW extension.

This first version is intended to couple RUBEM recharge to MODFLOW and return
river-aquifer exchange to RUBEM.  It supports a generic number of aquifer
layers configured in JSON, transient DIS parameters, PCG, optional wetting,
RIV, GHB and DRN, recharge to the highest active cell,
and retrieval of heads/storage.

WEL is not implemented and fails explicitly if configured as enabled.

Layer numbering follows PCRaster MODFLOW: layer 1 is the bottom layer and
layer N is the uppermost layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Optional

import numpy as np
import pcraster as pcr
from pcraster import initialise
from pcraster._pcraster import Field


@dataclass
class ModflowStepResult:
    converged: bool
    baseflow_mm: Field

    water_table_head: Field | None

    aquifer_to_river_m3_per_day: Field
    river_to_aquifer_m3_per_day: Field
    net_river_leakage_m3_per_day: Field

    heads: dict[int, Field] = field(default_factory=dict)
    storage: dict[int, Field] = field(default_factory=dict)
    # Signed MODFLOW flux: negative means aquifer -> drain (m3/day).
    drain_flow: dict[int, Field] = field(default_factory=dict)


class ModflowGroundwater:
    """PCRaster MODFLOW groundwater component for RUBEM.

    Parameters
    ----------
    config:
        The ``MODFLOW`` section of the RUBEM configuration.  It may be a
        regular dictionary or an object with equivalent attributes (for
        example, a Pydantic model).
    cell_area_m2:
        Horizontal area of one RUBEM/MODFLOW cell in square metres. Its square
        root sets the MODFLOW row and column widths independently of the clone
        coordinate units. This area also converts RIV leakage [m3/day] back to
        an equivalent RUBEM water depth [mm/timestep].
    logger:
        Optional logger.  If omitted, a module logger is created.

    Notes
    -----
    * RUBEM recharge is expected in mm per RUBEM timestep.
    * MODFLOW is configured with days as the time unit and metres as the
      length unit, so recharge is converted to m/day.
    * RIV leakage follows the sign convention used by the legacy coupling:
      negative leakage is interpreted as aquifer -> river and therefore as
      baseflow; positive leakage is river -> aquifer.
    """

    def __init__(
        self,
        config: Any,
        cell_area_m2: float,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.cell_area_m2 = float(cell_area_m2)

        self.enabled = bool(self._get(config, "enabled", 0))
        self.layers = list(self._get(config, "layers", []))
        self.number_layers = len(self.layers)
        self.dry_head = -999.9

        self.mf = None
        self._initialized = False
        self._boundaries: dict[int, Field] = {}
        self._drain_active_layers: set[int] = set()

        if not np.isfinite(self.cell_area_m2) or self.cell_area_m2 <= 0:
            raise ValueError("MODFLOW cell_area_m2 must be finite and greater than zero.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def initialize(self, first_period_days: int) -> None:
        """Create and configure the persistent PCRaster MODFLOW object.

        This method must be called once from the RUBEM ``initial()`` method,
        after the PCRaster clone has already been set.
        """

        if not self.enabled:
            self.logger.info("MODFLOW module disabled by configuration.")
            return

        if self._initialized:
            raise RuntimeError("MODFLOW module has already been initialized.")

        self._validate_configuration()
        self._validate_period_days(first_period_days)

        self.logger.info(
            "Initializing PCRaster MODFLOW with %d layer(s)...",
            self.number_layers,
        )

        # The RUBEM model has already called pcr.setclone(...).
        # Keep one single persistent MODFLOW object for the full simulation.
        self.mf = initialise(pcr.clone())

        # Grid/layer geometry first.
        self._setup_geometry()
        self._setup_cell_dimensions()

        # DIS must be configured before BAS/BCF and solver packages.
        self._setup_dis(first_period_days)

        # BCF optional setting.
        self.mf.setDryHead(self.dry_head)

        self._setup_layer_properties()
        self._setup_wetting()
        self._setup_solver()

        self._initialized = True
        self.logger.info("PCRaster MODFLOW initialization completed.")

    def run_timestep(
        self,
        recharge_mm: Field,
        days_in_period: int,
    ) -> ModflowStepResult:
        """Run one MODFLOW stress period coupled to the current RUBEM step.

        Parameters
        ----------
        recharge_mm:
            RUBEM recharge in mm accumulated over the current timestep.
        days_in_period:
            Number of days represented by the RUBEM timestep (e.g. 28--31
            for a monthly simulation).
        """

        if not self.enabled:
            raise RuntimeError("MODFLOW run requested while MODFLOW is disabled.")

        if not self._initialized or self.mf is None:
            raise RuntimeError("MODFLOW must be initialized before run_timestep().")

        self._validate_period_days(days_in_period)

        # Update stress-period length so calendar months can have 28--31 days.
        dis_cfg = self._get(self.config, "dis", {})

        nstp = int(
            self._get(
                dis_cfg,
                "nstp",
                5,
            )
        )

        tsmult = float(
            self._get(
                dis_cfg,
                "tsmult",
                1.0,
            )
        )

        steady_state = int(
            self._get(
                dis_cfg,
                "steady_state",
                0,
            )
        )

        # Stress-period length is updated only for transient simulations.
        if steady_state == 0:
            self.mf.updateDISParameter(
                float(days_in_period),
                nstp,
                tsmult,
            )

        # Stress packages can be changed every dynamic timestep.
        recharge_m_per_day = self.recharge_mm_to_modflow(
            recharge_mm,
            days_in_period,
        )
        recharge_cfg = self._get(self.config, "recharge", {})
        recharge_option = int(self._get(recharge_cfg, "option", 3))
        self.mf.setRecharge(pcr.cover(recharge_m_per_day, pcr.scalar(0)), recharge_option)

        self._set_river_stress()
        self._set_ghb_stress()
        self._set_drain_stress()

        self.logger.debug("Running PCRaster MODFLOW...")
        self.mf.run()

        converged = bool(self.mf.converged())
        solver_cfg = self._get(self.config, "solver", {})
        fail_on_non_convergence = bool(self._get(solver_cfg, "fail_on_non_convergence", True))

        if not converged:
            message = "PCRaster MODFLOW did not converge for the current stress period."
            if fail_on_non_convergence:
                raise RuntimeError(message)
            self.logger.warning(message)

        exchange = self._get_river_exchange()

        coupling_cfg = self._get(
            self.config,
            "coupling",
            {},
        )

        dynamic_root_cfg = self._get(
            coupling_cfg,
            "dynamic_root_depth",
            {},
        )

        if bool(
            self._get(
                dynamic_root_cfg,
                "enabled",
                0,
            )
        ):
            water_table_head = self._get_water_table_head()
        else:
            water_table_head = None

        baseflow_mm = self.volume_rate_to_depth(
            exchange["aquifer_to_river"],
            days_in_period,
        )

        heads = self._get_heads_if_requested()
        storage = self._get_storage_if_requested()

        return ModflowStepResult(
            converged=converged,
            baseflow_mm=baseflow_mm,
            aquifer_to_river_m3_per_day=exchange["aquifer_to_river"],
            river_to_aquifer_m3_per_day=exchange["river_to_aquifer"],
            net_river_leakage_m3_per_day=exchange["net"],
            heads=heads,
            storage=storage,
            water_table_head=water_table_head,
            drain_flow=self._get_drain_flow_if_requested(),
        )

    def recharge_mm_to_modflow(
        self,
        recharge_mm: Field,
        days_in_period: int,
    ) -> Field:
        """Convert RUBEM recharge [mm/timestep] to MODFLOW [m/day]."""

        self._validate_period_days(days_in_period)
        return pcr.scalar(recharge_mm) / (1000.0 * float(days_in_period))

    def volume_rate_to_depth(
        self,
        volume_rate_m3_per_day: Field,
        days_in_period: int,
    ) -> Field:
        """Convert cell flow [m3/day] to water depth [mm/timestep]."""

        self._validate_period_days(days_in_period)
        return (
            pcr.scalar(volume_rate_m3_per_day) * float(days_in_period) * 1000.0 / self.cell_area_m2
        )

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------
    def _read_scalar_input(self, path, label, required=None, fill=0.0) -> Field:
        """Read a map, constant or lookup; validate and fill unused cells."""
        lookup = self._get(path, "table") is not None
        if lookup:
            classes = pcr.readmap(str(self._get(path, "map")))
            if classes.dataType() != pcr.Nominal:
                raise ValueError(f"{label}.map must be a nominal PCRaster map.")
            table = Path(self._get(path, "table"))
            # PCRaster caches tables by filename. A fresh snapshot is needed
            # when a calibrator rewrites a table between runs in one process.
            with TemporaryDirectory(prefix="rubem_kh_") as directory:
                snapshot = Path(directory) / "conductivity.tbl"
                snapshot.write_bytes(table.read_bytes())
                try:
                    raster = pcr.lookupscalar(str(snapshot), classes)
                except RuntimeError as error:
                    raise ValueError(
                        f"{label}: cannot read lookup table {table}: {error}"
                    ) from error
            label = f"{label} lookup (check class coverage in the map and table)"
        elif isinstance(path, (int, float)):
            self._validate_constant(path, label)
            raster = pcr.spatial(pcr.scalar(float(path)))
        elif isinstance(path, Field):
            raster = path
        else:
            raster = pcr.scalar(pcr.readmap(str(path)))
        values = pcr.pcr2numpy(raster, np.nan)
        finite = np.isfinite(values)
        if required is not None:
            invalid = required & ~finite
            if invalid.any():
                row, column = np.argwhere(invalid)[0] + 1
                raise ValueError(
                    f"{label}: missing or non-finite value in a required cell "
                    f"(row {row}, column {column})."
                )
        if lookup:
            used = required if required is not None else finite
            invalid = used & (values <= 0)
            if invalid.any():
                row, column = np.argwhere(invalid)[0] + 1
                raise ValueError(
                    f"{label}: conductivity must be positive (row {row}, column {column})."
                )
        return pcr.numpy2pcr(pcr.Scalar, np.where(finite, values, fill), np.nan)

    def _read_stress_inputs(self, package, layer_number, conductance, mask=None, **heads):
        """Build complete stress maps, with zero conductance outside BAS cells."""
        active = pcr.scalar(self._boundaries[layer_number]) != 0
        cond = self._read_scalar_input(conductance, f"{package}.conductance")
        if mask is not None:
            river_cells = self._read_scalar_input(mask, f"{package}.mask") > 0
            cond = pcr.ifthenelse(river_cells, cond, pcr.scalar(0))
        cond = pcr.ifthenelse(active, cond, pcr.scalar(0))
        required = pcr.pcr2numpy(cond, 0) > 0
        maps = {
            key: self._read_scalar_input(path, f"{package}.{key}", required)
            for key, path in heads.items()
        }
        return cond, maps

    def _setup_geometry(self) -> None:
        """Complete DIS geometry only in columns inactive in every layer.

        DIS requires elevations over the whole rectangular clone. BAS maps
        define the groundwater domain, including constant-head cells. Missing
        BAS values become inactive; elevations in the domain are never filled.
        """
        domain = None
        for number, layer in enumerate(self.layers, start=1):
            label = f"MODFLOW.layers[{number - 1}].boundary"
            path = self._required(layer, "boundary", label)
            boundary = pcr.cover(pcr.nominal(pcr.readmap(str(path))), pcr.nominal(0))
            self._boundaries[number] = boundary
            active = pcr.pcr2numpy(boundary, 0) != 0
            domain = active if domain is None else domain | active

        surfaces = [("MODFLOW.bottom", self._required(self.config, "bottom", "MODFLOW.bottom"))]
        for index, layer in enumerate(self.layers):
            label = f"MODFLOW.layers[{index}].top"
            surfaces.append((label, self._required(layer, "top", label)))

        elevations = []
        previous = None
        for index, (label, path) in enumerate(surfaces):
            values = pcr.pcr2numpy(pcr.scalar(pcr.readmap(str(path))), np.nan)
            invalid = domain & ~np.isfinite(values)
            if invalid.any():
                row, column = np.argwhere(invalid)[0] + 1
                raise ValueError(
                    f"{label}: missing or non-finite elevation in a column active "
                    f"in at least one MODFLOW layer (row {row}, column {column}). "
                    "Supply elevations throughout the groundwater domain."
                )

            # Synthetic 1 m layers outside the domain satisfy DIS geometry
            # without adding groundwater cells or changing any input files.
            values = np.where(domain, values, float(index))
            if previous is not None:
                invalid = domain & (values <= previous)
                if invalid.any():
                    row, column = np.argwhere(invalid)[0] + 1
                    raise ValueError(
                        f"{label}: top must be above the underlying surface "
                        f"(row {row}, column {column})."
                    )
            elevations.append(pcr.numpy2pcr(pcr.Scalar, values, np.nan))
            previous = values

        self.mf.createBottomLayer(elevations[0], elevations[1])
        for top in elevations[2:]:
            self.mf.addLayer(top)

    def _setup_cell_dimensions(self) -> None:
        """Use RUBEM's metric square cells even when map coordinates are degrees.

        This preserves the configured constant-area approximation; it does
        not reproject rasters or compute geodesic cell dimensions.
        """
        width_m = self.cell_area_m2**0.5
        self.mf.setRowWidth([width_m] * pcr.clone().nrRows())
        self.mf.setColumnWidth([width_m] * pcr.clone().nrCols())
        self.logger.info(
            "MODFLOW cell dimensions: %.6g x %.6g metres (RUBEM grid area); "
            "raster coordinates are unchanged.",
            width_m,
            width_m,
        )

    def _setup_dis(self, first_period_days: int) -> None:
        """Configure the transient MODFLOW discretization package."""

        dis_cfg = self._get(self.config, "dis", {})

        time_unit = int(self._get(dis_cfg, "time_unit", 4))
        length_unit = int(self._get(dis_cfg, "length_unit", 2))
        nstp = int(self._get(dis_cfg, "nstp", 5))
        tsmult = float(self._get(dis_cfg, "tsmult", 1.0))
        steady_state = int(self._get(dis_cfg, "steady_state", 0))

        # This first version deliberately expects days/metres because all
        # coupling conversions below are defined in m/day.
        if time_unit != 4:
            raise ValueError("MODFLOW.dis.time_unit must be 4 (days) in this first version.")
        if length_unit != 2:
            raise ValueError("MODFLOW.dis.length_unit must be 2 (metres) in this first version.")

        self.mf.setDISParameter(
            time_unit,
            length_unit,
            float(first_period_days),
            nstp,
            tsmult,
            steady_state,
        )

    def _setup_layer_properties(self) -> None:
        """Configure BAS and BCF data for each aquifer layer."""

        dis_cfg = self._get(self.config, "dis", {})
        transient = int(self._get(dis_cfg, "steady_state", 0)) == 0

        for layer_number, layer in enumerate(self.layers, start=1):
            initial_head = self._required(
                layer,
                "initial_head",
                f"MODFLOW.layers[{layer_number - 1}].initial_head",
            )
            horizontal_conductivity = self._required(
                layer,
                "horizontal_conductivity",
                f"MODFLOW.layers[{layer_number - 1}].horizontal_conductivity",
            )
            vertical_conductivity = self._required(
                layer,
                "vertical_conductivity",
                f"MODFLOW.layers[{layer_number - 1}].vertical_conductivity",
            )

            laytype = int(self._get(layer, "laytype", 0))
            compute_conductivity = bool(self._get(layer, "compute_conductivity", True))

            active = pcr.pcr2numpy(self._boundaries[layer_number], 0) != 0
            self.mf.setBoundary(self._boundaries[layer_number], layer_number)
            self.mf.setInitialHead(
                self._read_scalar_input(initial_head, f"Layer {layer_number}.initial_head", active),
                layer_number,
            )

            # PCRaster MODFLOW expects horizontal conductivity first and
            # vertical conductivity second.  In the legacy Bauru data:
            #   KY*.map -> horizontal conductivity
            #   KX*.map -> vertical conductivity
            self.mf.setConductivity(
                laytype,
                self._read_scalar_input(
                    horizontal_conductivity,
                    f"Layer {layer_number}.horizontal_conductivity",
                    active,
                    fill=1.0,
                ),
                self._read_scalar_input(
                    vertical_conductivity,
                    f"Layer {layer_number}.vertical_conductivity",
                    active,
                    fill=1.0,
                ),
                layer_number,
                compute_conductivity,
            )

            if transient:
                laycon = laytype % 10

                if laycon == 0:
                    # Confined.
                    primary_storage = self._required(
                        layer,
                        "specific_storage",
                        f"MODFLOW.layers[{layer_number - 1}].specific_storage",
                    )

                    # Sf2 is not physically used for LAYCON 0,
                    # but setStorage requires a second map.
                    secondary_storage = primary_storage

                elif laycon == 1:
                    # Unconfined.
                    specific_yield = self._required(
                        layer,
                        "specific_yield",
                        f"MODFLOW.layers[{layer_number - 1}].specific_yield",
                    )

                    primary_storage = specific_yield
                    secondary_storage = specific_yield

                elif laycon in (2, 3):
                    # Convertible.
                    primary_storage = self._required(
                        layer,
                        "specific_storage",
                        f"MODFLOW.layers[{layer_number - 1}].specific_storage",
                    )

                    secondary_storage = self._required(
                        layer,
                        "specific_yield",
                        f"MODFLOW.layers[{layer_number - 1}].specific_yield",
                    )

                else:
                    raise ValueError(f"Unsupported LAYCON {laycon} for layer {layer_number}.")

                self.mf.setStorage(
                    self._read_scalar_input(
                        primary_storage, f"Layer {layer_number}.primary_storage", active
                    ),
                    self._read_scalar_input(
                        secondary_storage, f"Layer {layer_number}.secondary_storage", active
                    ),
                    layer_number,
                )

    def _setup_wetting(self) -> None:
        """Configure optional BCF wetting capability."""

        wetting_cfg = self._get(self.config, "wetting", {})
        if not bool(self._get(wetting_cfg, "enabled", 0)):
            return

        wetfct = float(self._get(wetting_cfg, "wetfct", 1.0))
        iwetit = int(self._get(wetting_cfg, "iwetit", 3))
        ihdwet = int(self._get(wetting_cfg, "ihdwet", 0))

        self.mf.setWettingParameter(wetfct, iwetit, ihdwet)

        layers = self._get(wetting_cfg, "layers", None)
        if layers is None:
            wetting_layers = [
                layer_number
                for layer_number, layer in enumerate(self.layers, start=1)
                if (int(self._get(layer, "laytype", 0)) % 10) in (1, 3)
            ]

            if not wetting_layers:
                raise ValueError("Wetting is enabled, but no MODFLOW layer has LAYCON 1 or 3.")

        else:
            wetting_layers = [int(value) for value in layers]

        wetting_map_path = self._get(wetting_cfg, "map", None)

        if wetting_map_path:
            wetting_map = self._read_scalar_input(wetting_map_path, "MODFLOW.wetting.map")
        else:
            # Compatibility option for the legacy Bauru approach, where the
            # wetting map was derived as -1 * boundary of the top layer.
            source = self._get(wetting_cfg, "source_boundary_layer", None)
            if source is None:
                raise ValueError(
                    "Wetting is enabled, but neither MODFLOW.wetting.map nor "
                    "MODFLOW.wetting.source_boundary_layer was provided."
                )

            if isinstance(source, str) and source.lower() == "top":
                source_layer = self.number_layers
            else:
                source_layer = int(source)

            self._validate_layer_number(source_layer, "wetting source layer")
            source_boundary = self._required(
                self.layers[source_layer - 1],
                "boundary",
                f"MODFLOW.layers[{source_layer - 1}].boundary",
            )
            multiplier = float(self._get(wetting_cfg, "multiplier", -1.0))
            wetting_map = (
                pcr.cover(pcr.scalar(pcr.readmap(str(source_boundary))), pcr.scalar(0)) * multiplier
            )

        for layer_number in wetting_layers:
            self._validate_layer_number(
                layer_number,
                "wetting layer",
            )

            layer = self.layers[layer_number - 1]

            laytype = int(
                self._get(
                    layer,
                    "laytype",
                    0,
                )
            )

            laycon = laytype % 10

            if laycon not in (1, 3):
                raise ValueError(
                    f"Wetting cannot be applied to MODFLOW "
                    f"layer {layer_number}: LAYCON={laycon}. "
                    "Wetting requires LAYCON 1 or 3."
                )

            self.mf.setWetting(
                wetting_map,
                layer_number,
            )

    def _setup_solver(self) -> None:
        """Configure the MODFLOW solver.  Version 1 supports PCG."""

        solver_cfg = self._get(self.config, "solver", {})
        solver_type = str(self._get(solver_cfg, "type", "PCG")).upper()

        if solver_type != "PCG":
            raise NotImplementedError(
                f"Solver '{solver_type}' is not implemented in this first MODFLOW module."
            )

        self.mf.setPCG(
            int(self._get(solver_cfg, "mxiter", 2000)),
            int(self._get(solver_cfg, "iter1", 20)),
            int(self._get(solver_cfg, "npcond", 1)),
            float(self._get(solver_cfg, "hclose", 5.0)),
            float(self._get(solver_cfg, "rclose", 3.0)),
            float(self._get(solver_cfg, "relax", 1.0)),
            int(self._get(solver_cfg, "nbpol", 2)),
            float(self._get(solver_cfg, "damp", 0.5)),
        )

    # ------------------------------------------------------------------
    # Dynamic stress packages and outputs
    # ------------------------------------------------------------------
    def _set_river_stress(self) -> None:
        river_cfg = self._get(self.config, "river", {})
        if not bool(self._get(river_cfg, "enabled", 0)):
            return

        river_layers = list(self._get(river_cfg, "layers", []))

        for river_layer in river_layers:
            layer_number = int(self._required(river_layer, "layer", "MODFLOW.river.layers[].layer"))
            self._validate_layer_number(layer_number, "river layer")

            stage = self._required(
                river_layer,
                "stage",
                "MODFLOW.river.layers[].stage",
            )
            bottom = self._required(
                river_layer,
                "bottom",
                "MODFLOW.river.layers[].bottom",
            )
            conductance = self._required(
                river_layer,
                "conductance",
                "MODFLOW.river.layers[].conductance",
            )
            mask = self._get(river_layer, "mask")
            if isinstance(conductance, (int, float)) and mask is None:
                raise ValueError("Constant river conductance requires a 'mask' map.")

            cond, maps = self._read_stress_inputs(
                f"MODFLOW.river.layer{layer_number}",
                layer_number,
                conductance,
                mask=mask,
                stage=stage,
                bottom=bottom,
            )
            self.mf.setRiver(
                maps["stage"],
                maps["bottom"],
                cond,
                layer_number,
            )

    def _set_ghb_stress(self) -> None:
        """Apply external heads and conductances before each stress period.

        PCRaster activates GHB where conductance is positive. These exchanges
        affect groundwater heads; RUBEM baseflow is still obtained from RIV.
        """
        ghb_cfg = self._get(self.config, "ghb", {})
        if not bool(self._get(ghb_cfg, "enabled", 0)):
            return

        for ghb_layer in self._get(ghb_cfg, "layers", []):
            layer_number = int(self._required(ghb_layer, "layer", "MODFLOW.ghb.layers[].layer"))
            self._validate_layer_number(layer_number, "GHB layer")
            head = self._required(ghb_layer, "head", "MODFLOW.ghb.layers[].head")
            conductance = self._required(
                ghb_layer, "conductance", "MODFLOW.ghb.layers[].conductance"
            )
            cond, maps = self._read_stress_inputs(
                f"MODFLOW.ghb.layer{layer_number}", layer_number, conductance, head=head
            )
            self.mf.setGeneralHead(maps["head"], cond, layer_number)

    def _set_drain_stress(self) -> None:
        """Apply optional drains without adding their discharge to RUBEM baseflow."""
        drain_cfg = self._get(self.config, "drain", {})
        if not bool(self._get(drain_cfg, "enabled", 0)):
            return

        self._drain_active_layers.clear()
        for drain_layer in self._get(drain_cfg, "layers", []):
            layer_number = int(self._required(drain_layer, "layer", "MODFLOW.drain.layers[].layer"))
            self._validate_layer_number(layer_number, "DRN layer")
            elevation = self._required(drain_layer, "elevation", "MODFLOW.drain.layers[].elevation")
            conductance = self._required(
                drain_layer, "conductance", "MODFLOW.drain.layers[].conductance"
            )
            cond, maps = self._read_stress_inputs(
                f"MODFLOW.drain.layer{layer_number}",
                layer_number,
                conductance,
                elevation=elevation,
            )
            values = pcr.pcr2numpy(cond, 0)
            if (values < 0).any():
                raise ValueError(f"DRN layer {layer_number}: conductance must be non-negative.")
            if (values > 0).any():
                self._drain_active_layers.add(layer_number)
            self.mf.setDrain(maps["elevation"], cond, layer_number)

    def _get_drain_flow_if_requested(self) -> dict[int, Field]:
        """Return signed cell flows (m3/day), separately from RIV baseflow."""
        drain_cfg = self._get(self.config, "drain", {})
        output_cfg = self._get(self.config, "output", {})
        if not (
            bool(self._get(drain_cfg, "enabled", 0))
            and bool(self._get(output_cfg, "drain_flow", False))
        ):
            return {}
        result = {}
        for layer in self._get(drain_cfg, "layers", []):
            number = int(self._get(layer, "layer"))
            result[number] = (
                self.mf.getDrain(number)
                if number in self._drain_active_layers
                else pcr.spatial(pcr.scalar(0))
            )
        return result

    def _get_river_exchange(self) -> dict[str, Field]:
        """Aggregate RIV exchange over all configured river layers."""

        zero = pcr.scalar(0.0)
        total_net = zero
        total_aquifer_to_river = zero
        total_river_to_aquifer = zero

        river_cfg = self._get(self.config, "river", {})
        if not bool(self._get(river_cfg, "enabled", 0)):
            return {
                "net": total_net,
                "aquifer_to_river": total_aquifer_to_river,
                "river_to_aquifer": total_river_to_aquifer,
            }

        for river_layer in self._get(river_cfg, "layers", []):
            layer_number = int(self._get(river_layer, "layer"))
            leakage = pcr.scalar(self.mf.getRiverLeakage(layer_number))

            # Preserve the legacy RUBEM-MODFLOW sign interpretation:
            # leakage < 0 -> groundwater discharges to river -> baseflow.
            aquifer_to_river = pcr.max(-leakage, zero)
            river_to_aquifer = pcr.max(leakage, zero)

            total_net = total_net + leakage
            total_aquifer_to_river = total_aquifer_to_river + aquifer_to_river
            total_river_to_aquifer = total_river_to_aquifer + river_to_aquifer

        return {
            "net": total_net,
            "aquifer_to_river": total_aquifer_to_river,
            "river_to_aquifer": total_river_to_aquifer,
        }

    def _get_heads_if_requested(self) -> dict[int, Field]:
        output_cfg = self._get(self.config, "output", {})
        if not bool(self._get(output_cfg, "heads", True)):
            return {}

        return {
            layer_number: self.mf.getHeads(layer_number)
            for layer_number in range(1, self.number_layers + 1)
        }

    def _get_valid_head_for_layer(
        self,
        layer_number: int,
    ) -> Field:
        """Return valid head for one MODFLOW layer."""

        layer = self.layers[layer_number - 1]

        head = pcr.scalar(self.mf.getHeads(layer_number))

        boundary_path = self._required(
            layer,
            "boundary",
            f"MODFLOW.layers[{layer_number - 1}].boundary",
        )

        boundary = pcr.scalar(pcr.readmap(str(boundary_path)))

        valid_head = pcr.defined(head) & (boundary != 0) & (head != self.dry_head)

        return pcr.ifthen(
            valid_head,
            head,
        )

    def _get_water_table_head(self) -> Field:
        """Select groundwater head for RUBEM root-depth coupling."""

        coupling_cfg = self._get(
            self.config,
            "coupling",
            {},
        )

        root_cfg = self._get(
            coupling_cfg,
            "dynamic_root_depth",
            {},
        )

        water_table_cfg = self._get(
            root_cfg,
            "water_table",
            {},
        )

        method = self._get(
            water_table_cfg,
            "method",
            "highest_unconfined",
        )

        valid_methods = {
            "highest_unconfined",
            "highest_active_head",
            "layer",
        }

        if method not in valid_methods:
            raise ValueError(f"Invalid water-table selection method: {method!r}.")

        # -----------------------------------------------------
        # Explicit layer
        # -----------------------------------------------------

        if method == "layer":
            layer_number = int(
                self._required(
                    water_table_cfg,
                    "layer",
                    "MODFLOW.coupling.dynamic_root_depth.water_table.layer",
                )
            )

            self._validate_layer_number(
                layer_number,
                "water-table source layer",
            )

            return self._get_valid_head_for_layer(layer_number)

        # -----------------------------------------------------
        # Search top -> bottom
        # -----------------------------------------------------

        selected_head = None

        for layer_number in range(
            self.number_layers,
            0,
            -1,
        ):
            layer = self.layers[layer_number - 1]

            laytype = int(
                self._get(
                    layer,
                    "laytype",
                    0,
                )
            )

            laycon = laytype % 10

            candidate = self._get_valid_head_for_layer(layer_number)

            if method == "highest_unconfined":
                # LAYCON 0 is always confined.
                if laycon == 0:
                    continue

                # LAYCON 1 is explicitly unconfined.
                if laycon == 1:
                    pass

                # LAYCON 2 and 3 are convertible.
                # They behave as unconfined where the head is at or below
                # the top elevation of the layer.
                elif laycon in (2, 3):
                    top_path = self._required(
                        layer,
                        "top",
                        f"MODFLOW.layers[{layer_number - 1}].top",
                    )

                    layer_top = pcr.scalar(pcr.readmap(str(top_path)))

                    candidate = pcr.ifthen(
                        pcr.defined(candidate) & (candidate <= layer_top),
                        candidate,
                    )

            if selected_head is None:
                selected_head = candidate

            else:
                selected_head = pcr.cover(
                    selected_head,
                    candidate,
                )

        if selected_head is None:
            raise RuntimeError(
                "No MODFLOW layer satisfies the configured "
                f"water-table selection method '{method}'."
            )

        return selected_head

    def _get_storage_if_requested(self) -> dict[int, Field]:
        output_cfg = self._get(self.config, "output", {})
        if not bool(self._get(output_cfg, "storage", False)):
            return {}

        return {
            layer_number: self.mf.getStorage(layer_number)
            for layer_number in range(1, self.number_layers + 1)
        }

    # ------------------------------------------------------------------
    # Validation and configuration helpers
    # ------------------------------------------------------------------
    def _validate_configuration(self) -> None:
        if self.number_layers < 1:
            raise ValueError("MODFLOW.layers must contain at least one layer.")

        recharge_cfg = self._get(self.config, "recharge", {})
        recharge_option = int(self._get(recharge_cfg, "option", 3))
        if recharge_option != 3:
            raise ValueError(
                "MODFLOW.recharge.option must be 3 (recharge to the highest active cell)."
            )

        river_cfg = self._get(self.config, "river", {})
        if bool(self._get(river_cfg, "enabled", 0)):
            river_layers = list(self._get(river_cfg, "layers", []))
            if not river_layers:
                raise ValueError("MODFLOW.river.enabled is true but MODFLOW.river.layers is empty.")

            seen_layers: set[int] = set()
            for river_layer in river_layers:
                layer_number = int(
                    self._required(
                        river_layer,
                        "layer",
                        "MODFLOW.river.layers[].layer",
                    )
                )
                self._validate_layer_number(layer_number, "river layer")
                if layer_number in seen_layers:
                    raise ValueError(
                        f"MODFLOW river layer {layer_number} is configured more than once."
                    )
                seen_layers.add(layer_number)

        ghb_cfg = self._get(self.config, "ghb", {})
        if bool(self._get(ghb_cfg, "enabled", 0)):
            ghb_layers = list(self._get(ghb_cfg, "layers", []))
            if not ghb_layers:
                raise ValueError("MODFLOW.ghb.enabled=1 requires at least one GHB layer.")
            seen_ghb_layers: set[int] = set()
            for ghb_layer in ghb_layers:
                layer_number = int(self._required(ghb_layer, "layer", "MODFLOW.ghb.layers[].layer"))
                self._validate_layer_number(layer_number, "GHB layer")
                if layer_number in seen_ghb_layers:
                    raise ValueError(
                        f"MODFLOW GHB layer {layer_number} is configured more than once."
                    )
                seen_ghb_layers.add(layer_number)

        drain_cfg = self._get(self.config, "drain", {})
        if bool(self._get(drain_cfg, "enabled", 0)):
            drain_layers = list(self._get(drain_cfg, "layers", []))
            if not drain_layers:
                raise ValueError("MODFLOW.drain.enabled=1 requires at least one DRN layer.")
            seen_drain_layers: set[int] = set()
            for drain_layer in drain_layers:
                number = int(self._required(drain_layer, "layer", "MODFLOW.drain.layers[].layer"))
                self._validate_layer_number(number, "DRN layer")
                if number in seen_drain_layers:
                    raise ValueError(f"MODFLOW DRN layer {number} is configured more than once.")
                seen_drain_layers.add(number)

        wells_cfg = self._get(self.config, "wells", {})
        if bool(self._get(wells_cfg, "enabled", 0)):
            raise NotImplementedError(
                "WEL is enabled in the configuration but is not implemented "
                "in this first MODFLOW module version."
            )

        # Validate required paths early, before PCRaster emits a less explicit
        # error during MODFLOW package setup.
        paths: list[tuple[str, Any]] = [
            ("MODFLOW.bottom", self._required(self.config, "bottom", "MODFLOW.bottom"))
        ]

        for index, layer in enumerate(self.layers):
            for key in (
                "top",
                "horizontal_conductivity",
                "vertical_conductivity",
                "boundary",
                "initial_head",
            ):
                paths.append(
                    (
                        f"MODFLOW.layers[{index}].{key}",
                        self._required(layer, key, f"MODFLOW.layers[{index}].{key}"),
                    )
                )

            dis_cfg = self._get(self.config, "dis", {})

            if int(self._get(dis_cfg, "steady_state", 0)) == 0:
                laytype = int(
                    self._get(
                        layer,
                        "laytype",
                        0,
                    )
                )

                laycon = laytype % 10

                storage_keys = []

                if laycon == 0:
                    storage_keys = [
                        "specific_storage",
                    ]

                elif laycon == 1:
                    storage_keys = [
                        "specific_yield",
                    ]

                elif laycon in (2, 3):
                    storage_keys = [
                        "specific_storage",
                        "specific_yield",
                    ]

                for key in storage_keys:
                    paths.append(
                        (
                            f"MODFLOW.layers[{index}].{key}",
                            self._required(
                                layer,
                                key,
                                f"MODFLOW.layers[{index}].{key}",
                            ),
                        )
                    )

        if bool(self._get(river_cfg, "enabled", 0)):
            for index, river_layer in enumerate(self._get(river_cfg, "layers", [])):
                mask = self._get(river_layer, "mask")
                if isinstance(self._get(river_layer, "conductance"), (int, float)) and mask is None:
                    raise ValueError("Constant river conductance requires a 'mask' map.")
                if mask is not None:
                    paths.append((f"MODFLOW.river.layers[{index}].mask", mask))
                for key in ("stage", "bottom", "conductance"):
                    paths.append(
                        (
                            f"MODFLOW.river.layers[{index}].{key}",
                            self._required(
                                river_layer,
                                key,
                                f"MODFLOW.river.layers[{index}].{key}",
                            ),
                        )
                    )

        if bool(self._get(ghb_cfg, "enabled", 0)):
            for index, ghb_layer in enumerate(self._get(ghb_cfg, "layers", [])):
                for key in ("head", "conductance"):
                    label = f"MODFLOW.ghb.layers[{index}].{key}"
                    paths.append((label, self._required(ghb_layer, key, label)))

        if bool(self._get(drain_cfg, "enabled", 0)):
            for index, drain_layer in enumerate(self._get(drain_cfg, "layers", [])):
                for key in ("elevation", "conductance"):
                    label = f"MODFLOW.drain.layers[{index}].{key}"
                    paths.append((label, self._required(drain_layer, key, label)))

        wetting_cfg = self._get(self.config, "wetting", {})
        wetting_path = self._get(wetting_cfg, "map", None)
        if bool(self._get(wetting_cfg, "enabled", 0)) and wetting_path:
            paths.append(("MODFLOW.wetting.map", wetting_path))

        for label, path in paths:
            if isinstance(path, (int, float)):
                self._validate_constant(path, label)
                if label.endswith(".specific_yield") and path > 1:
                    raise ValueError(f"{label}: specific yield must be between 0 and 1.")
            elif self._get(path, "table") is not None:
                for key in ("map", "table"):
                    file_path = self._required(path, key, f"{label}.{key}")
                    if not Path(str(file_path)).is_file():
                        raise FileNotFoundError(f"{label}.{key} does not exist: {file_path}")
            elif not Path(str(path)).is_file():
                raise FileNotFoundError(f"{label} does not exist: {path}")

    @staticmethod
    def _validate_constant(value, label) -> None:
        if isinstance(value, bool) or not np.isfinite(value) or value < 0:
            raise ValueError(f"{label}: constant must be finite and non-negative.")

    def _validate_layer_number(self, layer_number: int, label: str) -> None:
        if layer_number < 1 or layer_number > self.number_layers:
            raise ValueError(
                f"Invalid {label} {layer_number}; valid range is 1-{self.number_layers}."
            )

    @staticmethod
    def _validate_period_days(days_in_period: int) -> None:
        if int(days_in_period) <= 0:
            raise ValueError("days_in_period must be greater than zero.")

    @staticmethod
    def _get(container: Any, key: str, default: Any = None) -> Any:
        """Read a key from either a mapping or an attribute-based config."""

        if container is None:
            return default
        if isinstance(container, Mapping):
            return container.get(key, default)
        return getattr(container, key, default)

    @classmethod
    def _required(cls, container: Any, key: str, label: str) -> Any:
        value = cls._get(container, key, None)
        if value is None or value == "":
            raise ValueError(f"Missing required MODFLOW configuration value: {label}")
        return value
