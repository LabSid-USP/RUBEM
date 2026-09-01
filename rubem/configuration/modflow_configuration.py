"""Pydantic configuration models for the optional PCRaster MODFLOW module."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


PositiveLayer = Annotated[int, Field(ge=1)]
PositiveFloat = Annotated[float, Field(gt=0)]
PositiveInt = Annotated[int, Field(ge=1)]


class _Strict(BaseModel):
    """Strict immutable configuration section."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ModflowLayerConfiguration(_Strict):
    """Geometry and BCF/BAS properties of one MODFLOW layer.

    PCRaster MODFLOW numbers layers from bottom to top:
    layer 1 is the deepest layer and layer N is the uppermost layer.
    """

    name: str
    top: str

    # Legacy Bauru convention:
    # KY*.map -> horizontal hydraulic conductivity
    # KX*.map -> vertical hydraulic conductivity
    horizontal_conductivity: str
    vertical_conductivity: str

    boundary: str
    initial_head: str

    # Required for transient simulations (steady_state = 0).
    specific_storage: str | None = None
    specific_yield: str | None = None


    laytype: int = 0
    compute_conductivity: bool = True

    @field_validator("laytype")
    @classmethod
    def _check_laytype(cls, value: int) -> int:
        valid = {
            0, 1, 2, 3,
            10, 11, 12, 13,
            20, 21, 22, 23,
            30, 31, 32, 33,
        }

        if value not in valid:
            raise ValueError(
                f"Invalid MODFLOW LAYTYPE: {value}."
            )

        return value
   


class ModflowRechargeConfiguration(_Strict):
    """Recharge coupling from RUBEM to MODFLOW."""

    source: Literal["rubem"] = "rubem"

    # Project decision: recharge is applied to the highest active cell.
    # PCRaster MODFLOW NRCHOP = 3.
    option: Literal[3] = 3


class ModflowDisConfiguration(_Strict):
    """MODFLOW discretization/time settings used by the coupling."""

    # Current coupling conversions are explicitly defined in metres and days.
    time_unit: Literal[4] = 4
    length_unit: Literal[2] = 2

    nstp: PositiveInt = 5
    tsmult: PositiveFloat = 1.0
    steady_state: Literal[0, 1] = 0


class ModflowSolverConfiguration(_Strict):
    """PCG solver settings."""

    type: Literal["PCG"] = "PCG"

    mxiter: PositiveInt = 2000
    iter1: PositiveInt = 20
    npcond: Literal[1, 2] = 1

    hclose: PositiveFloat = 5.0
    rclose: PositiveFloat = 3.0
    relax: PositiveFloat = 1.0

    nbpol: Annotated[int, Field(ge=0)] = 2
    damp: PositiveFloat = 0.5

    fail_on_non_convergence: bool = True


class ModflowWettingConfiguration(_Strict):
    """Optional BCF wetting configuration."""

    enabled: Literal[0, 1] = 0

    # Either provide an explicit WETDRY map...
    map: str | None = None

    # ...or derive it from a boundary layer (e.g. "top") as in the legacy model.
    source_boundary_layer: Literal["top"] | PositiveLayer | None = None
    multiplier: float = -1.0

    # None means all layers that support wetting (LAYCON 1 or 3).
    layers: list[PositiveLayer] | None = None

    wetfct: PositiveFloat = 1.0
    iwetit: PositiveInt = 3
    ihdwet: Literal[0, 1] = 0


    @model_validator(mode="after")
    def _check_source(self) -> Self:

        if not self.enabled:
            return self

        has_map = self.map is not None
        has_source = self.source_boundary_layer is not None

        if has_map == has_source:
            raise ValueError(
                "wetting.enabled=1 requires exactly one of "
                "'map' or 'source_boundary_layer'."
            )

        return self


class ModflowRiverLayerConfiguration(_Strict):
    """RIV package input for one MODFLOW layer."""

    layer: PositiveLayer
    stage: str
    bottom: str
    conductance: str


class ModflowRiverConfiguration(_Strict):
    enabled: Literal[0, 1] = 0
    layers: list[ModflowRiverLayerConfiguration] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_layers(self) -> Self:
        if self.enabled and not self.layers:
            raise ValueError("river.enabled=1 requires at least one river layer.")

        numbers = [item.layer for item in self.layers]
        if len(numbers) != len(set(numbers)):
            raise ValueError("river.layers cannot contain the same layer more than once.")

        return self


class ModflowGhbConfiguration(_Strict):
    """Reserved configuration for the future GHB implementation."""

    enabled: Literal[0, 1] = 0
    layers: list[PositiveLayer] = Field(default_factory=list)
    conductance: str | None = None
    head_table: str | None = None


class ModflowWellsConfiguration(_Strict):
    """Reserved configuration for the future WEL implementation."""

    enabled: Literal[0, 1] = 0
    map: str | None = None
    table: str | None = None
    layers: list[PositiveLayer] = Field(default_factory=list)


