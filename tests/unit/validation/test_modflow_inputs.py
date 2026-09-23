"""Checks of the MODFLOW inputs and runtime run before a coupled simulation.

The rasters are real PCRaster maps on the 3x3 synthetic grid: pyfakefs cannot
back PCRaster or GDAL I/O.
"""

import math
import os
from pathlib import Path

import numpy as np
import pytest

from rubem import _deps
from rubem.configuration._problems import ConfigurationError
from rubem.configuration.input_raster_files import InputRasterFiles
from rubem.configuration.input_table_files import InputTableFiles
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.model_configuration_file import ModelConfigurationFile
from rubem.configuration.model_configuration_file_v1 import ModelConfigurationFileV1
from rubem.configuration.modflow_configuration import ModflowSettings
from rubem.validation import modflow_inputs
from rubem.validation.modflow_inputs import check_modflow_inputs
from tests.helpers.synthetic import (
    CELL_SIZE,
    MODFLOW_HEAD,
    MODFLOW_LAYER_THICKNESS,
    MODFLOW_TOP,
    NORTH,
    WEST,
    write_grid_map,
    write_modflow_inputs,
    write_synthetic_dataset,
)

NAN = math.nan
# Row-major 3x3 grids: the cell at row 2, column 3 is index 5.
ROW_2_COLUMN_3 = 5


@pytest.fixture(name="config")
def config_fixture(tmp_path):
    """The synthetic dataset with a valid three-layer MODFLOW section."""
    config = write_synthetic_dataset(str(tmp_path))
    config["MODFLOW"] = write_modflow_inputs(config)
    return config


def raster_files(config):
    rasters = config["RASTERS"]
    return InputRasterFiles(
        dem=rasters["dem"],
        clone=rasters["clone"],
        ndvi_max=rasters["ndvi_max"],
        ndvi_min=rasters["ndvi_min"],
        soil=rasters["soil"],
        ldd=rasters["ldd"],
        sample_locations=rasters["samples"],
        validate_input=False,
    )


def table_files(config):
    tables = dict(config["TABLES"])
    tables["rainy_days"] = tables.pop("rainydays")
    tables["kc_min"] = tables.pop("k_c_min")
    tables["kc_max"] = tables.pop("k_c_max")
    return InputTableFiles(**tables, validate_input=False)


def check(config, validate_input=True):
    settings = ModflowSettings.model_validate(config["MODFLOW"])
    return check_modflow_inputs(
        settings, raster_files(config), validate_input, tables=table_files(config)
    )


def blocking(problems):
    return [problem for problem in problems if problem.blocking]


def sibling(config, name):
    """A path in the directory of the MODFLOW inputs."""
    return os.path.join(os.path.dirname(config["MODFLOW"]["top"]), name)


def grid(values, at=None, value=None):
    """Nine values; ``values`` broadcast, with ``value`` placed at index ``at``."""
    array = np.full(9, values, dtype=float)
    if at is not None:
        array[at] = value
    return array


def enable_root_depth(config, rows):
    table = sibling(config, "dpz_min.txt")
    Path(table).write_text("".join(f"{key} {value}\n" for key, value in rows), encoding="utf8")
    config["MODFLOW"]["coupling"] = {
        "dynamic_root_depth": {"enabled": True, "minimum_depth_table": table}
    }
    return table


class TestValidInputs:
    @pytest.mark.unit
    @pytest.mark.parametrize("validate_input", [True, False])
    def test_the_synthetic_inputs_have_no_problem(self, config, validate_input):
        assert check(config, validate_input) == []


