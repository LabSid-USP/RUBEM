"""The MODFLOW parameters a calibration may search: catalog, domain and document patching."""

import json
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from rubem.calibration.modflow_parameters import MODFLOW_PREFIX, ModflowCatalog, catalog
from rubem.calibration.parameters import decision_space
from rubem.configuration.modflow_configuration import ModflowSettings
from tests.helpers.config import REPO_ROOT


def write_table(path, text):
    path.write_text(text, encoding="utf8")
    return str(path)


def layer(name, laytype, **overrides):
    """One layer whose rasters are paths that are never read by the catalog."""
    item = {
        "name": name,
        "bottom": f"/maps/{name}_bottom.map",
        "initial_head": f"/maps/{name}_head.map",
        "boundary": "/maps/bound.map",
        "laytype": laytype,
        "horizontal_conductivity": 1.0,
        "vertical_conductivity": 0.1,
        "specific_yield": 0.15,
        "specific_storage": 1e-5,
    }
    item.update(overrides)
    return item


def section(layers, rivers=None, steady_state=False):
    """An enabled MODFLOW section with the given layers and river entries."""
    entries = rivers or [
        {
            "layers": [1],
            "stage": "/maps/stage.map",
            "bottom": "/maps/riv_bottom.map",
            "conductance": 0.387,
            "mask": "/maps/riv_mask.map",
        }
    ]
    return {
        "enabled": True,
        "top": "/maps/top.map",
        "layers": layers,
        "dis": {"steady_state": steady_state},
        "river": {"enabled": True, "entries": entries},
    }


@pytest.fixture
def kh_table(tmp_path):
    return write_table(tmp_path / "kh1.tbl", "1 0.5\n2 0.1\n")


@pytest.fixture
def two_layers(kh_table):
    """Layer 1 unconfined with kh classes, layer 2 convertible with a storage map."""
    return section(
        [
            layer(
                "upper",
                1,
                horizontal_conductivity={"map": "/maps/kh_classes1.map", "table": kh_table},
            ),
            layer("lower", 2, specific_storage="/maps/ss.map"),
        ],
        rivers=[
            {
                "layers": [1],
                "stage": "/maps/stage.map",
                "bottom": "/maps/riv_bottom.map",
                "conductance": 0.387,
                "mask": "/maps/riv_mask.map",
            },
            {
                "layers": [2],
                "stage": "/maps/stage.map",
                "bottom": "/maps/riv_bottom.map",
                "conductance": "/maps/riv_cond.map",
            },
        ],
    )


def document_of(settings_section):
    """A format 1.0 document reduced to what the patching touches."""
    return {"modflow": ModflowSettings.model_validate(settings_section).model_dump(mode="json")}


