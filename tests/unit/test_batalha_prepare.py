"""Pure policies of the Batalha example preparer (no dataset, no MODFLOW run)."""

import json
import runpy
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("scipy.ndimage", reason="The Batalha preparer requires SciPy.")

EXAMPLE = Path(__file__).parents[2] / "examples/batalha_modflow/prepare.py"


@pytest.fixture(scope="module")
def preparer():
    return runpy.run_path(str(EXAMPLE))


def _prototype_settings():
    """A bottom-up prototype MODFLOW section with GHB on the top layer only."""
    return {
        "enabled": 1,
        "coupling": {"baseflow_from_river_leakage": True, "dynamic_root_depth": {"enabled": 0}},
        "bottom": "botton.map",
        "layers": [
            {"name": "layer_1", "top": "botton2.map", "laytype": 2, "specific_storage": "ss.map"},
            {"name": "layer_2", "top": "botton3.map", "laytype": 2, "specific_storage": "ss.map"},
            {"name": "layer_3", "top": "top_model.map", "laytype": 1, "specific_storage": "ss.map"},
        ],
        "recharge": {"source": "rubem", "option": 3},
        "dis": {"time_unit": 4, "length_unit": 2, "nstp": 5, "tsmult": 1.0, "steady_state": 0},
        "solver": {
            "type": "PCG",
            "mxiter": 2000,
            "hclose": 20.0,
            "rclose": 10.0,
            "fail_on_non_convergence": True,
        },
        "wetting": {
            "enabled": 1,
            "map": "wet.map",
            "multiplier": 1.0,
            "layers": [3],
            "wetfct": 0.1,
            "iwetit": 3,
            "ihdwet": 0,
        },
        "river": {
            "enabled": 1,
            "layers": [{"layer": 3, "stage": "s.map", "bottom": "b.map", "conductance": "c.map"}],
        },
        "ghb": {"enabled": 1, "layers": [{"layer": 3, "head": "gh.map", "conductance": "gc.map"}]},
        "wells": {"enabled": 0},
        "output": {"heads": True, "river_leakage": True, "storage": False},
    }


def test_to_pr_schema_reverses_layers_and_remaps_packages(preparer):
    settings = _prototype_settings()
    preparer["_to_pr_schema"](settings)
    assert settings["top"] == "top_model.map"
    assert [layer["name"] for layer in settings["layers"]] == ["layer_3", "layer_2", "layer_1"]
    assert [layer["bottom"] for layer in settings["layers"]] == [
        "botton3.map",
        "botton2.map",
        "botton.map",
    ]
    assert "specific_storage" not in settings["layers"][0]  # LAYCON 1 uses specific yield
    assert settings["river"]["entries"][0]["layers"] == [1]
    assert settings["ghb"]["entries"][0]["layers"] == [1]
    assert settings["wetting"]["layers"] == [1]
    assert "multiplier" not in settings["wetting"]
    for absent in ("recharge", "wells"):
        assert absent not in settings
    assert "type" not in settings["solver"]
    assert settings["output"]["root_depth"] is True


def test_ghb_entries_cover_the_requested_layers(preparer):
    source = _prototype_settings()["ghb"]
    none = preparer["ghb_section"](source, "none", "gc.map")
    assert none == {"enabled": 0}
    top = preparer["ghb_section"](source, "top", "gc.map")
    assert top == source
    full = preparer["ghb_section"](source, "full", "gc.map")
    assert [entry["layer"] for entry in full["layers"]] == [1, 2, 3]
    assert {entry["conductance"] for entry in full["layers"]} == {"gc.map"}
    split = preparer["ghb_section"](source, "split", "gc-third.map")
    assert [entry["layer"] for entry in split["layers"]] == [1, 2, 3]
    assert {entry["conductance"] for entry in split["layers"]} == {"gc-third.map"}
    assert {entry["head"] for entry in split["layers"]} == {"gh.map"}
    with pytest.raises(ValueError):
        preparer["ghb_section"](source, "sideways", "gc.map")


def test_fill_nearest_uses_the_closest_donor_only_on_missing_active_cells(preparer):
    head = np.array([[10.0, -888.0, 30.0], [np.nan, 0.0, 33.0]])
    active = np.array([[True, True, True], [True, True, False]])
    filled, count = preparer["fill_nearest"](head, active)
    assert count == 3
    assert filled[0, 1] in (10.0, 30.0)
    assert filled[1, 0] == 10.0
    assert filled[1, 1] in (10.0, 30.0)  # the inactive 33.0 is never a donor
    assert np.isnan(filled[1, 2])  # inactive cells carry no value
    assert filled[0, 0] == 10.0 and filled[0, 2] == 30.0


