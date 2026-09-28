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


def prepare(
    dataset: Path,
    destination: Path,
    *,
    months: int = 2,
    wetting: str = "below",
    mxiter: int = 2000,
    wetfct: float = 1.0,
    ihdwet: int = 0,
    head_donors: str = "positive",
    wetdry_threshold: float = 1.0,
) -> dict[str, Path]:
    """Write the same physical model in the three branches' configuration formats.

    Derived heads are numerical initialization estimates, not observations.
    The assumptions and each altered cell count are recorded in manifest.json.
    """
    dataset, destination = dataset.resolve(), destination.resolve()
    if destination == dataset or dataset in destination.parents:
        raise ValueError("The destination must be outside the source dataset.")
    if months < 2 or months > 9:
        raise ValueError("This dataset exercise supports 2 through 9 months.")
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
    source_paths = {dataset / "bauru_modflow.json", dataset / "input/clone/clone.map"}
    source_paths.update(maps.glob("*.map"))
    for path in sorted(source_paths):
        manifest["source_sha256"][str(path.relative_to(dataset))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

    original = json.loads((dataset / "bauru_modflow.json").read_text(encoding="utf-8"))
    old_root = str(Path(original["RASTERS"]["clone"]).parents[2])
    base = _replace(original, old_root, str(dataset))
    month_index = 2023 * 12 + 7 + months - 1
    base["SIM_TIME"] = {
        "start": "01/08/2023",
        "end": f"01/{month_index % 12 + 1:02d}/{month_index // 12}",
    }
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
        settings = document["MODFLOW"]
        if branch == "feat_356_modflow_coupling":
            settings.pop("bottom")
            settings["top"] = str(maps / SURFACES[-1])
            settings["layers"].reverse()
            for layer, bottom in zip(settings["layers"], reversed(SURFACES[:-1])):
                layer.pop("top")
                layer["bottom"] = str(maps / bottom)
            for package in ("river", "ghb"):
                settings[package]["entries"] = settings[package].pop("layers")
                for entry in settings[package]["entries"]:
                    entry["layers"] = [4 - entry.pop("layer")]
            settings["wetting"].pop("multiplier")
            settings["wetting"]["layers"] = [1]
            for name in ("recharge", "wells"):
                settings.pop(name)
            for name in ("time_unit", "length_unit"):
                settings["dis"].pop(name)
            for name in ("type", "fail_on_non_convergence"):
                settings["solver"].pop(name)
            settings["coupling"].pop("baseflow_from_river_leakage")
            settings["output"]["root_depth"] = True
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
        wetting=args.wetting,
        mxiter=args.mxiter,
        wetfct=args.wetfct,
        ihdwet=args.ihdwet,
        head_donors=args.head_donors,
        wetdry_threshold=args.wetdry_threshold,
    ).items():
        print(f"{branch}: {path}")
