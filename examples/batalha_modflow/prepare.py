"""Prepare explicit Batalha sensitivity inputs without changing the source data."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pcraster as pcr
from scipy.ndimage import distance_transform_edt

BRANCHES = ("feat_modflow_module", "feat_calibrator_modflow", "feat_356_modflow_coupling")
SURFACES = ("botton.map", "botton2.map", "botton3.map", "top_model.map")


def _json(path: Path, document: dict) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _replace(value, old: str, new: str):
    if isinstance(value, dict):
        return {key: _replace(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace(item, old, new) for item in value]
    return value.replace(old, new) if isinstance(value, str) else value


def _window(months: int) -> dict[str, str]:
    month_index = 2023 * 12 + 7 + months - 1
    return {"start": "01/08/2023", "end": f"01/{month_index % 12 + 1:02d}/{month_index // 12}"}


def _sha256(dataset: Path, paths) -> dict[str, str]:
    return {
        str(path.relative_to(dataset)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }


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
    for name in ("recharge", "wells"):
        settings.pop(name, None)
    for name in ("time_unit", "length_unit"):
        settings["dis"].pop(name, None)
    for name in ("type", "fail_on_non_convergence"):
        settings["solver"].pop(name, None)
    settings["coupling"].pop("baseflow_from_river_leakage", None)
    settings["output"]["root_depth"] = True


def _prepare_scientist(dataset: Path, destination: Path, months: int) -> dict[str, Path]:
    """Emit the configuration delivered with the dataset on 2026-10-08, unchanged.

    Only paths, the simulation window and the output directory are rewritten;
    no raster is derived. The PR refuses the 277 + 18 no-data sentinels that stay
    active in the initial heads of the two lower layers, so its JSON runs only
    with ``--allow-blocking-problems`` (``allow_blocking_problems=True`` in the
    API). The manifest records the hashes and the closure caveat.
    """
    source = dataset / "bauru_modflow(patched).json"
    if not source.is_file():
        raise FileNotFoundError(f"The scientist's configuration is missing: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    original = json.loads(source.read_text(encoding="utf-8"))
    old_root = str(Path(original["RASTERS"]["clone"]).parents[2])
    base = _replace(original, old_root, str(dataset))
    base["SIM_TIME"] = _window(months)
    maps = dataset / "input/modflow"
    manifest = {
        "profile": "scientist",
        "source_configuration": str(source),
        "changes": "paths, simulation window and output directory only; no derived raster",
        "pr_run_requirement": (
            "--allow-blocking-problems: 277 active cells of head2.map and 18 of head1.map "
            "hold the -888 no-data sentinel as initial head"
        ),
        "closure_caveat": (
            "HCLOSE 20 m and RCLOSE 10 m3/day accept the quiet phase of a wet/dry limit "
            "cycle at the top-layer cell (row 15, column 231) left active below its bottom; "
            "1/1, 0.1/0.1 and 0.01/0.01 fail in the first substep on every branch"
        ),
        "parameter_caveat": (
            "KX (4.813-5.192, the workbook's VANIS) enters as horizontal conductivity and "
            "ss.map (1e-6) as the unscaled BCF storage coefficient, as delivered"
        ),
        "source_sha256": _sha256(dataset, {source, *maps.glob("*.map")}),
    }
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
    months: int = 2,
    profile: str = "reconstructed",
    wetting: str = "below",
    mxiter: int = 2000,
    wetfct: float = 1.0,
    ihdwet: int = 0,
    head_donors: str = "positive",
    wetdry_threshold: float = 1.0,
) -> dict[str, Path]:
    """Write the same physical model in the three branches' configuration formats.

    The ``reconstructed`` profile derives heads, conductivities, storage and
    river layers under the declared policies; derived heads are numerical
    initialization estimates, not observations. The ``scientist`` profile
    passes the configuration delivered with the dataset through unchanged (see
    :func:`_prepare_scientist`); the wetting and solver options apply only to
    the former. The assumptions and each altered cell count are recorded in
    manifest.json.
    """
    dataset, destination = dataset.resolve(), destination.resolve()
    if destination == dataset or dataset in destination.parents:
        raise ValueError("The destination must be outside the source dataset.")
    if months < 2 or months > 9:
        raise ValueError("This dataset exercise supports 2 through 9 months.")
    if profile not in ("reconstructed", "scientist"):
        raise ValueError("The profile must be 'reconstructed' or 'scientist'.")
    if profile == "scientist":
        return _prepare_scientist(dataset, destination, months)
    if not np.isfinite(wetdry_threshold) or wetdry_threshold <= 0:
        raise ValueError("The wetting threshold must be positive and finite.")
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

    boundary = read("bound.map")
    active = np.isfinite(boundary) & (boundary != 0)
    surface = [read(name) for name in SURFACES]
    for bottom, top in zip(surface, surface[1:]):
        if not np.all(np.isfinite(bottom[active]) & (top[active] > bottom[active])):
            raise ValueError("The expected Batalha surfaces are not stacked on the active domain.")
    manifest = {
        "source_dataset": str(dataset),
        "active_cells": int(active.sum()),
        "head_initialization": "nearest positive finite active head in the same layer; no clamping",
        "head_donors": head_donors,
        "conductivity_assumption": "KX is Kh/Kv; Kh=KY and Kv=KY/KX, in metres/day",
        "storage_assumption": "ss.map is Ss[1/m]; BCF Sf1=Ss*layer thickness for LAYCON2",
        "river_policy": "assign by bed elevation; exclude beds outside the complete model column",
        "ghb_policy": "original entries on the uppermost layer only",
        "wetting": wetting,
        "wetdry_threshold_m": wetdry_threshold,
        "layers": [],
        "source_sha256": {},
    }
    manifest["source_sha256"] = _sha256(
        dataset,
        {dataset / "bauru_modflow.json", dataset / "input/clone/clone.map", *maps.glob("*.map")},
    )

    original = json.loads((dataset / "bauru_modflow.json").read_text(encoding="utf-8"))
    old_root = str(Path(original["RASTERS"]["clone"]).parents[2])
    base = _replace(original, old_root, str(dataset))
    base["SIM_TIME"] = _window(months)
    mf = base["MODFLOW"]
    mf["bottom"] = str(maps / SURFACES[0])
    ss = read("ss.map")
    for index, layer in enumerate(mf["layers"]):
        suffix = index + 1
        bottom, top = surface[index : index + 2]
        head = read(f"head{suffix}.map")
        valid = active & np.isfinite(head) & (head > 0)
        if not valid.any():
            raise ValueError(f"Layer {suffix} has no positive valid head to initialize from.")
        missing = active & ~valid
        donors = valid & (head >= bottom) if head_donors == "wet" else valid
        if not donors.any():
            raise ValueError(f"Layer {suffix} has no head matching the donor policy.")
        nearest = distance_transform_edt(~donors, return_distances=False, return_indices=True)
        seeded = head.copy()
        seeded[missing] = head[tuple(nearest[:, missing])]
        seeded[~active] = np.nan
        kh, anisotropy = read(f"KY{suffix}.map"), read(f"KX{suffix}.map")
        if not np.all((kh[active] > 0) & (anisotropy[active] > 0)):
            raise ValueError(f"Layer {suffix} has nonpositive conductivity or anisotropy.")
        layer.update(
            name=("lower", "middle", "upper")[index],
            top=str(maps / SURFACES[index + 1]),
            horizontal_conductivity=str(maps / f"KY{suffix}.map"),
            vertical_conductivity=write(f"kv{suffix}.map", kh / anisotropy),
            initial_head=write(f"head{suffix}-initialized.map", seeded),
            specific_storage=write(f"storage{suffix}.map", ss * (top - bottom)),
            compute_conductivity=True,
        )
        if index == 2:
            layer.pop("specific_storage", None)
        manifest["layers"].append(
            {
                "suffix": suffix,
                "original_sentinels": int((active & (head == -888)).sum()),
                "initialized_cells": int(missing.sum()),
                "positive_heads_below_bottom_retained": int((valid & (head < bottom)).sum()),
                "initialized_heads_below_bottom": int((active & (seeded < bottom)).sum()),
                "thickness_min": float(np.min((top - bottom)[active])),
                "thickness_max": float(np.max((top - bottom)[active])),
            }
        )

    bed, stage, conductance = read("riv_bot.map"), read("riv_stage.map"), read("riv_cond.map")
    river = active & np.isfinite(conductance) & (conductance > 0)
    assigned = np.zeros(active.shape, dtype=bool)
    entries, counts = [], []
    for index, (bottom, top) in enumerate(zip(surface, surface[1:])):
        selected = river & ~assigned & (bed >= bottom) & (bed <= top)
        assigned |= selected
        counts.append(int(selected.sum()))
        entries.append(
            {
                "layer": index + 1,
                "stage": write(f"river-stage{index + 1}.map", np.where(selected, stage, np.nan)),
                "bottom": write(f"river-bed{index + 1}.map", np.where(selected, bed, np.nan)),
                "conductance": write(
                    f"river-conductance{index + 1}.map", np.where(selected, conductance, np.nan)
                ),
            }
        )
    manifest["river_cells_bottom_to_top"] = counts
    manifest["river_cells_excluded"] = int((river & ~assigned).sum())
    write("river-excluded.map", (river & ~assigned).astype(float))
    mf["river"] = {"enabled": True, "layers": entries}
    mf["dis"]["nstp"] = 1
    mf["solver"].update(mxiter=mxiter, hclose=0.01, rclose=0.01)
    mf["wetting"].update(
        enabled=wetting != "off",
        map=write(
            "wetting.map",
            np.where(active, -wetdry_threshold if wetting == "below" else wetdry_threshold, 0),
        ),
        multiplier=1.0,
        layers=[3],
        wetfct=wetfct,
        ihdwet=ihdwet,
    )
    configs = {}
    for branch in BRANCHES:
        document = copy.deepcopy(base)
        document["DIRECTORIES"]["output"] = str(destination / "runs" / branch)
        if branch == BRANCHES[-1]:
            _to_pr_schema(document["MODFLOW"])
        path = destination / f"{branch}.json"
        _json(path, document)
        configs[branch] = path

        faithful = copy.deepcopy(document)
        for layer in faithful["MODFLOW"]["layers"]:
            suffix = {"lower": 1, "middle": 2, "upper": 3}[layer["name"]]
            layer["initial_head"] = str(maps / f"head{suffix}.map")
        faithful["DIRECTORIES"]["output"] += "-original-heads"
        _json(destination / f"{branch}-original-heads.json", faithful)
    _json(destination / "manifest.json", manifest)
    return configs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--months", type=int, default=2)
    parser.add_argument(
        "--profile", choices=("reconstructed", "scientist"), default="reconstructed"
    )
    parser.add_argument("--wetting", choices=("off", "below", "lateral"), default="below")
    parser.add_argument("--mxiter", type=int, default=2000)
    parser.add_argument("--wetfct", type=float, default=1.0)
    parser.add_argument("--ihdwet", type=int, choices=(0, 1), default=0)
    parser.add_argument("--head-donors", choices=("positive", "wet"), default="positive")
    parser.add_argument("--wetdry-threshold", type=float, default=1.0)
    args = parser.parse_args()
    for branch, path in prepare(
        args.dataset,
        args.destination,
        months=args.months,
        profile=args.profile,
        wetting=args.wetting,
        mxiter=args.mxiter,
        wetfct=args.wetfct,
        ihdwet=args.ihdwet,
        head_donors=args.head_donors,
        wetdry_threshold=args.wetdry_threshold,
    ).items():
        print(f"{branch}: {path}")