def test_answered_top_heads_apply_the_three_rules(preparer):
    head3 = np.array([[600.0, -805.0, 540.0], [-888.0, 450.0, 555.0]])
    head2 = np.array([[590.0, 580.0, 538.0], [500.0, 537.0, 550.0]])
    bottom = np.array([[500.0, 500.0, 535.0], [500.0, 535.8, 500.0]])
    surface = np.array([[590.0, 600.0, 560.0], [560.0, 560.0, 560.0]])
    active = np.array([[True, True, True], [False, True, True]])
    fixed, report = preparer["answered_top_heads"](head3, head2, bottom, surface, active)
    assert fixed[0, 1] == 580.0  # negative value on an active cell comes from the middle layer
    assert fixed[1, 1] == 537.0  # active head below its bottom is repaired from the middle layer
    assert fixed[0, 0] == 590.0  # heads above the model top are cut at the surface
    assert fixed[0, 2] == 540.0 and fixed[1, 2] == 555.0
    assert fixed[1, 0] == -888.0  # inactive cells are left as delivered
    assert report["negative_replaced"] == 1
    assert report["negative_without_valid_donor"] == 0
    assert report["below_bottom_repaired"] == 1
    assert report["below_bottom_cells"] == [(2, 2)]
    assert report["clipped_to_surface"] == 1
    kept, report = preparer["answered_top_heads"](
        head3, head2, bottom, surface, active, repair_below_bottom=False
    )
    assert kept[1, 1] == 450.0  # listed for deactivation, not repaired
    assert report["below_bottom_cells"] == [(2, 2)] and report["below_bottom_repaired"] == 0
    invalid = np.array([[590.0, -888.0, 538.0], [500.0, np.nan, 550.0]])
    fixed, report = preparer["answered_top_heads"](head3, invalid, bottom, surface, active)
    assert fixed[0, 1] == 500.0  # no valid donor: the layer bottom, never the -888 sentinel
    assert fixed[1, 1] == 535.8  # no valid donor: the layer bottom, never NaN
    assert report["negative_without_valid_donor"] == 1


def test_ghb_variants_need_one_delivered_entry(preparer):
    disabled = {"enabled": 0, "layers": [{"layer": 3, "head": "gh.map", "conductance": "gc.map"}]}
    assert preparer["ghb_section"](disabled, "none", None) == {"enabled": 0}
    with pytest.raises(ValueError):
        preparer["ghb_section"](disabled, "full", None)
    two = {"enabled": 1, "layers": [{"layer": 3, "head": "a", "conductance": "b"}] * 2}
    with pytest.raises(ValueError):
        preparer["ghb_section"](two, "split", "c")


def test_the_water_table_layer_is_remapped(preparer):
    settings = _prototype_settings()
    settings["coupling"]["dynamic_root_depth"]["water_table"] = {"method": "layer", "layer": 1}
    preparer["_to_pr_schema"](settings)
    assert settings["coupling"]["dynamic_root_depth"]["water_table"]["layer"] == 3


def test_source_root_keeps_the_separators_of_the_json(preparer):
    assert (
        preparer["_source_root"]("/data/batalha_basin/input/clone/clone.map")
        == "/data/batalha_basin"
    )
    assert preparer["_source_root"]("C:/RUBEM/DATASET/input/clone/clone.map") == "C:/RUBEM/DATASET"
    assert (
        preparer["_source_root"](r"C:\RUBEM\DATASET\input\clone\clone.map") == r"C:\RUBEM\DATASET"
    )
    with pytest.raises(ValueError):
        preparer["_source_root"]("clone.map")


def test_sha256_keys_are_posix_and_accept_files_outside_the_dataset(preparer, tmp_path):
    dataset = tmp_path / "dataset"
    (dataset / "input").mkdir(parents=True)
    inside, outside = dataset / "input" / "a.map", tmp_path / "source.json"
    inside.write_bytes(b"a")
    outside.write_bytes(b"b")
    digests = preparer["_sha256"](dataset, {inside, outside})
    assert set(digests) == {"input/a.map", outside.as_posix()}


def test_conductivity_suffixes_follow_the_orientation(preparer):
    assert preparer["conductivity_suffixes"]("base3") == {"lower": 3, "middle": 2, "upper": 1}
    assert preparer["conductivity_suffixes"]("as-delivered") == {
        "lower": 1,
        "middle": 2,
        "upper": 3,
    }
    with pytest.raises(ValueError):
        preparer["conductivity_suffixes"]("other")