class TestCatalog:
    @pytest.mark.unit
    def test_the_numbers_and_the_table_rows_the_run_reads_are_named_top_down(self, two_layers):
        found = catalog(ModflowSettings.model_validate(two_layers))

        # LAYCON 1 reads only its specific yield; layer 2 has its specific
        # storage as a map, which is not a number to search; the second river
        # entry has a conductance map.
        assert found.names == (
            "modflow.layers.1.specific_yield",
            "modflow.layers.1.kh.1",
            "modflow.layers.1.kh.2",
            "modflow.layers.2.specific_yield",
            "modflow.river.1.conductance",
        )
        assert found.values == {
            "modflow.layers.1.specific_yield": 0.15,
            "modflow.layers.1.kh.1": 0.5,
            "modflow.layers.1.kh.2": 0.1,
            "modflow.layers.2.specific_yield": 0.15,
            "modflow.river.1.conductance": 0.387,
        }
        assert all(name.startswith(MODFLOW_PREFIX) for name in found.names)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("laytype", "expected"),
        [
            (0, ["specific_storage"]),
            (1, ["specific_yield"]),
            (2, ["specific_yield", "specific_storage"]),
            (13, ["specific_yield", "specific_storage"]),
        ],
    )
    def test_only_the_storage_the_layer_type_reads_is_named(self, laytype, expected):
        found = catalog(ModflowSettings.model_validate(section([layer("only", laytype)])))

        assert [
            name.rsplit(".", 1)[1] for name in found.names if name.startswith("modflow.layers.")
        ] == expected

    @pytest.mark.unit
    def test_a_steady_state_run_names_no_storage(self):
        found = catalog(
            ModflowSettings.model_validate(section([layer("only", 2)], steady_state=True))
        )

        assert found.names == ("modflow.river.1.conductance",)

    @pytest.mark.unit
    def test_numeric_class_keys_are_canonical_and_intervals_are_not_named(self, tmp_path):
        table = write_table(tmp_path / "kh.tbl", "01 0.5\n2.0 0.1\n[3,5] 0.2\n1 9.0\n")
        found = catalog(
            ModflowSettings.model_validate(
                section(
                    [
                        layer(
                            "only",
                            1,
                            horizontal_conductivity={"map": "/maps/classes.map", "table": table},
                        )
                    ]
                )
            )
        )

        # PCRaster uses the first row that matches a class, so the second row
        # of class 1 is never read and the name carries the first one's value.
        assert found.values["modflow.layers.1.kh.1"] == 0.5
        assert found.values["modflow.layers.1.kh.2"] == 0.1
        assert not [name for name in found.names if "[" in name]
        # The rows themselves are kept as they are written.
        assert found.tables[1] == [("01", 0.5), ("2.0", 0.1), ("[3,5]", 0.2), ("1", 9.0)]

    @pytest.mark.unit
    @pytest.mark.parametrize("interval", ["[1,3]", "<1,>", "[2,2]"])
    def test_a_class_an_earlier_interval_row_covers_is_not_named(self, tmp_path, interval):
        table = write_table(tmp_path / "kh.tbl", f"{interval} 5\n2 7\n")
        settings = ModflowSettings.model_validate(
            section(
                [
                    layer(
                        "only",
                        1,
                        horizontal_conductivity={"map": "/maps/classes.map", "table": table},
                    )
                ]
            )
        )

        found = catalog(settings)

        # PCRaster reads the interval row for class 2, so searching the second
        # row would spend the budget on a value the run never sees.
        assert "modflow.layers.1.kh.2" not in found.names
        with pytest.raises(ValueError, match=r"modflow\.layers\.1\.specific_yield"):
            decision_space(bounds={"modflow.layers.1.kh.2": (0.1, 1.0)}, modflow=found)

    @pytest.mark.unit
    def test_a_class_after_an_interval_that_does_not_cover_it_is_named(self, tmp_path):
        table = write_table(tmp_path / "kh.tbl", "[3,5] 5\n<0,2> 6\n2 7\n")
        settings = ModflowSettings.model_validate(
            section(
                [
                    layer(
                        "only",
                        1,
                        horizontal_conductivity={"map": "/maps/classes.map", "table": table},
                    )
                ]
            )
        )

        assert catalog(settings).values["modflow.layers.1.kh.2"] == 7.0

    @pytest.mark.unit
    def test_the_catalog_is_plain_data_that_crosses_to_a_worker(self, two_layers):
        found = catalog(ModflowSettings.model_validate(two_layers))

        assert isinstance(found, ModflowCatalog)
        # The process pool pickles the context of every evaluation; the bytes
        # here are the ones this test produced.
        assert pickle.loads(pickle.dumps(found)) == found

    @pytest.mark.unit
    def test_importing_the_module_imports_no_native_library(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys\n"
                "import rubem.calibration.modflow_parameters\n"
                "import rubem.calibration.parameters\n"
                "print(sorted(m for m in sys.modules "
                "if m.split('.')[0] in ('pcraster', 'osgeo', 'scipy')))\n",
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )

        assert completed.stdout.strip() == "[]"