class ModflowOutputConfiguration(_Strict):
    heads: bool = True
    river_leakage: bool = True
    storage: bool = False


class ModflowWaterTableConfiguration(_Strict):
    """How groundwater head is selected for root-depth coupling."""

    method: Literal[
        "highest_unconfined",
        "highest_active_head",
        "layer",
    ] = "highest_unconfined"

    # Used only when method == "layer".
    layer: PositiveLayer | None = None
    
    
    @model_validator(mode="after")
    def _check_layer(self) -> Self:

        if self.method == "layer":

            if self.layer is None:
                raise ValueError(
                    "water_table.method='layer' requires 'layer'."
                )

        elif self.layer is not None:

            raise ValueError(
                "'water_table.layer' can only be provided "
                "when water_table.method='layer'."
            )

        return self

   

class ModflowDynamicRootDepthConfiguration(_Strict):

    enabled: Literal[0, 1] = 0

    minimum_depth_table: str | None = None

    water_table: ModflowWaterTableConfiguration = Field(
        default_factory=ModflowWaterTableConfiguration
    )

    @model_validator(mode="after")
    def _check_minimum_depth_table(self) -> Self:

        if self.enabled and not self.minimum_depth_table:
            raise ValueError(
                "dynamic_root_depth.enabled=1 requires "
                "'minimum_depth_table'."
            )

        return self

class ModflowCouplingConfiguration(_Strict):

    baseflow_from_river_leakage: bool = True

    dynamic_root_depth: ModflowDynamicRootDepthConfiguration = Field(
        default_factory=ModflowDynamicRootDepthConfiguration
    )