class TestFiles:
    @pytest.mark.unit
    @pytest.mark.parametrize("validate_input", [True, False])
    def test_a_missing_file_is_blocking_with_or_without_validation(self, config, validate_input):
        missing = sibling(config, "absent.map")
        config["MODFLOW"]["layers"][1]["bottom"] = missing

        problems = check(config, validate_input)

        assert len(problems) == 1
        assert problems[0].blocking
        assert problems[0].description == "MODFLOW input file does not exist."
        assert Path(problems[0].file) == Path(missing)

    @pytest.mark.unit
    def test_a_missing_lookup_table_is_reported(self, config):
        table = sibling(config, "absent.tbl")
        config["MODFLOW"]["layers"][0]["horizontal_conductivity"]["table"] = table

        problems = check(config)

        assert [Path(p.file) for p in blocking(problems)] == [Path(table)]

    @pytest.mark.unit
    def test_an_empty_file_is_blocking(self, config):
        empty = sibling(config, "empty.map")
        Path(empty).write_bytes(b"")
        config["MODFLOW"]["top"] = empty

        problems = check(config, validate_input=False)

        assert len(problems) == 1 and problems[0].blocking
        assert problems[0].description == "MODFLOW input file is empty."
        assert Path(problems[0].file) == Path(empty)

    @pytest.mark.unit
    def test_a_file_shared_by_several_layers_is_reported_once(self, config):
        boundary = sibling(config, "absent_bound.map")
        for item in config["MODFLOW"]["layers"]:
            item["boundary"] = boundary

        assert len(check(config)) == 1

    @pytest.mark.unit
    def test_the_files_of_what_the_run_does_not_read_are_not_checked(self, config):
        """A disabled package may keep entries whose files are gone."""
        absent = sibling(config, "absent.map")
        config["MODFLOW"]["drain"] = {
            "enabled": False,
            "entries": [{"layers": [1], "elevation": absent, "conductance": absent}],
        }
        config["MODFLOW"]["wetting"] = {"enabled": False, "map": absent}
        config["MODFLOW"]["coupling"] = {
            "dynamic_root_depth": {"enabled": False, "minimum_depth_table": absent}
        }

        assert check(config) == []

    @pytest.mark.unit
    def test_the_content_is_not_read_when_a_file_is_missing(self, config):
        config["MODFLOW"]["top"] = sibling(config, "absent.map")
        write_grid_map(config["MODFLOW"]["layers"][0]["boundary"], 7, nominal=True)

        problems = check(config)

        assert [p.description for p in problems] == ["MODFLOW input file does not exist."]


class TestRuntime:
    @pytest.mark.unit
    @pytest.mark.parametrize("validate_input", [True, False])
    def test_a_missing_runtime_is_blocking_with_or_without_validation(
        self, config, monkeypatch, validate_input
    ):
        monkeypatch.setattr(modflow_inputs, "missing_groundwater_deps", lambda: ["mf2005"])

        problems = check(config, validate_input)

        assert len(problems) == 1 and problems[0].blocking
        assert problems[0].description == "MODFLOW runtime is not available."
        assert problems[0].reason == _deps.groundwater_deps_message(["mf2005"])

    @pytest.mark.unit
    def test_the_content_is_not_read_without_pcraster(self, config, monkeypatch):
        monkeypatch.setattr(
            modflow_inputs, "missing_groundwater_deps", lambda: ["pcraster._pcraster_modflow"]
        )
        monkeypatch.setattr(modflow_inputs, "missing_runtime_deps", lambda: ["pcraster"])
        write_grid_map(config["MODFLOW"]["layers"][0]["boundary"], 7, nominal=True)

        problems = check(config)

        assert [p.description for p in problems] == ["MODFLOW runtime is not available."]


class TestRasters:
    @pytest.mark.unit
    def test_the_content_is_checked_only_with_validation(self, config):
        write_grid_map(config["MODFLOW"]["layers"][0]["boundary"], 7, nominal=True)

        assert check(config, validate_input=False) == []
        assert blocking(check(config, validate_input=True))

    @pytest.mark.unit
    def test_a_raster_of_another_geometry_is_blocking(self, config):
        """PCRaster reads a map of another size on the clone without complaint."""
        import pcraster as pcr

        small = sibling(config, "small.map")
        pcr.setclone(2, 2, CELL_SIZE, WEST, NORTH)
        pcr.report(pcr.numpy2pcr(pcr.Scalar, np.full((2, 2), 50.0, np.float32), -9999.0), small)
        config["MODFLOW"]["layers"][2]["bottom"] = small

        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert problems[0].description == "MODFLOW raster does not share the clone geometry."
        assert Path(problems[0].file) == Path(small)

    @pytest.mark.unit
    def test_an_unreadable_raster_is_blocking(self, config):
        broken = sibling(config, "broken.map")
        Path(broken).write_text("not a raster", encoding="utf8")
        config["MODFLOW"]["top"] = broken

        problems = check(config)

        assert problems and all(p.blocking for p in problems)
        assert Path(problems[0].file) == Path(broken)
        assert "cannot be read" in problems[0].description


