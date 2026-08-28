"""Pydantic configuration models for the optional PCRaster MODFLOW module."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    laytype: Annotated[int, Field(ge=0, le=3)] = 0
    compute_conductivity: bool = True


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
    npcond: Annotated[int, Field(ge=1)] = 1

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

    # None means all model layers.
    layers: list[PositiveLayer] | None = None

    wetfct: PositiveFloat = 1.0
    iwetit: PositiveInt = 3
    ihdwet: Annotated[int, Field(ge=0)] = 0

    @model_validator(mode="after")
    def _check_source(self) -> Self:
        if self.enabled and self.map is None and self.source_boundary_layer is None:
            raise ValueError(
                "wetting.enabled=1 requires either 'map' or "
                "'source_boundary_layer'."
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

        number_layers = len(self.layers)

        # Transient BCF storage parameters are required for every layer.
        if self.dis.steady_state == 0:
            for index, layer in enumerate(self.layers, start=1):
                if not layer.specific_storage:
                    raise ValueError(
                        f"MODFLOW layer {index} requires 'specific_storage' "
                        "for a transient simulation."
                    )
                if not layer.specific_yield:
                    raise ValueError(
                        f"MODFLOW layer {index} requires 'specific_yield' "
                        "for a transient simulation."
                    )

        # Cross-check package layer numbers against the generic layer count.
        for river_layer in self.river.layers:
            if river_layer.layer > number_layers:
                raise ValueError(
                    f"RIV layer {river_layer.layer} is outside the valid "
                    f"range 1-{number_layers}."
                )

        if self.wetting.layers is not None:
            for layer_number in self.wetting.layers:
                if layer_number > number_layers:
                    raise ValueError(
                        f"Wetting layer {layer_number} is outside the valid "
                        f"range 1-{number_layers}."
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

        return type(self).model_validate(data)
