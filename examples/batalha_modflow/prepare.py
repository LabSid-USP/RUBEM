"""Prepare explicit Batalha configurations for the three MODFLOW branches.

Two profiles, both generated from the configuration the scientist delivered
(``--source``, a prototype-schema JSON) without writing into the dataset:

- ``scientist`` passes that configuration through unchanged, apart from the
  paths, the simulation window and the output directory. It reproduces the
  scientist's own runs for parity checks.
- ``answered`` applies her answers of 2026-10-13 to the questions of
  2026-10-08: ``KX`` is the vertical anisotropy (``Kh = KY``, ``Kv = KY/KX``)
  and the single-valued ``KX3``/``KY3`` maps belong to the base layer; the
  ``-888`` initial heads of the two lower layers are dry cells to fill from
  the nearest valid head and keep active; the negative heads of the top layer
  come from ``head2.map``; heads above the model top are cut at the surface;
  ``ss.map`` is the dimensionless BCF Sf1 as delivered; the river stays on
  the top layer; the GHB variant, the wetting repairs around cell (15, 231)
  and the solver are chosen by options so every choice is a documented run.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
from pathlib import Path, PurePosixPath

import numpy as np
import pcraster as pcr
from scipy.ndimage import distance_transform_edt

from rubem.file._naming import raster_series_filename, raster_series_pattern

BRANCHES = ("feat_modflow_module", "feat_calibrator_modflow", "feat_356_modflow_coupling")
SURFACES = ("botton.map", "botton2.map", "botton3.map", "top_model.map")
PHYSICAL = ("lower", "middle", "upper")  # prototype layers 1, 2, 3; PR layers 3, 2, 1
PROFILES = ("scientist", "answered")
GHB_VARIANTS = ("none", "top", "full", "split")
WETTING_FIXES = ("a1", "a2", "d")
WETTING_STRATEGIES = ("as-delivered", "below", "off")
MAX_MONTHS = 313  # length of the historical series delivered on 2026-10-29
SERIES = ("ndvi", "landuse", "etp", "prec", "kp")


def _json(path: Path, document: dict) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _replace(value, old: str, new: str):
    if isinstance(value, dict):
        return {key: _replace(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace(item, old, new) for item in value]
    return value.replace(old, new) if isinstance(value, str) else value


def _window(months: int, start: str = "01/08/2023") -> dict[str, str]:
    """The simulation window of ``months`` monthly steps from the first of ``start`` (dd/mm/yyyy)."""
    match = re.fullmatch(r"01/(\d{2})/(\d{4})", start)
    if not match:
        raise ValueError(
            f"The window start must be the first of a month as dd/mm/yyyy, got {start!r}."
        )
    month_index = int(match.group(2)) * 12 + int(match.group(1)) - 1 + months - 1
    return {"start": start, "end": f"01/{month_index % 12 + 1:02d}/{month_index // 12}"}


def series_links(available: list[int], *, first_step: int, months: int) -> dict[int, int]:
    """Which source step each window step reads, from a series whose step 1 may be years earlier.

    Window step ``k`` reads source step ``first_step + k - 1`` when that raster
    exists, otherwise the latest raster at or before it (the land-use series
    has one raster per year). Raises when nothing exists at or before the
    first step.
    """
    steps = sorted(available)
    links = {}
    for k in range(1, months + 1):
        wanted = first_step + k - 1
        candidates = [step for step in steps if step <= wanted]
        if not candidates:
            raise ValueError(f"No raster at or before source step {wanted} (window step {k}).")
        links[k] = candidates[-1]
    return links


def station_sample(samples: np.ndarray, *, row: int, col: int) -> tuple[np.ndarray, int]:
    """``samples`` with a new id on the 1-based cell ``(row, col)``; the id is the next free one."""
    if not (1 <= row <= samples.shape[0] and 1 <= col <= samples.shape[1]):
        raise ValueError(f"Cell ({row}, {col}) is outside the {samples.shape} grid.")
    if samples[row - 1, col - 1] != 0:
        raise ValueError(
            f"Cell ({row}, {col}) already carries sample id {samples[row - 1, col - 1]}."
        )
    identifier = int(samples.max()) + 1
    stamped = samples.copy()
    stamped[row - 1, col - 1] = identifier
    return stamped, identifier


def _shift_series(document: dict, generated: Path, first_step: int, months: int) -> dict:
    """Point the window's series at symbolic links into the source series, shifted by ``first_step``.

    Returns the links written, by series. Copies when the platform refuses links.
    """
    written = {}
    for series in SERIES:
        directory = Path(document["DIRECTORIES"][series])
        prefix = document["FILENAME_PREFIXES"][f"{series}_prefix"]
        pattern = raster_series_pattern(prefix)
        available = {}
        for entry in directory.iterdir():
            if pattern.fullmatch(entry.name):
                # the 8.3 name is the prefix followed by zero-padded digits split by the dot
                available[int(entry.name[len(prefix) :].replace(".", ""))] = entry
        links = series_links(list(available), first_step=first_step, months=months)
        target = generated / "series" / series
        target.mkdir(parents=True, exist_ok=True)
        for step, source_step in links.items():
            link = target / raster_series_filename(prefix, step)
            if link.exists() or link.is_symlink():
                link.unlink()
            try:
                link.symlink_to(available[source_step].resolve())
            except OSError:
                shutil.copy2(available[source_step], link)
        document["DIRECTORIES"][series] = str(target) + "/"
        written[series] = {
            "source": str(directory),
            "first_source_step": first_step,
            "links": links,
        }
    return written


def _sha256(dataset: Path, paths) -> dict[str, str]:
    """SHA-256 by POSIX path relative to the dataset, or absolute for a file outside it."""
    digests = {}
    for path in sorted(paths):
        key = path.relative_to(dataset) if dataset in path.parents else path
        digests[key.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def _source_root(clone_path: str) -> str:
    """The dataset root written in a source JSON: the clone path minus its last three parts.

    The string keeps the separators the JSON uses, so a POSIX path is rewritten
    correctly on Windows too.
    """
    parts = re.split(r"[\\/]", clone_path)
    if len(parts) < 4:
        raise ValueError(f"The clone path has no dataset root to replace: {clone_path}")
    separator = "\\" if "\\" in clone_path and "/" not in clone_path else "/"
    return separator.join(parts[:-3])


def _to_pr_schema(settings: dict) -> None:
    """Rewrite a bottom-up prototype section in place into the PR's top-down schema.

    Prototype layer ``n`` becomes layer ``count + 1 - n``: each layer's top is
    the bottom of the layer above it, the model bottom closes the last layer and
    the uppermost top becomes the model top. Keys the PR fixes internally
    (recharge option, units, solver type) or dropped are removed.
    """
    tops = [layer.pop("top") for layer in settings["layers"]]
    bottoms = [settings.pop("bottom"), *tops[:-1]]
    settings["top"] = tops[-1]
    settings["layers"].reverse()
    for layer, bottom in zip(settings["layers"], reversed(bottoms)):
        layer["bottom"] = bottom
        if layer["laytype"] % 10 == 1:
            layer.pop("specific_storage", None)
    count = len(settings["layers"])
    for package in ("river", "ghb", "drain"):
        if "layers" in settings.get(package, {}):
            settings[package]["entries"] = settings[package].pop("layers")
            for entry in settings[package]["entries"]:
                entry["layers"] = [count + 1 - entry.pop("layer")]
    wetting = settings["wetting"]
    wetting.pop("multiplier", None)
    wetting.pop("source_boundary_layer", None)
    if wetting.get("layers"):
        wetting["layers"] = [count + 1 - number for number in wetting["layers"]]
    water_table = settings.get("coupling", {}).get("dynamic_root_depth", {}).get("water_table", {})
    if "layer" in water_table:
        water_table["layer"] = count + 1 - water_table["layer"]
    for name in ("recharge", "wells"):
        settings.pop(name, None)
    for name in ("time_unit", "length_unit"):
        settings["dis"].pop(name, None)
    for name in ("type", "fail_on_non_convergence"):
        settings["solver"].pop(name, None)
    settings["coupling"].pop("baseflow_from_river_leakage", None)
    settings["output"]["root_depth"] = True


def conductivity_suffixes(orientation: str) -> dict[str, int]:
    """The ``KX``/``KY`` suffix of each physical layer.

    ``base3`` follows the scientist's rule of 2026-10-13 (the base layer has
    one conductivity class, the other two have two): the single-valued
    ``KX3``/``KY3`` go to the base. ``as-delivered`` keeps suffix ``n`` on
    prototype layer ``n``, as in the delivered JSON.
    """
    if orientation == "base3":
        return {"lower": 3, "middle": 2, "upper": 1}
    if orientation == "as-delivered":
        return {"lower": 1, "middle": 2, "upper": 3}
    raise ValueError("The conductivity orientation must be 'base3' or 'as-delivered'.")


def ghb_section(source: dict, variant: str, split_conductance: str) -> dict:
    """The prototype GHB section of a variant, from the delivered section.

    ``none`` disables the package; ``top`` keeps the delivered entries; ``full``
    repeats the delivered maps on the three layers (column conductance three
    times the map); ``split`` puts a third of the conductance on each layer so
    the column keeps the map's conductance, as the map was computed for the
    whole saturated thickness.
    """
    if variant == "none":
        return {"enabled": 0}
    if variant == "top":
        return copy.deepcopy(source)
    if variant not in ("full", "split"):
        raise ValueError(f"The GHB variant must be one of {GHB_VARIANTS}.")
    entries = source.get("layers", []) if source.get("enabled") else []
    if len(entries) != 1:
        raise ValueError(
            "The 'full' and 'split' GHB variants need a delivered section with one enabled "
            f"entry; the source has {len(entries)}."
        )
    entry = copy.deepcopy(entries[0])
    conductance = entry["conductance"] if variant == "full" else split_conductance
    return {
        "enabled": 1,
        "layers": [
            {"layer": number, "head": entry["head"], "conductance": conductance}
            for number in (1, 2, 3)
        ],
    }


def fill_nearest(head: np.ndarray, active: np.ndarray) -> tuple[np.ndarray, int]:
    """Active cells without a positive finite head take the nearest one that has it.

    Inactive cells are left without a value. Returns the filled array and the
    number of cells filled.
    """
    valid = active & np.isfinite(head) & (head > 0)
    if not valid.any():
        raise ValueError("The layer has no positive valid head to initialize from.")
    missing = active & ~valid
    nearest = distance_transform_edt(~valid, return_distances=False, return_indices=True)
    filled = head.astype(float).copy()
    filled[missing] = head[tuple(nearest[:, missing])]
    filled[~active] = np.nan
    return filled, int(missing.sum())


def answered_top_heads(
    head: np.ndarray,
    below: np.ndarray,
    bottom: np.ndarray,
    surface: np.ndarray,
    active: np.ndarray,
    *,
    repair_below_bottom: bool = True,
) -> tuple[np.ndarray, dict]:
    """The scientist's three rules for the top layer, applied to active cells only.

    Negative heads take the middle-layer head of the same cell (answer 4), or
    the layer bottom where that head is not a positive finite value; active
    non-negative heads below the layer bottom are listed for the ``a2``
    deactivation and, with ``repair_below_bottom``, repaired the same way
    (answer 5, item a1); heads above the model top are cut at the surface
    (answer 9). Inactive cells keep the delivered value. The masks come from
    the delivered heads, so the counts describe exactly what was changed.
    """
    fixed = head.astype(float).copy()
    donor = np.where(np.isfinite(below) & (below > 0), below, bottom)
    negative = active & (fixed < 0)
    under = active & ~negative & (fixed < bottom)
    fixed[negative] = np.maximum(donor[negative], bottom[negative])
    if repair_below_bottom:
        fixed[under] = np.maximum(donor[under], bottom[under])
    above = active & (fixed > surface)
    fixed[above] = surface[above]
    report = {
        "negative_replaced": int(negative.sum()),
        "negative_without_valid_donor": int((negative & ~(np.isfinite(below) & (below > 0))).sum()),
        "below_bottom_cells": [(int(r) + 1, int(c) + 1) for r, c in np.argwhere(under)],
        "below_bottom_repaired": int(under.sum()) if repair_below_bottom else 0,
        "clipped_to_surface": int(above.sum()),
    }
    return fixed, report


def _ndvi_extremes(document: dict) -> dict | None:
    """Point ``ndvi_max``/``ndvi_min`` at the NDVI series directory when the listed files are missing.

    The historical dataset of 2026-10-29 keeps both maps in ``ndvi_hist/`` while
    the delivered JSON still names ``ndvi/``; the repair is recorded.
    """
    repaired = {}
    for key in ("ndvi_max", "ndvi_min"):
        listed = Path(document["RASTERS"][key])
        if listed.is_file():
            continue
        candidate = Path(document["DIRECTORIES"]["ndvi"]) / listed.name
        if not candidate.is_file():
            raise FileNotFoundError(f"{key} is missing: {listed} (and {candidate})")
        document["RASTERS"][key] = str(candidate)
        repaired[key] = {"listed": str(listed), "used": str(candidate)}
    return repaired or None


def _prepare_scientist(
    dataset: Path,
    source: Path,
    destination: Path,
    months: int,
    *,
    start: str,
    first_step: int,
    station: tuple[int, int] | None,
) -> dict:
    """Emit the delivered configuration unchanged for the three branches.

    Only paths, the simulation window and the output directory are rewritten;
    no raster is derived. The PR refuses the no-data sentinels that stay active
    in the initial heads of the two lower layers, so its JSON runs only with
    ``--allow-blocking-problems`` (``allow_blocking_problems=True`` in the API).
    """
    destination.mkdir(parents=True, exist_ok=True)
    original = json.loads(source.read_text(encoding="utf-8"))
    base = _replace(original, _source_root(original["RASTERS"]["clone"]), str(dataset))
    base["SIM_TIME"] = _window(months, start)
    maps = dataset / "input/modflow"
    pcr.setclone(str(dataset / "input/clone/clone.map"))
    generated = destination / "derived"
    generated.mkdir(parents=True, exist_ok=True)
    ndvi_extremes = _ndvi_extremes(base)
    series = _shift_series(base, generated, first_step, months) if first_step != 1 else {}
    station_record = _station(base, generated, station) if station else None
    sentinels = {}
    for layer in original["MODFLOW"]["layers"][:2]:
        head = pcr.pcr2numpy(pcr.readmap(str(maps / Path(layer["initial_head"]).name)), np.nan)
        boundary = pcr.pcr2numpy(pcr.readmap(str(maps / Path(layer["boundary"]).name)), 0)
        sentinels[layer["name"]] = int(((boundary != 0) & (head == -888)).sum())
    manifest = {
        "profile": "scientist",
        "source_configuration": str(source),
        "changes": "paths, simulation window and output directory only; no derived raster",
        "pr_run_requirement": (
            "--allow-blocking-problems: active cells holding the -888 no-data sentinel as "
            f"initial head, by prototype layer: {sentinels}"
        ),
        "parameter_caveat": (
            "KX (the workbook's VANIS) enters as horizontal conductivity and ss.map as the "
            "unscaled BCF storage coefficient, as delivered; the scientist's answers of "
            "2026-10-13 (KX is the anisotropy) make the 'answered' profile the corrected one"
        ),
        "window": base["SIM_TIME"],
        "series": series,
        "station": station_record,
        "ndvi_extremes_repaired": ndvi_extremes,
        "source_sha256": _sha256(dataset, {source, *maps.glob("*.map")}),
    }
    return _emit(base, destination, manifest)


def _station(document: dict, generated: Path, station: tuple[int, int]) -> dict:
    """Write a samples map with a new id on the station cell and point the document at it."""
    source = Path(document["RASTERS"]["samples"])
    samples = pcr.pcr2numpy(pcr.readmap(str(source)), 0)
    row, col = station
    stamped, identifier = station_sample(samples, row=row, col=col)
    path = generated / "samples-station.map"
    pcr.report(pcr.numpy2pcr(pcr.Nominal, stamped.astype(np.int32), 0), str(path))
    document["RASTERS"]["samples"] = str(path)
    return {"source": str(source), "row": row, "col": col, "sample_id": identifier}


def _emit(base: dict, destination: Path, manifest: dict) -> dict[str, Path]:
    configs = {}
    for branch in BRANCHES:
        document = copy.deepcopy(base)
        document["DIRECTORIES"]["output"] = str(destination / "runs" / branch)
        if branch == BRANCHES[-1]:
            _to_pr_schema(document["MODFLOW"])
        path = destination / f"{branch}.json"
        _json(path, document)
        configs[branch] = path
    _json(destination / "manifest.json", manifest)
    return configs


def prepare(
    dataset: Path,
    destination: Path,
    *,
    source: Path | None = None,
    months: int = 2,
    profile: str = "answered",
    conductivity: str = "base3",
    ghb: str = "none",
    wetting_fixes: tuple[str, ...] = (),
    wetting: str = "as-delivered",
    solver: dict | None = None,
    nstp: int | None = None,
    wetfct: float | None = None,
    iwetit: int | None = None,
    start: str = "01/08/2023",
    first_step: int = 1,
    station: tuple[int, int] | None = None,
) -> dict[str, Path]:
    """Write the same physical model in the three branches' configuration formats.

    ``source`` is the scientist's prototype-schema JSON (default
    ``<dataset>/bauru_modflow.json``). The ``scientist`` profile passes it
    through (see :func:`_prepare_scientist`); the ``answered`` profile derives
    the rasters her answers require and applies the options: ``conductivity``
    orientation, ``ghb`` variant, ``wetting_fixes`` (``a1`` repair the active
    top heads below the layer bottom, ``a2`` deactivate those cells and block
    their rewetting, ``d`` IHDWET 1), ``wetting`` strategy (``as-delivered``
    keeps the delivered WETDRY map, ``below`` negates it so only the cell
    below can rewet a dry cell, ``off`` disables rewetting: cells that dry
    stay inactive), ``solver`` keys merged into the PCG block, and
    ``nstp``/``wetfct``/``iwetit`` overrides. Every choice and every altered
    cell count is recorded in ``manifest.json``. Both profiles take the window
    ``start`` and ``months``, ``first_step`` (the source step the window
    starts at, when the series begin earlier: the historical series delivered
    on 2026-10-29 start in August 2000, so August 2023 is step 277) and
    ``station`` (a 1-based ``(row, col)`` cell that receives a new sample id).
    """
    dataset, destination = dataset.resolve(), destination.resolve()
    if destination == dataset or dataset in destination.parents:
        raise ValueError("The destination must be outside the source dataset.")
    if months < 2 or months > MAX_MONTHS:
        raise ValueError(f"This dataset exercise supports 2 through {MAX_MONTHS} months.")
    if first_step < 1:
        raise ValueError("The first source step must be 1 or greater.")
    if profile not in PROFILES:
        raise ValueError(f"The profile must be one of {PROFILES}.")
    source = (dataset / "bauru_modflow.json" if source is None else Path(source)).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"The scientist's configuration is missing: {source}")
    if profile == "scientist":
        return _prepare_scientist(
            dataset,
            source,
            destination,
            months,
            start=start,
            first_step=first_step,
            station=station,
        )
    suffixes = conductivity_suffixes(conductivity)
    if ghb not in GHB_VARIANTS:
        raise ValueError(f"The GHB variant must be one of {GHB_VARIANTS}.")
    fixes = tuple(wetting_fixes)
    if any(fix not in WETTING_FIXES for fix in fixes):
        raise ValueError(f"The wetting fixes must be among {WETTING_FIXES}.")
    if wetting not in WETTING_STRATEGIES:
        raise ValueError(f"The wetting strategy must be one of {WETTING_STRATEGIES}.")
    maps = dataset / "input/modflow"
    generated = destination / "derived"
    generated.mkdir(parents=True, exist_ok=True)
    pcr.setclone(str(dataset / "input/clone/clone.map"))

    def read(name: str) -> np.ndarray:
        return pcr.pcr2numpy(pcr.scalar(pcr.readmap(str(maps / name))), np.nan)

    def write(name: str, values: np.ndarray) -> str:
        path = generated / name
        pcr.report(pcr.numpy2pcr(pcr.Scalar, values.astype(np.float32), np.nan), str(path))
        return str(path)

    original = json.loads(source.read_text(encoding="utf-8"))
    base = _replace(original, _source_root(original["RASTERS"]["clone"]), str(dataset))
    base["SIM_TIME"] = _window(months, start)
    ndvi_extremes = _ndvi_extremes(base)
    series = _shift_series(base, generated, first_step, months) if first_step != 1 else {}
    station_record = _station(base, generated, station) if station else None
    mf = base["MODFLOW"]
    if len(mf["layers"]) != 3:
        raise ValueError("The Batalha source configuration must have three layers.")
    surface = [read(name) for name in SURFACES]
    boundaries = [
        pcr.pcr2numpy(pcr.readmap(str(maps / Path(layer["boundary"]).name)), 0) != 0
        for layer in mf["layers"]
    ]
    for active, bottom, top in zip(boundaries, surface, surface[1:]):
        if not np.all(np.isfinite(bottom[active]) & (top[active] > bottom[active])):
            raise ValueError("The expected Batalha surfaces are not stacked on the active domain.")
    heads = [read(f"head{index + 1}.map") for index in range(3)]
    manifest = {
        "profile": "answered",
        "source_configuration": str(source),
        "answers": {
            "1_conductivity_suffixes": suffixes,
            "2_anisotropy": "KX is Kh/Kv: Kh = KY, Kv = KY/KX [m/day]",
            "3_storage": "ss.map is the dimensionless BCF Sf1, unscaled; the top layer uses sy.map",
            "4_lower_heads": "active cells without a positive head take the nearest valid head",
            "4_top_negative_heads": "replaced by head2.map at the same cell",
            "5_wetting_fixes": list(fixes),
            "6_wetting_strategy": wetting,
            "8_river": "delivered entries, top layer",
            "8_11_ghb": ghb,
            "9_top_heads_above_surface": "cut at top_model.map, the DIS top",
        },
        "window": base["SIM_TIME"],
        "series": series,
        "station": station_record,
        "ndvi_extremes_repaired": ndvi_extremes,
        "layers": [],
        "source_sha256": _sha256(
            dataset, {source, dataset / "input/clone/clone.map", *maps.glob("*.map")}
        ),
    }
    mf["bottom"] = str(maps / SURFACES[0])
    filled = {}
    for index, (name, layer) in enumerate(zip(PHYSICAL, mf["layers"])):
        active, bottom, top = boundaries[index], surface[index], surface[index + 1]
        suffix = suffixes[name]
        horizontal, anisotropy = read(f"KY{suffix}.map"), read(f"KX{suffix}.map")
        if not np.all((horizontal[active] > 0) & (anisotropy[active] > 0)):
            raise ValueError(f"Suffix {suffix} has nonpositive conductivity or anisotropy.")
        record = {
            "name": name,
            "prototype_layer": index + 1,
            "pr_layer": 3 - index,
            "head_suffix": index + 1,
            "conductivity_suffix": suffix,
            "conductivity_classes": int(np.unique(horizontal[active]).size),
            "active_cells": int(active.sum()),
        }
        if index < 2:
            seeded, count = fill_nearest(heads[index], active)
            record["sentinels_in_active_cells"] = int((active & (heads[index] == -888)).sum())
            record["heads_filled"] = count
        else:
            seeded, report = answered_top_heads(
                heads[2], filled["middle"], bottom, top, active, repair_below_bottom="a1" in fixes
            )
            record.update(report)
            if "a2" in fixes:
                deactivate = np.zeros(active.shape, dtype=bool)
                for row, col in report["below_bottom_cells"]:
                    deactivate[row - 1, col - 1] = True
                boundary = pcr.pcr2numpy(
                    pcr.readmap(str(maps / Path(layer["boundary"]).name)), np.nan
                )
                boundary[deactivate] = 0
                layer["boundary"] = write("boundary-upper.map", boundary)
                wetdry = read(Path(mf["wetting"]["map"]).name)
                wetdry[deactivate] = 0
                mf["wetting"]["map"] = write("wetting-upper.map", wetdry)
                record["deactivated_cells"] = report["below_bottom_cells"]
        filled[name] = seeded
        record["initialized_heads_below_bottom"] = int((active & (seeded < bottom)).sum())
        layer.update(
            name=name,
            top=str(maps / SURFACES[index + 1]),
            horizontal_conductivity=str(maps / f"KY{suffix}.map"),
            vertical_conductivity=write(f"kv-{name}.map", horizontal / anisotropy),
            initial_head=write(f"head-{name}.map", seeded),
            compute_conductivity=True,
        )
        manifest["layers"].append(record)
    third = None
    if ghb == "split":
        entries = mf["ghb"].get("layers", []) if mf["ghb"].get("enabled") else []
        if len(entries) != 1:
            raise ValueError("The 'split' GHB variant needs a delivered section with one entry.")
        conductance = read(PurePosixPath(entries[0]["conductance"].replace("\\", "/")).name)
        third = write(
            "ghb-conductance-third.map",
            np.where(np.isfinite(conductance), conductance / 3, np.nan),
        )
    mf["ghb"] = ghb_section(mf["ghb"], ghb, third)
    if wetting == "off":
        mf["wetting"]["enabled"] = 0
    elif wetting == "below":
        wetdry = (
            read(Path(mf["wetting"]["map"]).name)
            if not str(mf["wetting"]["map"]).startswith(str(generated))
            else pcr.pcr2numpy(pcr.scalar(pcr.readmap(mf["wetting"]["map"])), np.nan)
        )
        mf["wetting"]["map"] = write("wetting-below.map", -np.abs(wetdry))
    if "d" in fixes:
        mf["wetting"]["ihdwet"] = 1
    if wetfct is not None:
        mf["wetting"]["wetfct"] = wetfct
    if iwetit is not None:
        mf["wetting"]["iwetit"] = iwetit
    if nstp is not None:
        mf["dis"]["nstp"] = nstp
    if solver:
        mf["solver"].update(solver)
    manifest["wetting"] = {
        key: mf["wetting"][key] for key in ("enabled", "wetfct", "iwetit", "ihdwet")
    }
    manifest["solver"] = {
        key: mf["solver"].get(key) for key in ("mxiter", "iter1", "hclose", "rclose", "damp")
    }
    manifest["nstp"] = mf["dis"]["nstp"]
    return _emit(base, destination, manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--source", type=Path, help="prototype-schema JSON (default <dataset>/bauru_modflow.json)"
    )
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument("--profile", choices=PROFILES, default="answered")
    parser.add_argument("--conductivity", choices=("base3", "as-delivered"), default="base3")
    parser.add_argument("--ghb", choices=GHB_VARIANTS, default="none")
    parser.add_argument("--wetting-fixes", default="", help="comma-separated subset of a1,a2,d")
    parser.add_argument("--wetting", choices=WETTING_STRATEGIES, default="as-delivered")
    parser.add_argument("--hclose", type=float)
    parser.add_argument("--rclose", type=float)
    parser.add_argument("--mxiter", type=int)
    parser.add_argument("--iter1", type=int)
    parser.add_argument("--damp", type=float)
    parser.add_argument("--nstp", type=int)
    parser.add_argument("--wetfct", type=float)
    parser.add_argument("--iwetit", type=int)
    parser.add_argument(
        "--start", default="01/08/2023", help="first month of the window, dd/mm/yyyy"
    )
    parser.add_argument(
        "--first-step", type=int, default=1, help="source series step of the window's first month"
    )
    parser.add_argument("--station", help="ROW,COL (1-based) that receives a new sample id")
    args = parser.parse_args()
    station = tuple(int(value) for value in args.station.split(",")) if args.station else None
    overrides = {
        key: getattr(args, key)
        for key in ("hclose", "rclose", "mxiter", "iter1", "damp")
        if getattr(args, key) is not None
    }
    for branch, path in prepare(
        args.dataset,
        args.destination,
        source=args.source,
        months=args.months,
        profile=args.profile,
        conductivity=args.conductivity,
        ghb=args.ghb,
        wetting_fixes=tuple(fix for fix in args.wetting_fixes.split(",") if fix),
        wetting=args.wetting,
        solver=overrides,
        nstp=args.nstp,
        wetfct=args.wetfct,
        iwetit=args.iwetit,
        start=args.start,
        first_step=args.first_step,
        station=station,
    ).items():
        print(f"{branch}: {path}")