class TestBoundary:
    @pytest.mark.unit
    def test_a_boundary_value_other_than_minus_one_zero_or_one_is_blocking(self, config):
        path = sibling(config, "bound2.map")
        write_grid_map(path, grid(1, at=ROW_2_COLUMN_3, value=2), nominal=True)
        config["MODFLOW"]["layers"][1]["boundary"] = path

        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert problems[0].description == "MODFLOW boundary of layer 2 (layer2) has invalid values."
        assert "[2]" in problems[0].reason
        assert Path(problems[0].file) == Path(path)

    @pytest.mark.unit
    def test_constant_head_and_missing_cells_are_accepted(self, config):
        path = sibling(config, "bound_ch.map")
        values = grid(1, at=0, value=-1)
        values[8] = NAN
        write_grid_map(path, values, nominal=True)
        config["MODFLOW"]["layers"][0]["boundary"] = path

        assert check(config) == []


class TestGeometry:
    @pytest.mark.unit
    def test_a_missing_top_on_an_active_column_is_blocking(self, config):
        write_grid_map(config["MODFLOW"]["top"], grid(MODFLOW_TOP, at=ROW_2_COLUMN_3, value=NAN))

        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert problems[0].description == "MODFLOW model top has missing values on active columns."
        assert "row 2, column 3" in problems[0].reason

    @pytest.mark.unit
    def test_a_bottom_that_is_not_below_the_layer_above_is_blocking(self, config):
        upper = MODFLOW_TOP - MODFLOW_LAYER_THICKNESS
        write_grid_map(
            config["MODFLOW"]["layers"][1]["bottom"],
            grid(upper - MODFLOW_LAYER_THICKNESS, at=ROW_2_COLUMN_3, value=upper),
        )

        problems = check(config)

        geometry = [p for p in problems if "not below" in p.description]
        assert len(geometry) == 1 and geometry[0].blocking
        assert geometry[0].description == (
            "MODFLOW bottom of layer 2 (layer2) is not below the top of the layer."
        )
        assert "row 2, column 3" in geometry[0].reason
        assert "1 cell" in geometry[0].reason

    @pytest.mark.unit
    def test_a_bottom_above_the_model_top_is_blocking(self, config):
        write_grid_map(config["MODFLOW"]["layers"][0]["bottom"], grid(80.0, at=0, value=120.0))

        problems = check(config)

        assert any(
            p.blocking and p.description.startswith("MODFLOW bottom of layer 1 (layer1)")
            for p in problems
        )

    @pytest.mark.unit
    def test_columns_inactive_in_every_layer_are_not_checked(self, config):
        """The coupling fills those columns with synthetic elevations."""
        boundary = sibling(config, "bound_hole.map")
        write_grid_map(boundary, grid(1, at=ROW_2_COLUMN_3, value=0), nominal=True)
        for item in config["MODFLOW"]["layers"]:
            item["boundary"] = boundary
        write_grid_map(config["MODFLOW"]["top"], grid(MODFLOW_TOP, at=ROW_2_COLUMN_3, value=NAN))
        write_grid_map(
            config["MODFLOW"]["layers"][2]["bottom"], grid(40.0, at=ROW_2_COLUMN_3, value=500.0)
        )

        assert check(config) == []


class TestLayerValues:
    @pytest.mark.unit
    def test_a_missing_initial_head_on_an_active_cell_is_blocking(self, config):
        path = sibling(config, "head_hole.map")
        write_grid_map(path, grid(MODFLOW_HEAD, at=0, value=NAN))
        config["MODFLOW"]["layers"][2]["initial_head"] = path

        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert problems[0].description == (
            "MODFLOW initial head of layer 3 (layer3) has missing values on active cells."
        )
        assert "row 1, column 1" in problems[0].reason

    @pytest.mark.unit
    def test_a_missing_value_on_an_inactive_cell_is_accepted(self, config):
        boundary = sibling(config, "bound_hole.map")
        write_grid_map(boundary, grid(1, at=0, value=0), nominal=True)
        config["MODFLOW"]["layers"][2]["boundary"] = boundary
        path = sibling(config, "head_hole.map")
        write_grid_map(path, grid(MODFLOW_HEAD, at=0, value=NAN))
        config["MODFLOW"]["layers"][2]["initial_head"] = path

        assert check(config) == []

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "key, label",
        [
            ("vertical_conductivity", "vertical conductivity"),
            ("horizontal_conductivity", "horizontal conductivity"),
            ("specific_storage", "specific storage"),
            ("specific_yield", "specific yield"),
        ],
    )
    def test_a_missing_property_on_an_active_cell_is_blocking(self, config, key, label):
        path = sibling(config, f"{key}.map")
        write_grid_map(path, grid(0.1, at=ROW_2_COLUMN_3, value=NAN))
        config["MODFLOW"]["layers"][1][key] = path

        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert problems[0].description == (
            f"MODFLOW {label} of layer 2 (layer2) has missing values on active cells."
        )

    @pytest.mark.unit
    def test_a_head_below_the_bottom_in_every_active_cell_is_blocking(self, config):
        path = sibling(config, "head_low.map")
        write_grid_map(path, 10.0)
        config["MODFLOW"]["layers"][1]["initial_head"] = path

        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert problems[0].description == (
            "MODFLOW initial head of layer 2 (layer2) is below the layer bottom in every "
            "active cell."
        )

    @pytest.mark.unit
    def test_a_head_below_the_bottom_in_some_active_cells_is_a_warning(self, config):
        path = sibling(config, "head_low.map")
        values = grid(MODFLOW_HEAD, at=0, value=10.0)
        values[1] = 10.0
        write_grid_map(path, values)
        config["MODFLOW"]["layers"][1]["initial_head"] = path

        problems = check(config)

        assert len(problems) == 1 and not problems[0].blocking
        assert problems[0].description == (
            "MODFLOW initial head of layer 2 (layer2) is below the layer bottom in some "
            "active cells."
        )
        assert problems[0].reason.startswith("2 of 9 active cells")


