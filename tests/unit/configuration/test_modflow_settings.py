"""The optional MODFLOW section: schema, layer numbering and wiring in both formats."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rubem.cli import main
from rubem.configuration.migrate import migrate_legacy_file
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.model_configuration_file import ModelConfigurationFile
from rubem.configuration.model_configuration_file_v1 import ModelConfigurationFileV1
from rubem.configuration.modflow_configuration import ModflowSettings
from tests.helpers.synthetic import write_synthetic_dataset


def layer(name, bottom, head, laytype=2, **overrides):
    """One layer of the section, with every file named after the layer."""
    return {
        "name": name,
        "bottom": bottom,
        "initial_head": head,
        "boundary": "modflow/bound.map",
        "laytype": laytype,
        "horizontal_conductivity": {
            "map": f"modflow/kh_classes_{name}.map",
            "table": f"modflow/kh_{name}.tbl",
        },
        "vertical_conductivity": f"modflow/kv_{name}.map",
        "specific_yield": 0.15,
        "specific_storage": 1e-6,
        **overrides,
    }


def section(**overrides):
    """The target configuration of the plan: three layers listed top down."""
    data = {
        "enabled": True,
        "top": "modflow/top_model.map",
        "layers": [
            layer("upper", "modflow/botton3.map", "modflow/head3.map", laytype=1),
            layer("middle", "modflow/botton2.map", "modflow/head2.map"),
            layer("lower", "modflow/botton.map", "modflow/head1.map"),
        ],
        "dis": {"nstp": 5, "tsmult": 1.0, "steady_state": False},
        "solver": {
            "mxiter": 2000,
            "iter1": 20,
            "npcond": 1,
            "hclose": 5.0,
            "rclose": 3.0,
            "relax": 1.0,
            "nbpol": 2,
            "damp": 0.5,
        },
        "wetting": {
            "enabled": True,
            "map": "modflow/wet.map",
            "layers": [1],
            "wetfct": 1.0,
            "iwetit": 3,
            "ihdwet": 0,
        },
        "river": {
            "enabled": True,
            "entries": [
                {
                    "layers": [1],
                    "stage": "modflow/riv_stage.map",
                    "bottom": "modflow/riv_bot.map",
                    "conductance": 0.387,
                    "mask": "modflow/riv_cond.map",
                }
            ],
        },
        "ghb": {
            "enabled": True,
            "entries": [
                {
                    "layers": [1, 2, 3],
                    "head": "modflow/ghb_head.map",
                    "conductance": "modflow/ghb_cond.map",
                }
            ],
        },
        "drain": {"enabled": False, "entries": []},
        "coupling": {
            "dynamic_root_depth": {
                "enabled": False,
                "minimum_depth_table": None,
                "water_table": {"method": "highest_active_head", "layer": None},
            }
        },
        "output": {
            "heads": True,
            "river_leakage": True,
            "storage": False,
            "drain_flow": False,
            "root_depth": False,
        },
    }
    data.update(overrides)
    return data


def refused(data):
    """The validation message of ``data``."""
    with pytest.raises(ValidationError) as error:
        ModflowSettings.model_validate(data)
    return str(error.value)


class TestSchema:
    @pytest.mark.unit
    def test_the_target_configuration_validates(self):
        settings = ModflowSettings.model_validate(section())

        assert settings.enabled is True
        assert [item.name for item in settings.layers] == ["upper", "middle", "lower"]
        assert settings.layers[0].horizontal_conductivity.table == "modflow/kh_upper.tbl"
        assert settings.river.entries[0].conductance == 0.387
        assert settings.ghb.entries[0].layers == [1, 2, 3]
        assert settings.dis.steady_state is False

    @pytest.mark.unit
    def test_the_defaults_are_the_scientist_values(self):
        settings = ModflowSettings()

        assert settings.enabled is False
        assert settings.top is None and settings.layers == []
        assert (settings.dis.nstp, settings.dis.tsmult, settings.dis.steady_state) == (
            5,
            1.0,
            False,
        )
        solver = settings.solver
        assert (solver.mxiter, solver.iter1, solver.npcond, solver.nbpol) == (2000, 20, 1, 2)
        assert (solver.hclose, solver.rclose, solver.relax, solver.damp) == (5.0, 3.0, 1.0, 0.5)
        assert settings.wetting.enabled is False
        assert (settings.wetting.wetfct, settings.wetting.iwetit, settings.wetting.ihdwet) == (
            1.0,
            3,
            0,
        )
        assert not (settings.river.enabled or settings.ghb.enabled or settings.drain.enabled)
        assert settings.coupling.dynamic_root_depth.enabled is False
        output = settings.output
        assert (output.heads, output.river_leakage) == (True, True)
        assert not (output.storage or output.drain_flow or output.root_depth)

    @pytest.mark.unit
    @pytest.mark.parametrize("flag, expected", [(1, True), (0, False)])
    def test_enabled_is_a_boolean_that_accepts_one_and_zero(self, flag, expected):
        data = section(enabled=flag)
        data["wetting"]["enabled"] = flag
        data["river"]["enabled"] = 1

        settings = ModflowSettings.model_validate(data)

        assert settings.enabled is expected
        assert settings.wetting.enabled is expected
        assert settings.river.enabled is True

    @pytest.mark.unit
    def test_the_settings_are_frozen(self):
        settings = ModflowSettings.model_validate(section())

        with pytest.raises(ValidationError):
            settings.enabled = False

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "path, key",
        [
            ((), "wells"),
            ((), "recharge"),
            ((), "bottom"),
            (("dis",), "time_unit"),
            (("dis",), "length_unit"),
            (("solver",), "type"),
            (("solver",), "fail_on_non_convergence"),
            (("coupling",), "baseflow_from_river_leakage"),
            (("wetting",), "source_boundary_layer"),
            (("wetting",), "multiplier"),
            (("layers", 0), "top"),
            (("river",), "layers"),
        ],
    )
    def test_the_keys_the_prototype_had_are_refused_by_name(self, path, key):
        data = section()
        target = data
        for step in path:
            target = target[step]
        target[key] = 1

        assert key in refused(data)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "laytype", [0, 1, 2, 3, 10, 11, 12, 13, 20, 21, 22, 23, 30, 31, 32, 33]
    )
    def test_every_bcf_layer_type_is_accepted(self, laytype):
        data = section(enabled=False)
        data["layers"][0]["laytype"] = laytype

        assert ModflowSettings.model_validate(data).layers[0].laytype == laytype

    @pytest.mark.unit
    @pytest.mark.parametrize("laytype", [-1, 4, 9, 14, 40, 34])
    def test_other_layer_types_are_refused(self, laytype):
        data = section(enabled=False)
        data["layers"][0]["laytype"] = laytype

        assert "LAYTYPE" in refused(data)

    @pytest.mark.unit
    def test_a_layer_type_must_be_given(self):
        data = section()
        del data["layers"][1]["laytype"]

        assert "laytype" in refused(data)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("modflow/kh.map", "modflow/kh.map"),
            (0.5, 0.5),
            (2, 2.0),
            ({"map": "classes.map", "table": "kh.tbl"}, None),
        ],
    )
    def test_the_horizontal_conductivity_is_a_map_a_number_or_a_lookup(self, value, expected):
        data = section()
        data["layers"][1]["horizontal_conductivity"] = value

        conductivity = ModflowSettings.model_validate(data).layers[1].horizontal_conductivity

        if expected is None:
            assert (conductivity.map, conductivity.table) == ("classes.map", "kh.tbl")
        else:
            assert conductivity == expected

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "field", ["horizontal_conductivity", "vertical_conductivity", "specific_storage"]
    )
    @pytest.mark.parametrize("value", [-1.0, float("nan"), float("inf")])
    def test_a_numeric_property_must_be_finite_and_physical(self, field, value):
        data = section()
        data["layers"][1][field] = value

        refused(data)

    @pytest.mark.unit
    @pytest.mark.parametrize("field", ["horizontal_conductivity", "vertical_conductivity"])
    def test_a_numeric_conductivity_must_be_positive(self, field):
        data = section()
        data["layers"][1][field] = 0.0

        refused(data)

    @pytest.mark.unit
    @pytest.mark.parametrize("value", [-0.1, 1.5])
    def test_a_numeric_specific_yield_is_a_fraction(self, value):
        data = section()
        data["layers"][1]["specific_yield"] = value

        refused(data)

    @pytest.mark.unit
    def test_a_numeric_string_stays_a_path(self):
        data = section()
        data["layers"][1]["vertical_conductivity"] = "0.5"

        assert ModflowSettings.model_validate(data).layers[1].vertical_conductivity == "0.5"

    @pytest.mark.unit
    def test_an_empty_path_is_refused(self):
        data = section()
        data["layers"][1]["bottom"] = ""

        refused(data)

    @pytest.mark.unit
    @pytest.mark.parametrize("value", [0, -1.0])
    def test_a_numeric_river_conductance_must_be_positive(self, value):
        data = section()
        data["river"]["entries"][0]["conductance"] = value

        refused(data)


class TestEnabledRules:
    """Cross-field rules, checked only when the section is enabled."""

    @pytest.mark.unit
    def test_a_disabled_section_is_not_checked(self):
        data = section(enabled=False, top=None)
        data["river"]["enabled"] = False
        data["layers"][1]["laytype"] = 1
        data["wetting"]["layers"] = [9]

        assert ModflowSettings.model_validate(data).enabled is False

    @pytest.mark.unit
    def test_an_empty_disabled_section_is_accepted(self):
        assert ModflowSettings.model_validate({"enabled": False}).layers == []

    @pytest.mark.unit
    def test_the_model_top_is_required(self):
        assert "'top'" in refused(section(top=None))

    @pytest.mark.unit
    def test_at_least_one_layer_is_required(self):
        assert "at least one layer" in refused(section(layers=[]))

    @pytest.mark.unit
    def test_layer_names_are_unique(self):
        data = section()
        data["layers"][2]["name"] = "upper"

        assert "'upper'" in refused(data)

    @pytest.mark.unit
    def test_the_river_package_is_required(self):
        data = section()
        data["river"]["enabled"] = False

        assert "river" in refused(data)

    @pytest.mark.unit
    @pytest.mark.parametrize("package", ["river", "ghb", "drain"])
    def test_an_enabled_package_needs_an_entry(self, package):
        data = section()
        data[package] = {"enabled": True, "entries": []}

        assert f"{package}.enabled" in refused(data)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "package, entry",
        [
            ("river", {"stage": "s.map", "bottom": "b.map", "conductance": "c.map"}),
            ("ghb", {"head": "h.map", "conductance": "c.map"}),
            ("drain", {"elevation": "e.map", "conductance": "c.map"}),
        ],
    )
    @pytest.mark.parametrize("number", [4, 7])
    def test_a_package_layer_must_exist(self, package, entry, number):
        data = section()
        data[package] = {"enabled": True, "entries": [{**entry, "layers": [number]}]}

        message = refused(data)

        assert f"layer {number}" in message and "1-3" in message

    @pytest.mark.unit
    @pytest.mark.parametrize("number", [0, -1])
    def test_a_layer_number_is_positive(self, number):
        data = section()
        data["ghb"]["entries"][0]["layers"] = [number]

        refused(data)

    @pytest.mark.unit
    def test_an_entry_lists_at_least_one_layer(self):
        data = section()
        data["ghb"]["entries"][0]["layers"] = []

        refused(data)

    @pytest.mark.unit
    def test_a_layer_appears_once_in_an_entry(self):
        data = section()
        data["ghb"]["entries"][0]["layers"] = [1, 2, 2]

        assert "ghb" in refused(data)

    @pytest.mark.unit
    def test_a_layer_appears_in_one_entry_per_package(self):
        data = section()
        first = data["river"]["entries"][0]
        data["river"]["entries"].append({**first, "layers": [2, 1]})

        message = refused(data)

        assert "river" in message and "layer 1" in message

    @pytest.mark.unit
    def test_the_same_layer_may_carry_several_packages(self):
        data = section()
        data["drain"] = {
            "enabled": True,
            "entries": [{"layers": [1], "elevation": "e.map", "conductance": "c.map"}],
        }

        assert ModflowSettings.model_validate(data).drain.entries[0].layers == [1]

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "laycon, missing",
        [
            (0, "specific_storage"),
            (1, "specific_yield"),
            (2, "specific_storage"),
            (2, "specific_yield"),
            (3, "specific_storage"),
            (3, "specific_yield"),
        ],
    )
    def test_a_transient_run_needs_the_storage_of_the_layer_type(self, laycon, missing):
        data = section()
        data["wetting"]["enabled"] = False
        target = data["layers"][0]
        target["laytype"] = 10 + laycon
        target[missing] = None

        message = refused(data)

        assert missing in message and f"LAYCON {laycon}" in message and "layer 1" in message

    @pytest.mark.unit
    @pytest.mark.parametrize("laycon, unused", [(0, "specific_yield"), (1, "specific_storage")])
    def test_a_transient_run_does_not_need_the_other_storage(self, laycon, unused):
        data = section()
        data["wetting"]["enabled"] = False
        data["layers"][0]["laytype"] = laycon
        data["layers"][0][unused] = None

        assert ModflowSettings.model_validate(data).layers[0].laytype == laycon

    @pytest.mark.unit
    def test_a_steady_state_run_needs_no_storage(self):
        data = section(dis={"steady_state": True})
        for item in data["layers"]:
            item["specific_yield"] = None
            item["specific_storage"] = None

        assert ModflowSettings.model_validate(data).dis.steady_state is True

    @pytest.mark.unit
    @pytest.mark.parametrize("laytype", [1, 11, 21, 31])
    def test_laycon_1_is_valid_only_on_the_top_layer(self, laytype):
        data = section()
        data["layers"][2]["laytype"] = laytype

        message = refused(data)

        assert "layer 3" in message and "LAYCON 1" in message

    @pytest.mark.unit
    def test_wetting_on_a_layer_that_is_not_laycon_1_or_3_is_refused(self):
        data = section()
        data["wetting"]["layers"] = [1, 2, 3]

        message = refused(data)

        assert "layer 2" in message and "LAYCON 2" in message
        assert "layer 3" in message

    @pytest.mark.unit
    def test_wetting_on_every_layer_needs_laycon_1_or_3(self):
        data = section()
        data["layers"][1]["laytype"] = 3
        data["layers"][2]["laytype"] = 33
        data["wetting"]["layers"] = [1, 2, 3]

        assert ModflowSettings.model_validate(data).wetting_layers() == [1, 2, 3]

    @pytest.mark.unit
    def test_wetting_layers_must_exist(self):
        data = section()
        data["wetting"]["layers"] = [1, 5]

        assert "layer 5" in refused(data)

    @pytest.mark.unit
    def test_a_wetting_layer_is_listed_once(self):
        data = section()
        data["wetting"]["layers"] = [1, 1]

        assert "wetting" in refused(data)

    @pytest.mark.unit
    def test_wetting_without_layers_applies_to_every_laycon_1_or_3_layer(self):
        data = section()
        data["layers"][2]["laytype"] = 13
        data["wetting"]["layers"] = None

        assert ModflowSettings.model_validate(data).wetting_layers() == [1, 3]

    @pytest.mark.unit
    def test_wetting_without_layers_needs_a_laycon_1_or_3_layer(self):
        data = section()
        data["layers"][0]["laytype"] = 2
        data["wetting"]["layers"] = None

        assert "LAYCON 1 or 3" in refused(data)

    @pytest.mark.unit
    def test_wetting_needs_its_map(self):
        data = section()
        data["wetting"]["map"] = None

        assert "wetting.map" in refused(data)

    @pytest.mark.unit
    def test_no_wetting_layer_when_wetting_is_disabled(self):
        data = section()
        data["wetting"]["enabled"] = False

        assert ModflowSettings.model_validate(data).wetting_layers() == []

    @pytest.mark.unit
    def test_a_numeric_river_conductance_needs_a_mask(self):
        data = section()
        data["river"]["entries"][0]["mask"] = None

        assert "mask" in refused(data)

    @pytest.mark.unit
    def test_a_river_conductance_map_needs_no_mask(self):
        data = section()
        entry = data["river"]["entries"][0]
        entry["conductance"] = "modflow/riv_cond.map"
        entry["mask"] = None

        settings = ModflowSettings.model_validate(data)

        assert settings.river.entries[0].conductance == "modflow/riv_cond.map"

    @pytest.mark.unit
    def test_the_root_depth_coupling_needs_its_minimum_depth_table(self):
        data = section()
        data["coupling"]["dynamic_root_depth"]["enabled"] = True

        assert "minimum_depth_table" in refused(data)

    @pytest.mark.unit
    @pytest.mark.parametrize("number, valid", [(None, False), (2, True), (4, False)])
    def test_the_water_table_layer_method_needs_a_layer_in_range(self, number, valid):
        data = section()
        data["coupling"]["dynamic_root_depth"] = {
            "enabled": True,
            "minimum_depth_table": "txt/Dpz_min.txt",
            "water_table": {"method": "layer", "layer": number},
        }

        if valid:
            settings = ModflowSettings.model_validate(data)
            assert settings.coupling.dynamic_root_depth.water_table.layer == number
        else:
            assert "water_table" in refused(data)

    @pytest.mark.unit
    def test_a_water_table_layer_is_only_given_with_the_layer_method(self):
        data = section()
        data["coupling"]["dynamic_root_depth"] = {
            "enabled": True,
            "minimum_depth_table": "txt/Dpz_min.txt",
            "water_table": {"method": "highest_active_head", "layer": 2},
        }

        assert "water_table.layer" in refused(data)

    @pytest.mark.unit
    def test_the_highest_unconfined_method_needs_a_convertible_layer(self):
        data = section(dis={"steady_state": True})
        data["wetting"]["enabled"] = False
        for item in data["layers"]:
            item["laytype"] = 0
        data["coupling"]["dynamic_root_depth"] = {
            "enabled": True,
            "minimum_depth_table": "txt/Dpz_min.txt",
            "water_table": {"method": "highest_unconfined"},
        }

        assert "highest_unconfined" in refused(data)

    @pytest.mark.unit
    def test_every_violation_is_reported_at_once(self):
        data = section(top=None)
        data["layers"][2]["name"] = "upper"
        data["river"]["enabled"] = False

        message = refused(data)

        assert "'top'" in message and "'upper'" in message and "river" in message


class TestLayerNumbering:
    """User layers are numbered top down (MODFLOW), PCRaster numbers them bottom up."""

    @pytest.mark.unit
    @pytest.mark.parametrize("user, pcraster", [(1, 3), (2, 2), (3, 1)])
    def test_the_top_layer_is_the_last_pcraster_layer(self, user, pcraster):
        settings = ModflowSettings.model_validate(section())

        assert settings.pcraster_layer(user) == pcraster
        assert settings.user_layer(pcraster) == user

    @pytest.mark.unit
    @pytest.mark.parametrize("number", [0, 4])
    def test_a_number_outside_the_layers_is_refused(self, number):
        settings = ModflowSettings.model_validate(section())

        with pytest.raises(ValueError, match="1-3"):
            settings.pcraster_layer(number)
        with pytest.raises(ValueError, match="1-3"):
            settings.user_layer(number)


class TestPaths:
    @pytest.mark.unit
    def test_every_relative_path_is_anchored_and_numbers_are_kept(self, tmp_path):
        data = section()
        data["layers"][1]["specific_yield"] = "modflow/sy.map"
        data["layers"][2]["horizontal_conductivity"] = 0.3
        data["drain"] = {
            "enabled": True,
            "entries": [{"layers": [2], "elevation": "drn/e.map", "conductance": "drn/c.map"}],
        }
        data["coupling"]["dynamic_root_depth"]["minimum_depth_table"] = "txt/Dpz_min.txt"

        anchored = ModflowSettings.model_validate(data).resolve_paths(tmp_path)

        def at(relative):
            return tmp_path / relative

        assert Path(anchored.top) == at("modflow/top_model.map")
        upper, middle, lower = anchored.layers
        assert Path(upper.bottom) == at("modflow/botton3.map")
        assert Path(upper.initial_head) == at("modflow/head3.map")
        assert Path(upper.boundary) == at("modflow/bound.map")
        assert Path(upper.horizontal_conductivity.map) == at("modflow/kh_classes_upper.map")
        assert Path(upper.horizontal_conductivity.table) == at("modflow/kh_upper.tbl")
        assert Path(upper.vertical_conductivity) == at("modflow/kv_upper.map")
        assert (upper.specific_yield, upper.specific_storage) == (0.15, 1e-6)
        assert Path(middle.specific_yield) == at("modflow/sy.map")
        assert lower.horizontal_conductivity == 0.3
        assert Path(anchored.wetting.map) == at("modflow/wet.map")
        river = anchored.river.entries[0]
        assert Path(river.stage) == at("modflow/riv_stage.map")
        assert Path(river.bottom) == at("modflow/riv_bot.map")
        assert Path(river.mask) == at("modflow/riv_cond.map")
        assert river.conductance == 0.387
        ghb = anchored.ghb.entries[0]
        assert (Path(ghb.head), Path(ghb.conductance)) == (
            at("modflow/ghb_head.map"),
            at("modflow/ghb_cond.map"),
        )
        drain = anchored.drain.entries[0]
        assert (Path(drain.elevation), Path(drain.conductance)) == (
            at("drn/e.map"),
            at("drn/c.map"),
        )
        table = anchored.coupling.dynamic_root_depth.minimum_depth_table
        assert Path(table) == at("txt/Dpz_min.txt")

    @pytest.mark.unit
    def test_absolute_paths_and_absent_files_are_kept(self, tmp_path):
        data = section()
        absolute = str(tmp_path / "elsewhere" / "top.map")
        data["top"] = absolute
        data["river"]["entries"][0]["conductance"] = "modflow/riv_cond.map"
        data["river"]["entries"][0]["mask"] = None

        anchored = ModflowSettings.model_validate(data).resolve_paths(tmp_path / "base")

        assert anchored.top == absolute
        assert anchored.river.entries[0].mask is None
        assert anchored.wetting.layers == [1]
        assert anchored.coupling.dynamic_root_depth.minimum_depth_table is None

    @pytest.mark.unit
    def test_no_base_directory_keeps_the_settings(self):
        settings = ModflowSettings.model_validate(section())

        assert settings.resolve_paths(None) is settings

    @pytest.mark.unit
    def test_the_names_and_methods_are_not_paths(self, tmp_path):
        anchored = ModflowSettings.model_validate(section()).resolve_paths(tmp_path)

        assert [item.name for item in anchored.layers] == ["upper", "middle", "lower"]
        assert anchored.coupling.dynamic_root_depth.water_table.method == "highest_active_head"

    @pytest.mark.unit
    def test_a_disabled_section_is_anchored_too(self, tmp_path):
        data = section(enabled=False)

        anchored = ModflowSettings.model_validate(data).resolve_paths(tmp_path)

        assert Path(anchored.top) == tmp_path / "modflow" / "top_model.map"
        assert anchored == ModflowSettings.model_validate(
            copy.deepcopy(anchored.model_dump(mode="json"))
        )


@pytest.fixture(name="config")
def config_fixture(tmp_path):
    """A legacy configuration of the synthetic dataset, with relative MODFLOW paths possible."""
    return write_synthetic_dataset(str(tmp_path))


def both_formats(config):
    """The legacy configuration and its format 1.0 document."""
    legacy = ModelConfigurationFile.model_validate(config)
    return (config, ModelConfigurationFileV1.from_legacy(legacy).to_dict())


class TestLegacyFile:
    @pytest.mark.unit
    def test_the_section_is_absent_by_default_and_written_as_null(self, config):
        file = ModelConfigurationFile.model_validate(config)

        assert file.modflow is None
        assert file.to_dict()["MODFLOW"] is None
        assert ModelConfigurationFile.model_validate(file.to_dict()) == file

    @pytest.mark.unit
    def test_the_section_round_trips(self, config):
        config["MODFLOW"] = section()

        file = ModelConfigurationFile.model_validate(config)

        assert file.modflow == ModflowSettings.model_validate(section())
        assert file.to_dict()["MODFLOW"]["layers"][0]["name"] == "upper"
        assert ModelConfigurationFile.model_validate(file.to_dict()) == file

    @pytest.mark.unit
    def test_the_lower_case_spelling_is_accepted(self, config):
        config["modflow"] = section()

        assert ModelConfigurationFile.model_validate(config).modflow.enabled is True

    @pytest.mark.unit
    @pytest.mark.parametrize("flag, expected", [(1, True), (0, False)])
    def test_enabled_accepts_one_and_zero(self, config, flag, expected):
        config["MODFLOW"] = section(enabled=flag)

        assert ModelConfigurationFile.model_validate(config).modflow.enabled is expected

    @pytest.mark.unit
    def test_an_unknown_key_of_the_section_is_refused(self, config):
        config["MODFLOW"] = section(wells={"enabled": 0})

        with pytest.raises(ValidationError, match="wells"):
            ModelConfigurationFile.model_validate(config)

    @pytest.mark.unit
    def test_the_section_paths_are_anchored(self, config, tmp_path):
        config["MODFLOW"] = section()

        anchored = ModelConfigurationFile.model_validate(config).resolve_paths(tmp_path)

        assert Path(anchored.modflow.top) == tmp_path / "modflow" / "top_model.map"
        lookup = anchored.modflow.layers[2].horizontal_conductivity
        assert Path(lookup.table) == tmp_path / "modflow" / "kh_lower.tbl"

    @pytest.mark.unit
    def test_anchoring_without_the_section_keeps_it_absent(self, config, tmp_path):
        anchored = ModelConfigurationFile.model_validate(config).resolve_paths(tmp_path)

        assert anchored.modflow is None


class TestFormat10File:
    @pytest.mark.unit
    def test_the_section_is_left_out_when_absent(self, config):
        document = both_formats(config)[1]

        assert "modflow" not in document
        assert ModelConfigurationFileV1.model_validate(document).modflow is None

    @pytest.mark.unit
    def test_the_section_follows_the_conversion_from_and_to_legacy(self, config):
        config["MODFLOW"] = section()
        legacy = ModelConfigurationFile.model_validate(config)

        v1 = ModelConfigurationFileV1.from_legacy(legacy)

        assert v1.modflow == legacy.modflow
        assert v1.to_legacy() == legacy

    @pytest.mark.unit
    def test_the_document_round_trips_with_unset_keys(self, config):
        config["MODFLOW"] = section()
        document = both_formats(config)[1]

        model = ModelConfigurationFileV1.model_validate(document)

        assert "minimum_depth_table" not in document["modflow"]["coupling"]["dynamic_root_depth"]
        assert model.modflow.coupling.dynamic_root_depth.minimum_depth_table is None
        assert ModelConfigurationFileV1.model_validate(model.to_dict()) == model

    @pytest.mark.unit
    @pytest.mark.parametrize("flag, expected", [(1, True), (0, False)])
    def test_enabled_accepts_one_and_zero(self, config, flag, expected):
        document = both_formats(config)[1]
        document["modflow"] = section(enabled=flag)

        assert ModelConfigurationFileV1.model_validate(document).modflow.enabled is expected

    @pytest.mark.unit
    def test_an_unknown_key_of_the_section_is_refused(self, config):
        document = both_formats(config)[1]
        document["modflow"] = section(recharge={"option": 3})

        with pytest.raises(ValidationError, match="recharge"):
            ModelConfigurationFileV1.model_validate(document)

    @pytest.mark.unit
    def test_the_section_paths_are_anchored(self, config, tmp_path):
        document = both_formats(config)[1]
        document["modflow"] = section()

        anchored = ModelConfigurationFileV1.model_validate(document).resolve_paths(tmp_path)

        assert Path(anchored.modflow.river.entries[0].stage) == (
            tmp_path / "modflow" / "riv_stage.map"
        )


class TestModelConfiguration:
    @pytest.mark.unit
    def test_an_absent_section_disables_the_coupling_silently(self, config):
        for source in both_formats(config):
            loaded = ModelConfiguration(source, validate_input=False)

            assert loaded.modflow is None
            assert loaded.modflow_enabled is False
            assert not [p for p in loaded.problems if "MODFLOW" in p.description]

    @pytest.mark.unit
    def test_an_enabled_section_reaches_the_configuration_anchored(self, config, tmp_path):
        """The section names files that do not exist: only their absence is reported."""
        config["MODFLOW"] = section()

        for source in both_formats(config):
            loaded = ModelConfiguration(
                source, validate_input=False, base_dir=tmp_path, allow_blocking_problems=True
            )

            assert loaded.modflow_enabled is True
            assert Path(loaded.modflow.top) == tmp_path / "modflow" / "top_model.map"
            modflow = [p for p in loaded.problems if "MODFLOW" in p.description]
            assert {p.description for p in modflow} == {"MODFLOW input file does not exist."}
            assert Path(modflow[0].file) == tmp_path / "modflow" / "top_model.map"

    @pytest.mark.unit
    @pytest.mark.parametrize("validate_input", [True, False])
    def test_a_disabled_section_is_reported_as_ignored(self, config, validate_input):
        config["MODFLOW"] = section(enabled=False)

        for source in both_formats(config):
            loaded = ModelConfiguration(source, validate_input=validate_input)

            assert loaded.modflow_enabled is False
            assert loaded.modflow.enabled is False
            ignored = [p for p in loaded.problems if "MODFLOW section is ignored" in p.description]
            assert len(ignored) == 1 and not ignored[0].blocking
            assert "enabled" in ignored[0].reason


class TestCommands:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        "arguments, key",
        [
            (["config", "schema"], "modflow"),
            (["config", "schema", "--format", "legacy"], "MODFLOW"),
        ],
    )
    def test_the_schema_describes_the_section(self, capsys, restore_logging, arguments, key):
        main(arguments)

        schema = json.loads(capsys.readouterr().out)
        assert key in schema["properties"]
        assert "ModflowSettings" in schema["$defs"]
        assert "ModflowLayer" in schema["$defs"]
        assert not [name for name in schema["$defs"] if "__" in name]

    @pytest.mark.unit
    def test_migration_carries_the_section_with_paths_relative_to_the_destination(
        self, config, tmp_path
    ):
        data = section()
        data["layers"][1]["specific_yield"] = "modflow/sy.map"
        config["MODFLOW"] = data
        source = tmp_path / "legacy.json"
        source.write_text(json.dumps(config), encoding="utf8")

        written = migrate_legacy_file(source, tmp_path / "migrated" / "config-v1.json")

        document = json.loads(Path(written).read_text(encoding="utf8"))
        modflow = document["modflow"]
        assert Path(modflow["top"]) == Path("..") / "modflow" / "top_model.map"
        lookup = modflow["layers"][0]["horizontal_conductivity"]
        assert Path(lookup["table"]) == Path("..") / "modflow" / "kh_upper.tbl"
        assert Path(modflow["layers"][1]["specific_yield"]) == Path("..") / "modflow" / "sy.map"
        assert modflow["layers"][0]["specific_yield"] == 0.15
        assert modflow["river"]["entries"][0]["conductance"] == 0.387
        migrated = ModelConfigurationFileV1.from_json(written).resolve_paths(Path(written).parent)
        assert Path(migrated.modflow.top).resolve() == (tmp_path / "modflow" / "top_model.map")