def test_window_covers_up_to_twenty_four_months(preparer):
    assert preparer["_window"](2) == {"start": "01/08/2023", "end": "01/09/2023"}
    assert preparer["_window"](9) == {"start": "01/08/2023", "end": "01/04/2024"}
    assert preparer["_window"](24) == {"start": "01/08/2023", "end": "01/07/2025"}
    assert preparer["_window"](300, "01/08/2000") == {"start": "01/08/2000", "end": "01/07/2025"}
    assert preparer["_window"](5, "01/11/2024") == {"start": "01/11/2024", "end": "01/03/2025"}
    with pytest.raises(ValueError):
        preparer["_window"](2, "2023-08-01")


def test_series_links_shift_the_window_and_fall_back_to_the_last_raster(preparer):
    links = preparer["series_links"]
    assert links([1, 2, 3, 4], first_step=1, months=3) == {1: 1, 2: 2, 3: 3}
    assert links(list(range(1, 314)), first_step=277, months=24) == {
        k: 276 + k for k in range(1, 25)
    }
    # a land-use series with a raster every twelve steps: the latest raster at or before the step
    sparse = [1, 13, 25, 277, 289, 301]
    assert links(sparse, first_step=277, months=3) == {1: 277, 2: 277, 3: 277}
    assert links(sparse, first_step=280, months=2) == {1: 277, 2: 277}
    assert links(sparse, first_step=300, months=3) == {1: 289, 2: 301, 3: 301}
    with pytest.raises(ValueError):
        links([5, 6], first_step=1, months=2)  # nothing at or before the first step


def test_station_sample_gets_a_new_id_on_a_free_cell(preparer):
    samples = np.array([[0, 1, 0], [0, 0, 2], [0, 0, 0]])
    stamped, identifier = preparer["station_sample"](samples, row=3, col=1)
    assert identifier == 3
    assert stamped[2, 0] == 3 and (stamped != samples).sum() == 1
    with pytest.raises(ValueError):
        preparer["station_sample"](samples, row=1, col=2)  # already a sample
    with pytest.raises(ValueError):
        preparer["station_sample"](samples, row=4, col=1)  # outside the grid