class TestConductivityClasses:
    @pytest.mark.unit
    def test_a_class_absent_from_the_table_is_blocking(self, config):
        lookup = config["MODFLOW"]["layers"][0]["horizontal_conductivity"]
        Path(lookup["table"]).write_text("1 0.5\n", encoding="utf8")

        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert problems[0].description == (
            "MODFLOW horizontal conductivity table of layer 1 (layer1) does not cover the "
            "classes of its map."
        )
        assert "[2]" in problems[0].reason
        assert Path(problems[0].file) == Path(lookup["table"])

    @pytest.mark.unit
    @pytest.mark.parametrize("value", ["0", "-0.1", "nan"])
    def test_a_class_without_a_positive_value_is_blocking(self, config, value):
        lookup = config["MODFLOW"]["layers"][0]["horizontal_conductivity"]
        Path(lookup["table"]).write_text(f"1 0.5\n2 {value}\n", encoding="utf8")

        problems = blocking(check(config))

        assert len(problems) == 1
        assert Path(problems[0].file) == Path(lookup["table"])

    @pytest.mark.unit
    def test_an_interval_key_covers_its_classes(self, config):
        lookup = config["MODFLOW"]["layers"][0]["horizontal_conductivity"]
        Path(lookup["table"]).write_text("[1,2] 0.5\n", encoding="utf8")

        assert check(config) == []

    @pytest.mark.unit
    def test_classes_of_inactive_cells_need_no_value(self, config):
        boundary = sibling(config, "bound_top_row_off.map")
        write_grid_map(boundary, [0, 0, 0, 1, 1, 1, 1, 1, 1], nominal=True)
        config["MODFLOW"]["layers"][0]["boundary"] = boundary
        lookup = config["MODFLOW"]["layers"][0]["horizontal_conductivity"]
        Path(lookup["table"]).write_text("2 0.1\n", encoding="utf8")

        assert check(config) == []

    @pytest.mark.unit
    def test_an_unreadable_table_is_blocking(self, config):
        lookup = config["MODFLOW"]["layers"][0]["horizontal_conductivity"]
        Path(lookup["table"]).write_text("1 0.5 extra\n", encoding="utf8")

        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert "cannot be read" in problems[0].description

    @pytest.mark.unit
    def test_a_class_map_that_is_not_nominal_is_blocking(self, config):
        lookup = config["MODFLOW"]["layers"][0]["horizontal_conductivity"]
        write_grid_map(lookup["map"], 1.0)

        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert "nominal" in problems[0].description

    @pytest.mark.unit
    def test_a_missing_class_on_an_active_cell_is_blocking(self, config):
        lookup = config["MODFLOW"]["layers"][0]["horizontal_conductivity"]
        write_grid_map(lookup["map"], grid(2, at=0, value=NAN), nominal=True)

        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert "row 1, column 1" in problems[0].reason


