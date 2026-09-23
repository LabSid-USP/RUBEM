"""The optional MODFLOW section of the configuration (legacy ``MODFLOW``, format 1.0 ``modflow``).

The same models are nested in both formats and are strict in both: an
unknown key is refused (a key that no longer exists would otherwise silently
disable a package). Layers are listed from the top down and numbered like
MODFLOW (layer 1 is the top layer); the PCRaster MODFLOW extension numbers
them from the bottom up, and :meth:`ModflowSettings.pcraster_layer` converts.
Lengths are metres and times days, the units of the coupling.

Cross-field rules are checked only when the section is enabled: a disabled
section is ignored by the run, so it may stay incomplete.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .._paths import PathInput, as_path

MapPath = Annotated[str, Field(min_length=1)]
LayerNumber = Annotated[int, Field(ge=1)]
LayerList = Annotated[list[LayerNumber], Field(min_length=1)]
PositiveInt = Annotated[int, Field(ge=1)]
PositiveFloat = Annotated[float, Field(gt=0, allow_inf_nan=False)]
# ``strict`` keeps a quoted number on the path branch of a ``path | number`` union.
PositiveNumber = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
NonNegativeNumber = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
Fraction = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]

LAYTYPES = frozenset(tens + laycon for tens in (0, 10, 20, 30) for laycon in (0, 1, 2, 3))
"""BCF layer types: the tens digit selects the transmissivity averaging, the
units digit (LAYCON) the layer type: 0 confined, 1 unconfined (top layer only),
2 and 3 convertible."""

WETTING_LAYCONS = (1, 3)
"""LAYCON values for which BCF reads a WETDRY array."""

MAX_LAYERS = 9
"""Most layers a section may list: the per-layer output prefixes (``mfh<n>``)
are followed by the zero-padded step, so ``mfh1`` and ``mfh10`` would give the
same file name."""


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ConductivityLookup(_Strict):
    """A nominal class map and a PCRaster lookup table giving the conductivity per class.

    :param map: Nominal raster of the conductivity classes.
    :param table: PCRaster lookup table, one ``class value`` row per class [m/day].
    """

    map: MapPath
    table: MapPath


class ModflowLayer(_Strict):
    """One MODFLOW layer: geometry, BAS domain and BCF properties.

    :param name: Unique name used in logs and outputs.
    :param bottom: Raster of the bottom elevation of the layer [m].
    :param initial_head: Raster of the starting head [m].
    :param boundary: BAS IBOUND raster: -1 constant head, 0 inactive, 1 active.
    :param laytype: BCF layer type (tens digit: averaging; units digit: LAYCON).
    :param horizontal_conductivity: Raster, number or class lookup [m/day].
    :param vertical_conductivity: Raster or number [m/day].
    :param specific_storage: Raster or number, the confined storage coefficient
        (BCF Sf1) [-]; needed in transient runs by LAYCON 0, 2 and 3.
    :param specific_yield: Raster or fraction (BCF Sf2) [-]; needed in
        transient runs by LAYCON 1, 2 and 3.
    :param compute_conductivity: Whether the extension computes the vertical
        conductance from the conductivities.
    """

    name: Annotated[str, Field(min_length=1)]
    bottom: MapPath
    initial_head: MapPath
    boundary: MapPath
    laytype: int
    horizontal_conductivity: MapPath | PositiveNumber | ConductivityLookup
    vertical_conductivity: MapPath | PositiveNumber
    specific_storage: MapPath | NonNegativeNumber | None = None
    specific_yield: MapPath | Fraction | None = None
    compute_conductivity: bool = True

    @field_validator("laytype")
    @classmethod
    def _known_laytype(cls, value: int) -> int:
        if value not in LAYTYPES:
            raise ValueError(
                f"invalid MODFLOW LAYTYPE {value}: expected one of {sorted(LAYTYPES)}."
            )
        return value

    @property
    def laycon(self) -> int:
        """The LAYCON digit of :attr:`laytype`."""
        return self.laytype % 10


class Dis(_Strict):
    """Time discretization of each stress period (one RUBEM step).

    :param nstp: Number of time steps per stress period. One by default: the
        extension reads the heads of a period only when its last time step
        converged, so a solver failure at an earlier time step ends the whole
        process instead of raising.
    :param tsmult: Time step multiplier.
    :param steady_state: Whether every stress period is steady state.
    """

    nstp: PositiveInt = 1
    tsmult: PositiveFloat = 1.0
    steady_state: bool = False


class Solver(_Strict):
    """PCG solver settings (the scientist's defaults).

    :param hclose: Head change criterion [m].
    :param rclose: Residual criterion [m3/day].
    """

    mxiter: PositiveInt = 2000
    iter1: PositiveInt = 20
    npcond: Literal[1, 2] = 1
    hclose: PositiveFloat = 5.0
    rclose: PositiveFloat = 3.0
    relax: PositiveFloat = 1.0
    nbpol: Annotated[int, Field(ge=0)] = 2
    damp: PositiveFloat = 0.5


class Wetting(_Strict):
    """BCF rewetting of dry cells.

    :param map: WETDRY raster [m].
    :param layers: Layers the map applies to; ``None`` means every layer
        whose LAYCON is 1 or 3.
    """

    enabled: bool = False
    map: MapPath | None = None
    layers: list[LayerNumber] | None = None
    wetfct: PositiveFloat = 1.0
    iwetit: PositiveInt = 3
    ihdwet: Literal[0, 1] = 0


class RiverEntry(_Strict):
    """RIV cells of one or more layers.

    :param stage: Raster of the river stage [m].
    :param bottom: Raster of the riverbed bottom [m].
    :param conductance: Raster or number [m2/day]; a number needs ``mask``.
    :param mask: Raster whose positive cells are river cells.
    """

    layers: LayerList
    stage: MapPath
    bottom: MapPath
    conductance: MapPath | PositiveNumber
    mask: MapPath | None = None


class GhbEntry(_Strict):
    """GHB cells of one or more layers (the same maps in every listed layer).

    :param head: Raster of the boundary head [m].
    :param conductance: Raster of the boundary conductance [m2/day].
    """

    layers: LayerList
    head: MapPath
    conductance: MapPath


class DrainEntry(_Strict):
    """DRN cells of one or more layers.

    :param elevation: Raster of the drain elevation [m].
    :param conductance: Raster of the drain conductance [m2/day].
    """

    layers: LayerList
    elevation: MapPath
    conductance: MapPath


class River(_Strict):
    enabled: bool = False
    entries: list[RiverEntry] = []


class Ghb(_Strict):
    enabled: bool = False
    entries: list[GhbEntry] = []


class Drain(_Strict):
    enabled: bool = False
    entries: list[DrainEntry] = []


class WaterTable(_Strict):
    """How the water-table head of the root-depth coupling is chosen.

    :param layer: The layer read when ``method`` is ``"layer"``.
    """

    method: Literal["highest_unconfined", "highest_active_head", "layer"] = "highest_unconfined"
    layer: LayerNumber | None = None


class DynamicRootDepth(_Strict):
    """Restriction of the vegetation root depth by the previous step's water table.

    :param minimum_depth_table: Lookup table of the minimum root depth per soil class.
    """

    enabled: bool = False
    minimum_depth_table: MapPath | None = None
    water_table: WaterTable = WaterTable()


class Coupling(_Strict):
    dynamic_root_depth: DynamicRootDepth = DynamicRootDepth()


class Output(_Strict):
    """MODFLOW diagnostics written as rasters."""

    heads: bool = True
    river_leakage: bool = True
    storage: bool = False
    drain_flow: bool = False
    root_depth: bool = False


class ModflowSettings(_Strict):
    """The MODFLOW section.

    :param enabled: Whether the run is coupled to MODFLOW.
    :param top: Raster of the model top, the top of layer 1 [m].
    :param layers: The layers from the top down.
    """

    enabled: bool = False
    top: MapPath | None = None
    layers: list[ModflowLayer] = []
    dis: Dis = Dis()
    solver: Solver = Solver()
    wetting: Wetting = Wetting()
    river: River = River()
    ghb: Ghb = Ghb()
    drain: Drain = Drain()
    coupling: Coupling = Coupling()
    output: Output = Output()

    @model_validator(mode="after")
    def _check_enabled(self) -> Self:
        if not self.enabled:
            return self
        errors = [
            *self._structure_errors(),
            *self._package_errors(),
            *self._storage_errors(),
            *self._wetting_errors(),
            *self._coupling_errors(),
        ]
        if errors:
            raise ValueError("MODFLOW section: " + " ".join(errors))
        return self

    def _structure_errors(self) -> list[str]:
        errors = []
        if not self.top:
            errors.append("an enabled section needs the model 'top'.")
        if not self.layers:
            errors.append("an enabled section needs at least one layer.")
        if len(self.layers) > MAX_LAYERS:
            errors.append(
                f"{len(self.layers)} layers are listed; at most {MAX_LAYERS} layers are "
                "supported, because the per-layer outputs mfh<n>, mfst<n> and mfdrn<n> of "
                "layer 1 and layer 10 would share file names."
            )
        names = [item.name for item in self.layers]
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            errors.append(f"layer names must be unique, repeated: {repeated}.")
        for number, item in enumerate(self.layers[1:], start=2):
            if item.laycon == 1:
                errors.append(
                    f"layer {number} has LAYCON 1, which is valid only for the top layer (layer 1)."
                )
        if not self.river.enabled:
            errors.append(
                "river.enabled must be true: the RIV leakage is the baseflow of the coupled run."
            )
        return errors

    def _range_error(self, what: str, number: int) -> str | None:
        count = len(self.layers)
        if 1 <= number <= count:
            return None
        return f"{what} refers to layer {number}, outside the layers 1-{count}."

    def _package_errors(self) -> list[str]:
        errors = []
        for name in ("river", "ghb", "drain"):
            package = getattr(self, name)
            if not package.enabled:
                continue
            if not package.entries:
                errors.append(f"{name}.enabled is true but {name}.entries is empty.")
            seen = set()
            for index, entry in enumerate(package.entries, start=1):
                for number in entry.layers:
                    error = self._range_error(f"{name} entry {index}", number)
                    if error:
                        errors.append(error)
                    if number in seen:
                        errors.append(f"{name} lists layer {number} more than once.")
                    seen.add(number)
        if self.river.enabled:
            for index, entry in enumerate(self.river.entries, start=1):
                if not isinstance(entry.conductance, str) and entry.mask is None:
                    errors.append(
                        f"river entry {index} has a numeric conductance and needs a 'mask' "
                        "raster selecting the river cells."
                    )
        return errors

    def _storage_errors(self) -> list[str]:
        if self.dis.steady_state:
            # The extension ends the process when asked for storage in a steady run.
            if self.output.storage:
                return [
                    "output.storage needs a transient run (dis.steady_state false): "
                    "a steady-state period has no storage flow."
                ]
            return []
        required = {
            0: ("specific_storage",),
            1: ("specific_yield",),
            2: ("specific_storage", "specific_yield"),
            3: ("specific_storage", "specific_yield"),
        }
        return [
            f"layer {number} ({item.name}) has LAYCON {item.laycon} and a transient run "
            f"needs its '{key}'."
            for number, item in enumerate(self.layers, start=1)
            for key in required[item.laycon]
            if getattr(item, key) is None
        ]

    def _wetting_errors(self) -> list[str]:
        wetting = self.wetting
        if not wetting.enabled:
            return []
        errors = []
        if wetting.map is None:
            errors.append("wetting is enabled but wetting.map (the WETDRY raster) is not given.")
        if wetting.layers is None:
            if not self.wetting_layers():
                errors.append("wetting is enabled but no layer has LAYCON 1 or 3.")
            return errors
        seen = set()
        for number in wetting.layers:
            if number in seen:
                errors.append(f"wetting lists layer {number} more than once.")
            seen.add(number)
            error = self._range_error("wetting", number)
            if error:
                errors.append(error)
                continue
            laycon = self.layers[number - 1].laycon
            if laycon not in WETTING_LAYCONS:
                errors.append(
                    f"wetting layer {number} has LAYCON {laycon}; BCF reads WETDRY only for "
                    "LAYCON 1 or 3."
                )
        return errors

    def _coupling_errors(self) -> list[str]:
        root_depth = self.coupling.dynamic_root_depth
        if not root_depth.enabled:
            return []
        errors = []
        if root_depth.minimum_depth_table is None:
            errors.append("dynamic_root_depth is enabled but minimum_depth_table is not given.")
        water_table = root_depth.water_table
        if water_table.method == "layer":
            if water_table.layer is None:
                errors.append("water_table.method 'layer' needs water_table.layer.")
            else:
                error = self._range_error("water_table", water_table.layer)
                if error:
                    errors.append(error)
        elif water_table.layer is not None:
            errors.append("water_table.layer is only given with water_table.method 'layer'.")
        if water_table.method == "highest_unconfined" and not any(
            item.laycon in (1, 2, 3) for item in self.layers
        ):
            errors.append(
                "water_table.method 'highest_unconfined' needs a layer with LAYCON 1, 2 or 3; "
                "use 'highest_active_head' or 'layer' to read a confined head."
            )
        return errors

    # ----- layer numbering ---------------------------------------------------

    def pcraster_layer(self, number: int) -> int:
        """The PCRaster MODFLOW number (bottom up) of user layer ``number`` (top down).

        :param number: Layer number as configured, 1 being the top layer.
        :type number: int
        :returns: The number the extension's ``set*``/``get*`` calls take.
        :rtype: int
        :raises ValueError: If ``number`` is not a configured layer.
        """
        self._check_number(number)
        return len(self.layers) - number + 1

    def user_layer(self, pcraster_number: int) -> int:
        """The configured number (top down) of PCRaster layer ``pcraster_number`` (bottom up).

        :param pcraster_number: Layer number of the extension, 1 being the bottom layer.
        :type pcraster_number: int
        :rtype: int
        :raises ValueError: If ``pcraster_number`` is not a layer of the model.
        """
        self._check_number(pcraster_number)
        return len(self.layers) - pcraster_number + 1

    def _check_number(self, number: int) -> None:
        if not 1 <= number <= len(self.layers):
            raise ValueError(f"layer {number} is outside the layers 1-{len(self.layers)}.")

    def wetting_layers(self) -> list[int]:
        """The user layers (top down) the WETDRY map applies to; empty when wetting is off.

        :rtype: list[int]
        """
        if not self.wetting.enabled:
            return []
        if self.wetting.layers is not None:
            return list(self.wetting.layers)
        return [
            number
            for number, item in enumerate(self.layers, start=1)
            if item.laycon in WETTING_LAYCONS
        ]

    # ----- paths -------------------------------------------------------------

    def resolve_paths(self, base_dir: PathInput | None) -> Self:
        """Return a copy whose relative paths are anchored on ``base_dir``.

        Absolute paths and numbers are kept; with ``base_dir=None`` the
        settings are returned unchanged.
        """
        if base_dir is None:
            return self
        base = as_path(base_dir)

        def anchor(value: str) -> str:
            return value if Path(value).is_absolute() else str(base / value)

        return type(self).model_validate(transform_paths(self.model_dump(mode="json"), anchor))


_LAYER_PATHS = ("bottom", "initial_head", "boundary")
_LAYER_PATHS_OR_NUMBERS = (
    "horizontal_conductivity",
    "vertical_conductivity",
    "specific_storage",
    "specific_yield",
)
_ENTRY_PATHS = {
    "river": ("stage", "bottom", "conductance", "mask"),
    "ghb": ("head", "conductance"),
    "drain": ("elevation", "conductance"),
}


def transform_paths(section: dict, transform: Callable[[str], str]) -> dict:
    """Apply ``transform`` to every file path of a MODFLOW section document.

    The document is the JSON form of :class:`ModflowSettings` (possibly with
    keys left out, as ``exclude_none`` writes it); numbers standing for a
    raster are kept, and so are the keys that are not paths.

    :param section: The section as a dictionary; changed in place.
    :type section: dict
    :param transform: Function applied to each path string.
    :type transform: Callable[[str], str]
    :returns: ``section``.
    :rtype: dict
    """

    def apply(mapping: dict, keys) -> None:
        for key in keys:
            value = mapping.get(key)
            if isinstance(value, str):
                mapping[key] = transform(value)

    apply(section, ("top",))
    for layer in section.get("layers", []):
        apply(layer, _LAYER_PATHS + _LAYER_PATHS_OR_NUMBERS)
        lookup = layer.get("horizontal_conductivity")
        if isinstance(lookup, dict):
            apply(lookup, ("map", "table"))
    apply(section.get("wetting", {}), ("map",))
    for package, keys in _ENTRY_PATHS.items():
        for entry in section.get(package, {}).get("entries", []):
            apply(entry, keys)
    root_depth = section.get("coupling", {}).get("dynamic_root_depth", {})
    apply(root_depth, ("minimum_depth_table",))
    return section