class ModflowConfiguration(_Strict):
    """Complete optional MODFLOW section of the RUBEM configuration."""

    enabled: Literal[0, 1] = 0

    # Bottom elevation of PCRaster MODFLOW layer 1.
    bottom: str | None = None

    # Ordered bottom -> top. The number of layers is len(layers).
    layers: list[ModflowLayerConfiguration] = Field(default_factory=list)

    recharge: ModflowRechargeConfiguration = Field(
        default_factory=ModflowRechargeConfiguration
    )
    dis: ModflowDisConfiguration = Field(default_factory=ModflowDisConfiguration)
    solver: ModflowSolverConfiguration = Field(
        default_factory=ModflowSolverConfiguration
    )
    wetting: ModflowWettingConfiguration = Field(
        default_factory=ModflowWettingConfiguration
    )
    river: ModflowRiverConfiguration = Field(
        default_factory=ModflowRiverConfiguration
    )
    
    coupling: ModflowCouplingConfiguration = Field(
    default_factory=ModflowCouplingConfiguration
    )   

    # Accepted now so the JSON structure is stable, but the first
    # ModflowGroundwater implementation intentionally raises if they are enabled.
    ghb: ModflowGhbConfiguration = Field(default_factory=ModflowGhbConfiguration)
    wells: ModflowWellsConfiguration = Field(
        default_factory=ModflowWellsConfiguration
    )

    output: ModflowOutputConfiguration = Field(
        default_factory=ModflowOutputConfiguration
    )

    @model_validator(mode="after")
    def _check_enabled_configuration(self) -> Self:
        if not self.enabled:
            return self

        if self.bottom is None or self.bottom == "":
            raise ValueError("modflow.enabled=1 requires 'bottom'.")

        if not self.layers:
            raise ValueError("modflow.enabled=1 requires at least one layer.")
        
        if not self.coupling.baseflow_from_river_leakage:
            raise ValueError(
                "This MODFLOW-RUBEM implementation requires "
                "'baseflow_from_river_leakage=true'."
            )

        if not self.river.enabled:
            raise ValueError(
                "MODFLOW river package must be enabled because "
                "RIV leakage is used as RUBEM baseflow."
            )

        if (
            self.coupling.dynamic_root_depth.enabled
            and not self.coupling.dynamic_root_depth.minimum_depth_table
        ):
            raise ValueError(
                "Dynamic root depth requires 'minimum_depth_table'."
            )
            
        number_layers = len(self.layers)
        
        
        if self.coupling.dynamic_root_depth.enabled:

            water_table_cfg = (
                self.coupling
                .dynamic_root_depth
                .water_table
            )

            if (
                water_table_cfg.method == "layer"
                and water_table_cfg.layer > number_layers
            ):
                raise ValueError(
                    f"Water-table source layer "
                    f"{water_table_cfg.layer} is outside "
                    f"the valid range 1-{number_layers}."
                )

            if water_table_cfg.method == "highest_unconfined":

                has_water_table_capable_layer = any(
                    (layer.laytype % 10) in (1, 2, 3)
                    for layer in self.layers
                )

                if not has_water_table_capable_layer:
                    raise ValueError(
                        "water_table.method='highest_unconfined' "
                        "requires at least one MODFLOW layer "
                        "with LAYCON 1, 2 or 3. "
                        "Use 'highest_active_head' or an explicit "
                        "'layer' if a piezometric head is intended "
                        "as the coupling proxy."
                    )

        # Transient BCF storage parameters are required for every layer.
        if self.dis.steady_state == 0:

            for index, layer in enumerate(
                self.layers,
                start=1,
            ):

                laycon = layer.laytype % 10

                if laycon == 0:

                    if not layer.specific_storage:
                        raise ValueError(
                            f"MODFLOW layer {index} with "
                            "LAYCON 0 requires "
                            "'specific_storage'."
                        )

                elif laycon == 1:

                    if not layer.specific_yield:
                        raise ValueError(
                            f"MODFLOW layer {index} with "
                            "LAYCON 1 requires "
                            "'specific_yield'."
                        )

                elif laycon in (2, 3):

                    if not layer.specific_storage:
                        raise ValueError(
                            f"MODFLOW layer {index} with "
                            f"LAYCON {laycon} requires "
                            "'specific_storage'."
                        )

                    if not layer.specific_yield:
                        raise ValueError(
                            f"MODFLOW layer {index} with "
                            f"LAYCON {laycon} requires "
                            "'specific_yield'."
                        )
        # Cross-check package layer numbers against the generic layer count.
        for river_layer in self.river.layers:
            if river_layer.layer > number_layers:
                raise ValueError(
                    f"RIV layer {river_layer.layer} is outside the valid "
                    f"range 1-{number_layers}."
                )


        if self.wetting.enabled:

            if self.wetting.layers is None:

                # Automatically use every layer that supports wetting.
                wetting_layers = [
                    layer_number
                    for layer_number, layer
                    in enumerate(self.layers, start=1)
                    if (layer.laytype % 10) in (1, 3)
                ]

                if not wetting_layers:
                    raise ValueError(
                        "Wetting is enabled, but no MODFLOW layer "
                        "has LAYCON 1 or 3."
                    )

            else:

                wetting_layers = list(self.wetting.layers)

                for layer_number in wetting_layers:

                    if layer_number > number_layers:
                        raise ValueError(
                            f"Wetting layer {layer_number} is outside "
                            f"the valid range 1-{number_layers}."
                        )

                    laycon = (
                        self.layers[layer_number - 1]
                        .laytype
                        % 10
                    )

                    if laycon not in (1, 3):
                        raise ValueError(
                            f"Wetting layer {layer_number} has "
                            f"LAYCON {laycon}; wetting requires "
                            "LAYCON 1 or 3."
                        )



        source = self.wetting.source_boundary_layer
        if isinstance(source, int) and source > number_layers:
            raise ValueError(
                f"Wetting source layer {source} is outside the valid "
                f"range 1-{number_layers}."
            )

        for layer_number in self.ghb.layers:
            if layer_number > number_layers:
                raise ValueError(
                    f"GHB layer {layer_number} is outside the valid "
                    f"range 1-{number_layers}."
                )

        for layer_number in self.wells.layers:
            if layer_number > number_layers:
                raise ValueError(
                    f"WEL layer {layer_number} is outside the valid "
                    f"range 1-{number_layers}."
                )

        return self

    def resolve_paths(self, base_dir) -> Self:
        """Return a copy with relative MODFLOW file paths anchored on base_dir."""

        if base_dir is None:
            return self

        base = Path(base_dir)

        def anchor(value):
            if value is None:
                return None
            path = Path(value)
            return value if path.is_absolute() else str(base / path)

        data = self.model_dump(mode="json")

        data["bottom"] = anchor(data.get("bottom"))

        for layer in data["layers"]:
            for key in (
                "top",
                "horizontal_conductivity",
                "vertical_conductivity",
                "boundary",
                "initial_head",
                "specific_storage",
                "specific_yield",
            ):
                layer[key] = anchor(layer.get(key))

        wetting = data["wetting"]
        wetting["map"] = anchor(wetting.get("map"))

        for river_layer in data["river"]["layers"]:
            for key in ("stage", "bottom", "conductance"):
                river_layer[key] = anchor(river_layer.get(key))

        ghb = data["ghb"]
        ghb["conductance"] = anchor(ghb.get("conductance"))
        ghb["head_table"] = anchor(ghb.get("head_table"))

        wells = data["wells"]
        wells["map"] = anchor(wells.get("map"))
        wells["table"] = anchor(wells.get("table"))


        dynamic_root_depth = (
            data["coupling"]["dynamic_root_depth"]
        )

        dynamic_root_depth["minimum_depth_table"] = anchor(
            dynamic_root_depth.get("minimum_depth_table")
        )
        return type(self).model_validate(data)