class TestActiveCellGuard:
    @pytest.mark.unit
    def test_a_package_layer_without_a_positive_conductance_is_blocking(self, config):
        entry = config["MODFLOW"]["ghb"]["entries"][0]
        path = sibling(config, "ghb_cond_split.map")
        # Conductance only on row 1; layer 2 is inactive there.
        write_grid_map(path, [1, 1, 1, 0, 0, 0, 0, 0, 0])
        entry["conductance"] = path
        boundary = sibling(config, "bound_top_row_off.map")
        write_grid_map(boundary, [0, 0, 0, 1, 1, 1, 1, 1, 1], nominal=True)
        config["MODFLOW"]["layers"][1]["boundary"] = boundary

        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert problems[0].description == "MODFLOW ghb package has no cell in layer 2 (layer2)."
        assert "aborts the process" in problems[0].implication

    @pytest.mark.unit
    def test_river_cells_are_selected_by_the_mask(self, config):
        write_grid_map(config["MODFLOW"]["river"]["entries"][0]["mask"], 0)

        problems = check(config)

        assert [p.description for p in problems] == [
            "MODFLOW river package has no cell in layer 1 (layer1)."
        ]

    @pytest.mark.unit
    def test_river_cells_outside_the_boundary_of_the_layer_do_not_count(self, config):
        boundary = sibling(config, "bound_middle_off.map")
        write_grid_map(boundary, [1, 0, 1, 1, 0, 1, 1, 0, 1], nominal=True)
        config["MODFLOW"]["layers"][0]["boundary"] = boundary

        problems = check(config)

        assert [p.description for p in problems] == [
            "MODFLOW river package has no cell in layer 1 (layer1)."
        ]

    @pytest.mark.unit
    def test_an_enabled_drain_layer_without_cells_is_blocking(self, config):
        config["MODFLOW"]["drain"] = {
            "enabled": True,
            "entries": [
                {
                    "layers": [3],
                    "elevation": config["MODFLOW"]["top"],
                    "conductance": write_grid_map(sibling(config, "drn_cond.map"), 0),
                }
            ],
        }

        problems = check(config)

        assert [p.description for p in problems] == [
            "MODFLOW drain package has no cell in layer 3 (layer3)."
        ]

    @pytest.mark.unit
    def test_a_missing_stress_value_on_a_package_cell_is_blocking(self, config):
        """GHB cells are the left column; a missing head elsewhere is harmless."""
        head = config["MODFLOW"]["ghb"]["entries"][0]["head"]
        write_grid_map(head, grid(MODFLOW_HEAD, at=1, value=NAN))
        assert check(config) == []

        write_grid_map(head, grid(MODFLOW_HEAD, at=3, value=NAN))
        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert problems[0].description == (
            "MODFLOW ghb head has missing values on the cells of the package."
        )
        assert "row 2, column 1" in problems[0].reason


class TestRiverbed:
    @pytest.mark.unit
    def test_riverbeds_outside_the_layer_are_counted_without_blocking(self, config):
        # River cells are the middle column; layer 1 spans [80, 100] m.
        bottom = config["MODFLOW"]["river"]["entries"][0]["bottom"]
        write_grid_map(bottom, [0, 70.0, 0, 0, 90.0, 0, 0, 105.0, 0])

        problems = check(config)

        assert len(problems) == 1 and not problems[0].blocking
        assert problems[0].reason.startswith(
            "2 of 3 river cells of layer 1 have their bed outside the layer's elevation interval"
        )
        assert "1 below the layer bottom" in problems[0].reason
        assert "1 above the layer top" in problems[0].reason
        assert Path(problems[0].file) == Path(bottom)

    @pytest.mark.unit
    def test_the_interval_of_a_lower_layer_runs_between_its_bottom_and_the_bottom_above(
        self, config
    ):
        config["MODFLOW"]["river"]["entries"][0]["layers"] = [2]

        problems = check(config)

        assert len(problems) == 1 and not problems[0].blocking
        assert problems[0].reason.startswith(
            "3 of 3 river cells of layer 2 have their bed outside the layer's elevation interval"
        )

    @pytest.mark.unit
    def test_a_bed_on_the_limits_of_the_interval_is_inside(self, config):
        bottom = config["MODFLOW"]["river"]["entries"][0]["bottom"]
        write_grid_map(bottom, [0, 80.0, 0, 0, 90.0, 0, 0, 100.0, 0])

        assert check(config) == []


