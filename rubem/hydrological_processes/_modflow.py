"""Groundwater module based on the PCRaster MODFLOW extension.

This first version is intended to couple RUBEM recharge to MODFLOW and return
river-aquifer exchange to RUBEM.  It supports a generic number of aquifer
layers configured in JSON, transient DIS parameters, PCG, optional wetting,
RIV, recharge to the highest active cell, and retrieval of heads/storage.

Not implemented in this first version: GHB and WEL.  They fail explicitly if
configured as enabled, so that they are never silently ignored.

Layer numbering follows PCRaster MODFLOW: layer 1 is the bottom layer and
layer N is the uppermost layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any, Mapping, Optional

import pcraster as pcr
from pcraster import initialise
from pcraster._pcraster import Field


@dataclass
class ModflowStepResult:
    """Outputs returned by one MODFLOW stress period."""

    converged: bool
    baseflow_mm: Field
    aquifer_to_river_m3_per_day: Field
    river_to_aquifer_m3_per_day: Field
    net_river_leakage_m3_per_day: Field
    heads: dict[int, Field] = field(default_factory=dict)
    storage: dict[int, Field] = field(default_factory=dict)


class ModflowGroundwater:
    """PCRaster MODFLOW groundwater component for RUBEM.

    Parameters
    ----------
    config:
        The ``MODFLOW`` section of the RUBEM configuration.  It may be a
        regular dictionary or an object with equivalent attributes (for
        example, a Pydantic model).
    cell_area_m2:
        Horizontal area of one RUBEM/MODFLOW cell in square metres.  This is
        used to convert RIV leakage [m3/day] back to an equivalent RUBEM
        water depth [mm/timestep].
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

        self.mf = None
        self._initialized = False

        if self.cell_area_m2 <= 0:
            raise ValueError("MODFLOW cell_area_m2 must be greater than zero.")

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

        self._setup_geometry()
        self._setup_dis(first_period_days)
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
        nstp = int(self._get(dis_cfg, "nstp", 5))
        tsmult = float(self._get(dis_cfg, "tsmult", 1.0))
        self.mf.updateDISParameter(float(days_in_period), nstp, tsmult)

        # Stress packages can be changed every dynamic timestep.
        recharge_m_per_day = self.recharge_mm_to_modflow(
            recharge_mm,
            days_in_period,
        )
        recharge_cfg = self._get(self.config, "recharge", {})
        recharge_option = int(self._get(recharge_cfg, "option", 3))
        self.mf.setRecharge(recharge_m_per_day, recharge_option)

        self._set_river_stress()

        self.logger.debug("Running PCRaster MODFLOW...")
        self.mf.run()

        converged = bool(self.mf.converged())
        solver_cfg = self._get(self.config, "solver", {})
        fail_on_non_convergence = bool(
            self._get(solver_cfg, "fail_on_non_convergence", True)
        )

        if not converged:
            message = "PCRaster MODFLOW did not converge for the current stress period."
            if fail_on_non_convergence:
                raise RuntimeError(message)
            self.logger.warning(message)

        exchange = self._get_river_exchange()
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
            pcr.scalar(volume_rate_m3_per_day)
            * float(days_in_period)
            * 1000.0
            / self.cell_area_m2
        )

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------
    def _setup_geometry(self) -> None:
        """Create the generic layer geometry from bottom to top."""

        bottom = self._required(self.config, "bottom", "MODFLOW.bottom")

        first_layer_top = self._required(
            self.layers[0],
            "top",
            "MODFLOW.layers[0].top",
        )

        self.mf.createBottomLayer(str(bottom), str(first_layer_top))

        for layer in self.layers[1:]:
            top = self._required(layer, "top", "MODFLOW.layers[].top")
            self.mf.addLayer(str(top))

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
            raise ValueError(
                "MODFLOW.dis.time_unit must be 4 (days) in this first version."
            )
        if length_unit != 2:
            raise ValueError(
                "MODFLOW.dis.length_unit must be 2 (metres) in this first version."
            )

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
            boundary = self._required(
                layer,
                "boundary",
                f"MODFLOW.layers[{layer_number - 1}].boundary",
            )
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
            compute_conductivity = bool(
                self._get(layer, "compute_conductivity", True)
            )

            self.mf.setBoundary(str(boundary), layer_number)
            self.mf.setInitialHead(str(initial_head), layer_number)

            # PCRaster MODFLOW expects horizontal conductivity first and
            # vertical conductivity second.  In the legacy Bauru data:
            #   KY*.map -> horizontal conductivity
            #   KX*.map -> vertical conductivity
            self.mf.setConductivity(
                laytype,
                str(horizontal_conductivity),
                str(vertical_conductivity),
                layer_number,
                compute_conductivity,
            )

            if transient:
                specific_storage = self._required(
                    layer,
                    "specific_storage",
                    f"MODFLOW.layers[{layer_number - 1}].specific_storage",
                )
                specific_yield = self._required(
                    layer,
                    "specific_yield",
                    f"MODFLOW.layers[{layer_number - 1}].specific_yield",
                )
                self.mf.setStorage(
                    str(specific_storage),
                    str(specific_yield),
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
            wetting_layers = list(range(1, self.number_layers + 1))
        else:
            wetting_layers = [int(value) for value in layers]

        wetting_map_path = self._get(wetting_cfg, "map", None)

        if wetting_map_path:
            wetting_map: Any = str(wetting_map_path)
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
            wetting_map = pcr.readmap(str(source_boundary)) * multiplier

        for layer_number in wetting_layers:
            self._validate_layer_number(layer_number, "wetting layer")
            self.mf.setWetting(wetting_map, layer_number)

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
            layer_number = int(
                self._required(river_layer, "layer", "MODFLOW.river.layers[].layer")
            )
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

            self.mf.setRiver(
                str(stage),
                str(bottom),
                str(conductance),
                layer_number,
            )

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
        if recharge_option not in (1, 3):
            raise ValueError("MODFLOW.recharge.option must be 1 or 3.")

        # This project explicitly requires recharge to the highest active cell.
        if recharge_option != 3:
            self.logger.warning(
                "MODFLOW recharge option is %d; option 3 is recommended for "
                "RUBEM coupling to the highest active cell.",
                recharge_option,
            )

        river_cfg = self._get(self.config, "river", {})
        if bool(self._get(river_cfg, "enabled", 0)):
            river_layers = list(self._get(river_cfg, "layers", []))
            if not river_layers:
                raise ValueError(
                    "MODFLOW.river.enabled is true but MODFLOW.river.layers is empty."
                )

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

        # GHB and WEL are intentionally postponed to the next implementation
        # step.  Never ignore them silently if somebody enables them in JSON.
        ghb_cfg = self._get(self.config, "ghb", {})
        if bool(self._get(ghb_cfg, "enabled", 0)):
            raise NotImplementedError(
                "GHB is enabled in the configuration but is not implemented "
                "in this first MODFLOW module version."
            )

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
                for key in ("specific_storage", "specific_yield"):
                    paths.append(
                        (
                            f"MODFLOW.layers[{index}].{key}",
                            self._required(layer, key, f"MODFLOW.layers[{index}].{key}"),
                        )
                    )

        if bool(self._get(river_cfg, "enabled", 0)):
            for index, river_layer in enumerate(self._get(river_cfg, "layers", [])):
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

        wetting_cfg = self._get(self.config, "wetting", {})
        wetting_path = self._get(wetting_cfg, "map", None)
        if bool(self._get(wetting_cfg, "enabled", 0)) and wetting_path:
            paths.append(("MODFLOW.wetting.map", wetting_path))

        for label, path in paths:
            if not Path(str(path)).exists():
                raise FileNotFoundError(f"{label} does not exist: {path}")

    def _validate_layer_number(self, layer_number: int, label: str) -> None:
        if layer_number < 1 or layer_number > self.number_layers:
            raise ValueError(
                f"Invalid {label} {layer_number}; valid range is "
                f"1-{self.number_layers}."
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