def test_prepare_refuses_destinations_inside_the_dataset(preparer, tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    with pytest.raises(ValueError):
        preparer["prepare"](dataset, dataset / "out")
    with pytest.raises(ValueError):
        preparer["prepare"](dataset, tmp_path / "out", months=1)
    with pytest.raises(ValueError):
        preparer["prepare"](dataset, tmp_path / "out", profile="reconstructed")
    assert preparer["WETTING_STRATEGIES"] == ("as-delivered", "below", "off")


def _delivery(root):
    """A miniature delivery: a JSON with Windows paths, two tables, two series, a MODFLOW map."""
    dataset = root / "batalha_basin"
    for folder in ("clone", "text", "ndvi", "ndvi_hist", "cob_hist", "prec_hist", "modflow"):
        (dataset / "input" / folder).mkdir(parents=True)
    for name in (
        "clone/clone.map",
        "clone/clone.map.aux.xml",
        "text/kcmax.txt",
        "text/unread.tss",
        "ndvi/ndvi_max.map",
        "ndvi/ndvi_min.map",
        "ndvi_hist/ndvi_max.map",
        "ndvi_hist/ndvi_min.map",
        "modflow/bound.map",
        "modflow/extra.map",
    ):
        (dataset / "input" / name).write_bytes(name.encode())
    for step in (276, 277, 278, 279):
        for prefix, folder in (("ndvi", "ndvi_hist"), ("prec", "prec_hist")):
            (dataset / "input" / folder / f"{prefix}0000.{step:03d}").write_bytes(b"%d" % step)
    (dataset / "input/cob_hist/cob00000.265").write_bytes(b"265")
    (dataset / "input/cob_hist/cob00000.277").write_bytes(b"277")
    root_path = "C:/RUBEM/DATASET/input/"
    directories = {"ndvi": "ndvi_hist", "landuse": "cob_hist", "etp": "prec_hist"}
    directories |= {"prec": "prec_hist", "kp": "prec_hist", "output": "output"}
    document = {
        "DIRECTORIES": {key: f"{root_path}{value}/" for key, value in directories.items()},
        "FILENAME_PREFIXES": {
            "ndvi_prefix": "ndvi",
            "landuse_prefix": "cob",
            "etp_prefix": "prec",
            "prec_prefix": "prec",
            "kp_prefix": "prec",
        },
        "RASTERS": {
            "clone": f"{root_path}clone/clone.map",
            "ndvi_max": f"{root_path}ndvi/ndvi_max.map",
            "ndvi_min": f"{root_path}ndvi/ndvi_min.map",
        },
        "TABLES": {"k_c_max": f"{root_path}text/kcmax.txt"},
        "MODFLOW": {"layers": [{"name": "layer_1", "boundary": f"{root_path}modflow/bound.map"}]},
    }
    source = dataset / "delivery.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    return dataset, source


def test_delivery_files_are_the_named_files_and_the_window_rasters(preparer, tmp_path):
    dataset, source = _delivery(tmp_path)
    files = preparer["delivery_files"](dataset, source, first_step=277, months=2)
    keys = [path.relative_to(dataset.resolve()).as_posix() for path in files]
    assert keys == [
        "delivery.json",
        "input/clone/clone.map",
        "input/cob_hist/cob00000.277",
        "input/modflow/bound.map",
        "input/ndvi/ndvi_max.map",
        "input/ndvi/ndvi_min.map",
        "input/ndvi_hist/ndvi0000.277",
        "input/ndvi_hist/ndvi0000.278",
        "input/ndvi_hist/ndvi_max.map",
        "input/ndvi_hist/ndvi_min.map",
        "input/prec_hist/prec0000.277",
        "input/prec_hist/prec0000.278",
        "input/text/kcmax.txt",
    ]  # no sidecar, no unread table or map, no output directory, no step outside the window


def test_the_manifest_also_pins_the_unread_tables(preparer, tmp_path):
    dataset, source = _delivery(tmp_path)
    (dataset / "input/dem").mkdir()
    (dataset / "input/dem/ldd.map").write_bytes(b"ldd")
    read = preparer["delivery_files"](dataset, source, first_step=277, months=2)
    pinned = preparer["manifest_files"](dataset, source, first_step=277, months=2)
    extra = sorted(
        path.relative_to(dataset.resolve()).as_posix() for path in set(pinned) - set(read)
    )
    assert extra == ["input/dem/ldd.map", "input/text/unread.tss"]


def test_a_copy_that_departs_from_the_manifest_is_reported_by_path(preparer, tmp_path):
    dataset, source = _delivery(tmp_path)
    files = preparer["delivery_files"](dataset, source, first_step=277, months=2)
    digests = preparer["_sha256"](dataset.resolve(), files)
    manifest = tmp_path / "delivery.sha256"
    manifest.write_text("".join(f"{digest}  {key}\n" for key, digest in digests.items()))
    committed = preparer["read_sha256_manifest"](manifest)
    assert committed == digests
    expected = list(digests)
    compare = preparer["compare_with_delivery"]
    assert compare(digests, expected, committed) == {"differing": [], "missing": [], "unlisted": []}
    (dataset / "input/text/kcmax.txt").write_bytes(b"25 0.2")
    (dataset / "input/ndvi/ndvi_min.map").unlink()
    files = [path for path in files if path.is_file()]
    local = preparer["_sha256"](dataset.resolve(), [*files, dataset / "input/modflow/extra.map"])
    assert compare(local, expected, committed) == {
        "differing": ["input/text/kcmax.txt"],
        "missing": ["input/ndvi/ndvi_min.map"],
        "unlisted": ["input/modflow/extra.map"],
    }


def test_the_committed_delivery_manifest_covers_the_24_month_window(preparer):
    path = preparer["DELIVERY_MANIFEST"]
    assert path.name == "delivery-2026-11-03.sha256"
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n") and "\r" not in text
    digests = preparer["read_sha256_manifest"](path)
    assert all(len(digest) == 64 and int(digest, 16) >= 0 for digest in digests.values())
    assert all(not key.startswith("/") and not key.endswith(".aux.xml") for key in digests)
    assert preparer["DELIVERY_SOURCE"] in digests
    for series, prefix in (("prec", "prec0000"), ("etp", "etp00000"), ("kp", "kp000000")):
        steps = [key for key in digests if key.startswith(f"input/{series}_hist/")]
        assert steps == [f"input/{series}_hist/{prefix}.{step}" for step in range(277, 301)]
    assert [key for key in digests if key.startswith("input/cob_hist/")] == [
        "input/cob_hist/cob00000.277",
        "input/cob_hist/cob00000.289",
    ]
    for folder in ("ndvi", "ndvi_hist"):
        assert {f"input/{folder}/ndvi_max.map", f"input/{folder}/ndvi_min.map"} <= set(digests)
    assert {"input/text/landuse/kcmax.txt", "input/modflow/bound3.map"} <= set(digests)
    assert {"input/dem/ldd.map", "input/text/obsCalib.tss"} <= set(digests)  # pinned, not read
    assert len(digests) == 153