class TestMinimumRootDepth:
    @pytest.mark.unit
    def test_a_valid_table_has_no_problem(self, config):
        enable_root_depth(config, [(1, 50.0)])

        assert check(config) == []

    @pytest.mark.unit
    def test_a_soil_class_absent_from_the_table_is_blocking(self, config):
        table = enable_root_depth(config, [(2, 50.0)])

        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert problems[0].description == (
            "Minimum root depth (Dpz_min) lookup table does not cover the soil classes."
        )
        assert Path(problems[0].file) == Path(table)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "value, description",
        [
            (0.0, "Minimum root depth (Dpz_min) lookup table has non-positive values."),
            (-5.0, "Minimum root depth (Dpz_min) lookup table has non-positive values."),
            (200.0, "Minimum root depth (Dpz_min) exceeds the rootzone depth (Zr)."),
        ],
    )
    def test_a_value_outside_zero_and_the_rootzone_depth_is_blocking(
        self, config, value, description
    ):
        """The synthetic rootzone depth (Zr) of soil class 1 is 150.39."""
        enable_root_depth(config, [(1, value)])

        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert problems[0].description == description
        assert "soil class 1" in problems[0].reason

    @pytest.mark.unit
    def test_an_unreadable_table_is_blocking(self, config):
        table = enable_root_depth(config, [(1, "x")])

        problems = check(config)

        assert len(problems) == 1 and problems[0].blocking
        assert "cannot be read" in problems[0].description
        assert Path(problems[0].file) == Path(table)


class TestModelConfiguration:
    @pytest.fixture(name="plain")
    def plain_fixture(self, tmp_path):
        return write_synthetic_dataset(str(tmp_path))

    @staticmethod
    def formats(config):
        legacy = ModelConfigurationFile.model_validate(config)
        return (config, ModelConfigurationFileV1.from_legacy(legacy).to_dict())

    @pytest.mark.unit
    @pytest.mark.parametrize("validate_input", [True, False])
    def test_an_absent_section_runs_no_check_and_adds_no_problem(
        self, plain, monkeypatch, validate_input
    ):
        """The problems of a configuration without the section are the ones of main."""
        baseline = [
            ModelConfiguration(source, validate_input=validate_input).problems
            for source in self.formats(plain)
        ]

        def refuse(*args, **kwargs):
            raise AssertionError("check_modflow_inputs ran without an enabled section")

        monkeypatch.setattr("rubem.configuration.model_configuration.check_modflow_inputs", refuse)
        for source, expected in zip(self.formats(plain), baseline, strict=True):
            loaded = ModelConfiguration(source, validate_input=validate_input)
            assert loaded.problems == expected
        assert baseline == [[], []]

    @pytest.mark.unit
    def test_a_disabled_section_runs_no_check(self, config, monkeypatch):
        config["MODFLOW"]["enabled"] = False
        config["MODFLOW"]["top"] = "absent.map"

        def refuse(*args, **kwargs):
            raise AssertionError("check_modflow_inputs ran for a disabled section")

        monkeypatch.setattr("rubem.configuration.model_configuration.check_modflow_inputs", refuse)
        for source in self.formats(config):
            loaded = ModelConfiguration(source)
            assert [p.description for p in loaded.problems] == ["MODFLOW section is ignored."]

    @pytest.mark.unit
    def test_valid_inputs_load_without_problems(self, config):
        for source in self.formats(config):
            assert ModelConfiguration(source).problems == []

    @pytest.mark.unit
    @pytest.mark.parametrize("validate_input", [True, False])
    def test_an_enabled_section_with_missing_files_is_blocking(self, config, validate_input):
        config["MODFLOW"]["top"] = sibling(config, "absent.map")

        for source in self.formats(config):
            with pytest.raises(ConfigurationError, match="MODFLOW input file does not exist"):
                ModelConfiguration(source, validate_input=validate_input)

    @pytest.mark.unit
    def test_the_content_is_checked_only_with_validation(self, config):
        write_grid_map(config["MODFLOW"]["layers"][0]["boundary"], 7, nominal=True)

        for source in self.formats(config):
            assert ModelConfiguration(source, validate_input=False).problems == []
            with pytest.raises(ConfigurationError, match="MODFLOW boundary of layer 1"):
                ModelConfiguration(source)

    @pytest.mark.unit
    def test_the_minimum_root_depth_is_compared_with_the_configured_rootzone_depth(self, config):
        enable_root_depth(config, [(1, 200.0)])

        for source in self.formats(config):
            loaded = ModelConfiguration(source, allow_blocking_problems=True)
            assert [p.description for p in blocking(loaded.problems)] == [
                "Minimum root depth (Dpz_min) exceeds the rootzone depth (Zr)."
            ]