class TestDomain:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("name", "value", "admissible"),
        [
            ("modflow.layers.1.specific_yield", 1.0, True),
            ("modflow.layers.1.specific_yield", 0.3, True),
            ("modflow.layers.1.specific_yield", 0.0, False),
            ("modflow.layers.1.specific_yield", 1.5, False),
            ("modflow.layers.1.kh.1", 1e-9, True),
            ("modflow.layers.1.kh.1", 0.0, False),
            ("modflow.layers.1.kh.1", -1.0, False),
            ("modflow.layers.1.kh.1", float("inf"), False),
            ("modflow.layers.1.kh.1", float("nan"), False),
            ("modflow.river.1.conductance", 50.0, True),
            ("modflow.river.1.conductance", 0.0, False),
            ("modflow.layers.2.specific_yield", 0.0, False),
        ],
    )
    def test_the_values_a_candidate_may_carry(self, two_layers, name, value, admissible):
        found = catalog(ModflowSettings.model_validate(two_layers))

        assert found.admits(name, value) is admissible

    @pytest.mark.unit
    def test_the_domain_is_described_for_the_messages(self, two_layers):
        found = catalog(ModflowSettings.model_validate(two_layers))

        assert found.domain("modflow.layers.1.specific_yield") == "(0, 1]"
        assert found.domain("modflow.layers.1.kh.2") == "(0, inf)"


class TestApply:
    @pytest.mark.unit
    def test_numbers_are_replaced_in_place(self, two_layers, tmp_path):
        found = catalog(ModflowSettings.model_validate(two_layers))
        document = document_of(two_layers)
        before = json.loads(json.dumps(document))

        found.apply(
            document,
            {
                "alpha": 4.5,
                "modflow.layers.2.specific_yield": 0.2,
                "modflow.river.1.conductance": 1,
            },
            tmp_path / "evaluation",
        )

        assert document["modflow"]["layers"][1]["specific_yield"] == 0.2
        conductance = document["modflow"]["river"]["entries"][0]["conductance"]
        assert conductance == 1.0
        assert isinstance(conductance, float)
        # Nothing else moved: the kh table is only rewritten when a class is named.
        before["modflow"]["layers"][1]["specific_yield"] = 0.2
        before["modflow"]["river"]["entries"][0]["conductance"] = 1.0
        assert document == before
        assert not (tmp_path / "evaluation").exists()
        ModflowSettings.model_validate(document["modflow"])

    @pytest.mark.unit
    def test_a_named_class_rewrites_the_table_of_its_layer(self, two_layers, kh_table, tmp_path):
        found = catalog(ModflowSettings.model_validate(two_layers))
        document = document_of(two_layers)
        table_dir = tmp_path / "evaluation"
        table_dir.mkdir()

        found.apply(document, {"modflow.layers.1.kh.2": 0.25}, table_dir)

        written = table_dir / "kh_layer1.tbl"
        lookup = document["modflow"]["layers"][0]["horizontal_conductivity"]
        assert Path(lookup["table"]) == written
        assert lookup["map"] == "/maps/kh_classes1.map"
        assert written.read_text(encoding="utf8").split() == ["1", "0.5", "2", "0.25"]
        # The configured table is never touched.
        assert (tmp_path / "kh1.tbl").read_text(encoding="utf8") == "1 0.5\n2 0.1\n"

    @pytest.mark.unit
    def test_the_rows_that_are_not_named_are_kept_verbatim(self, tmp_path):
        table = write_table(tmp_path / "kh.tbl", "01 0.5\n[3,5] 0.2\n1 9.0\n")
        settings = section(
            [layer("only", 1, horizontal_conductivity={"map": "/maps/c.map", "table": table})]
        )
        found = catalog(ModflowSettings.model_validate(settings))
        document = document_of(settings)

        found.apply(document, {"modflow.layers.1.kh.1": 0.75}, tmp_path)

        rows = [
            line.split() for line in (tmp_path / "kh_layer1.tbl").read_text("utf8").splitlines()
        ]
        assert rows == [["01", "0.75"], ["[3,5]", "0.2"], ["1", "9"]]

    @pytest.mark.unit
    def test_the_table_name_can_be_chosen(self, two_layers, tmp_path):
        found = catalog(ModflowSettings.model_validate(two_layers))
        document = document_of(two_layers)

        found.apply(
            document, {"modflow.layers.1.kh.1": 0.3}, tmp_path, table_prefix="basin-calibrated-kh"
        )

        assert (tmp_path / "basin-calibrated-kh1.tbl").is_file()
        assert not (tmp_path / "kh_layer1.tbl").exists()

    @pytest.mark.unit
    def test_without_a_modflow_name_the_document_is_left_alone(self, two_layers, tmp_path):
        found = catalog(ModflowSettings.model_validate(two_layers))
        document = document_of(two_layers)
        before = json.loads(json.dumps(document))

        found.apply(document, {"alpha": 4.5, "w_3": 0.1}, tmp_path / "nothing")

        assert document == before
        assert not (tmp_path / "nothing").exists()

    @pytest.mark.unit
    def test_a_name_the_catalog_does_not_hold_is_refused(self, two_layers, tmp_path):
        found = catalog(ModflowSettings.model_validate(two_layers))

        with pytest.raises(ValueError, match=r"modflow\.layers\.2\.specific_storage"):
            found.apply(
                document_of(two_layers), {"modflow.layers.2.specific_storage": 1e-4}, tmp_path
            )

    @pytest.mark.unit
    def test_pcraster_reads_the_rewritten_table(self, tmp_path):
        import pcraster as pcr

        from tests.helpers.synthetic import COLS, ROWS, write_grid_map

        classes = write_grid_map(
            tmp_path / "classes.map", [1] * COLS + [2] * (ROWS - 1) * COLS, True
        )
        table = write_table(tmp_path / "kh.tbl", "1 0.5\n2 0.1\n")
        settings = section(
            [layer("only", 1, horizontal_conductivity={"map": classes, "table": table})]
        )
        found = catalog(ModflowSettings.model_validate(settings))
        document = document_of(settings)
        out = tmp_path / "out"
        out.mkdir()

        # A value whose shortest repr is in scientific notation.
        found.apply(document, {"modflow.layers.1.kh.2": 1e-7}, out)

        rewritten = document["modflow"]["layers"][0]["horizontal_conductivity"]["table"]
        values = pcr.pcr2numpy(pcr.lookupscalar(rewritten, pcr.readmap(classes)), np.nan)
        assert values[0].tolist() == pytest.approx([0.5] * COLS)
        assert values[1:].ravel().tolist() == pytest.approx([1e-7] * (ROWS - 1) * COLS)

    @pytest.mark.unit
    def test_pcraster_reads_a_class_rewritten_before_an_interval_that_covers_it(self, tmp_path):
        import pcraster as pcr

        from tests.helpers.synthetic import COLS, ROWS, write_grid_map

        classes = write_grid_map(
            tmp_path / "classes.map", [1] * COLS + [2] * (ROWS - 1) * COLS, True
        )
        table = write_table(tmp_path / "kh.tbl", "2 7\n[1,3] 5\n")
        settings = section(
            [layer("only", 1, horizontal_conductivity={"map": classes, "table": table})]
        )
        found = catalog(ModflowSettings.model_validate(settings))
        document = document_of(settings)
        out = tmp_path / "out"
        out.mkdir()

        found.apply(document, {"modflow.layers.1.kh.2": 0.9}, out)

        rewritten = document["modflow"]["layers"][0]["horizontal_conductivity"]["table"]
        values = pcr.pcr2numpy(pcr.lookupscalar(rewritten, pcr.readmap(classes)), np.nan)
        assert values[0].tolist() == pytest.approx([5.0] * COLS)
        assert values[1:].ravel().tolist() == pytest.approx([0.9] * (ROWS - 1) * COLS)
