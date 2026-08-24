import json
import logging
import os
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from rubem.configuration._json import read_json
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.model_configuration_file import ModelConfigurationFile, str_to_bool
from tests.helpers.synthetic import write_synthetic_dataset


class TestStrToBool:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        "value, expected",
        [
            (True, True),
            ("True", True),
            ("yes", True),
            ("1", True),
            ("t", True),
            ("false", False),
            ("no", False),
            ("", False),
        ],
    )
    def test_accepts_booleans_and_strings(self, value, expected):
        assert str_to_bool(value) is expected

    @pytest.mark.unit
    def test_rejects_other_types(self):
        with pytest.raises(ValueError, match="Invalid value for boolean conversion"):
            str_to_bool(1)


class TestReadJson:
    @pytest.mark.unit
    def test_duplicated_keys_are_reported_and_the_last_value_wins(self, tmp_path, caplog):
        file = tmp_path / "config.json"
        file.write_text('{"A": {"x": 1}, "A": {"x": 2}, "B": {"y": 1, "y": 2}}', encoding="utf8")

        with caplog.at_level(logging.WARNING):
            data = read_json(file)

        assert data == {"A": {"x": 2}, "B": {"y": 2}}
        assert "Duplicated key(s)" in caplog.text and "'A'" in caplog.text and "'y'" in caplog.text

    @pytest.mark.unit
    def test_a_callback_receives_the_duplicates(self, tmp_path):
        file = tmp_path / "config.json"
        file.write_text('{"A": 1, "A": 2}', encoding="utf8")
        seen = []

        read_json(file, on_duplicate=seen.append)

        assert seen == [["A"]]

    @pytest.mark.unit
    def test_missing_and_invalid_files(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_json(tmp_path / "absent.json")
        broken = tmp_path / "broken.json"
        broken.write_text("{", encoding="utf8")
        with pytest.raises(json.JSONDecodeError):
            read_json(broken)


class TestModelConfigurationFile:
    @pytest.mark.unit
    def test_the_synthetic_configuration_round_trips(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))

        file = ModelConfigurationFile.model_validate(config)
        canonical = file.to_dict()

        assert canonical["SIM_TIME"]["start"] == config["SIM_TIME"]["start"]
        assert canonical["TABLES"] == config["TABLES"]
        assert canonical["GENERATE_FILE"]["tss"] is True
        assert ModelConfigurationFile.model_validate(canonical) == file

    @pytest.mark.unit
    def test_alternative_spellings_are_accepted_and_written_canonically(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        tables = config["TABLES"]
        config["TABLES"] = {
            "rainy_days": tables["rainydays"],
            "a_i": tables["a_i"],
            "a_o": tables["a_o"],
            "a_s": tables["a_s"],
            "a_v": tables["a_v"],
            "manning": tables["manning"],
            "dg": tables["bulk_density"],
            "K_sat": tables["k_sat"],
            "T_fcap": tables["t_fcap"],
            "Tsat": tables["t_sat"],
            "Tw": tables["t_wp"],
            "Zr": tables["rootzone_depth"],
            "kcmin": tables["k_c_min"],
            "kc_max": tables["k_c_max"],
        }
        calibration = config["CALIBRATION"]
        config["CALIBRATION"] = {
            "alpha": calibration["alpha"],
            "beta": calibration["b"],
            "w1": calibration["w_1"],
            "w2": calibration["w_2"],
            "w3": calibration["w_3"],
            "rcd": calibration["rcd"],
            "f": calibration["f"],
            "alpha_gw": calibration["alpha_gw"],
            "x": calibration["x"],
        }
        soil = config["INITIAL_SOIL_CONDITIONS"]
        config["INITIAL_SOIL_CONDITIONS"] = {
            **soil,
            "T_ini": soil.pop("t_ini"),
            "S_sat_ini": soil.pop("s_sat_ini"),
        }

        canonical = ModelConfigurationFile.model_validate(config).to_dict()

        assert canonical["TABLES"] == tables
        assert canonical["CALIBRATION"] == calibration
        assert set(canonical["INITIAL_SOIL_CONDITIONS"]) == {
            "t_ini",
            "bfw_ini",
            "bfw_lim",
            "s_sat_ini",
        }

    @pytest.mark.unit
    def test_strings_are_accepted_for_numbers_and_booleans(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        config["GRID"] = {"grid": "500"}
        config["GENERATE_FILE"] = {**config["GENERATE_FILE"], "itp": "True", "tss": "false"}
        config["RASTER_FILE_FORMAT"] = {"map_raster_series": "yes", "tiff_raster_series": "0"}

        file = ModelConfigurationFile.model_validate(config)

        assert file.grid.grid == 500.0
        assert file.generate_file.itp is True and file.generate_file.tss is False
        assert (
            file.raster_file_format.map_raster_series
            and not file.raster_file_format.tiff_raster_series
        )
        assert file.raster_file_format.no_data_value == -9999

    @pytest.mark.unit
    def test_dates_use_the_legacy_format_and_alignment_is_optional(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        config["SIM_TIME"] = {"start": "01/03/2000", "end": "01/05/2000", "alignment": ""}

        file = ModelConfigurationFile.model_validate(config)

        assert file.sim_time.start == date(2000, 3, 1)
        assert file.sim_time.alignment is None
        assert file.to_dict()["SIM_TIME"] == {
            "start": "01/03/2000",
            "end": "01/05/2000",
            "alignment": None,
        }
        with pytest.raises(ValidationError, match="does not match format"):
            ModelConfigurationFile.model_validate(
                {**config, "SIM_TIME": {"start": "2000-03-01", "end": "01/05/2000"}}
            )

    @pytest.mark.unit
    def test_unknown_keys_are_reported_and_ignored(self, tmp_path, caplog):
        config = write_synthetic_dataset(str(tmp_path))
        config["GRID"] = {"grid": 500, "resolution": 30}
        config["EXTRA_SECTION"] = {"x": 1}

        with caplog.at_level(logging.WARNING):
            file = ModelConfigurationFile.model_validate(config)

        assert file.grid.grid == 500
        assert "Unknown key(s) in Grid ignored: ['resolution']" in caplog.text
        assert "EXTRA_SECTION" in caplog.text

    @pytest.mark.unit
    def test_missing_sections_and_keys_are_reported_by_name(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        del config["SIM_TIME"]["start"]
        del config["GRID"]

        with pytest.raises(ValidationError) as error:
            ModelConfigurationFile.model_validate(config)

        message = str(error.value)
        assert "SIM_TIME.start" in message and "GRID" in message

    @pytest.mark.unit
    def test_optional_rasters_accept_empty_strings(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        config["RASTERS"] = {**config["RASTERS"], "ldd": "", "samples": None}

        file = ModelConfigurationFile.model_validate(config)

        assert file.rasters.ldd is None and file.rasters.samples is None

    @pytest.mark.unit
    def test_relative_paths_are_anchored_on_the_base_directory(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        relative = json.loads(json.dumps(config))
        for section in ("DIRECTORIES", "RASTERS", "TABLES"):
            relative[section] = {
                key: (os.path.relpath(value, tmp_path) if value else value)
                for key, value in config[section].items()
            }

        anchored = ModelConfigurationFile.model_validate(relative).resolve_paths(tmp_path)

        assert Path(anchored.rasters.dem) == Path(config["RASTERS"]["dem"])
        assert Path(anchored.directories.output) == tmp_path / "out"
        absolute = ModelConfigurationFile.model_validate(config)
        assert absolute.resolve_paths(tmp_path / "elsewhere") == absolute
        assert absolute.resolve_paths(None) is absolute

    @pytest.mark.unit
    def test_from_json_reads_a_file(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        path = tmp_path / "config.json"
        path.write_text(json.dumps(config), encoding="utf8")

        assert ModelConfigurationFile.from_json(path) == ModelConfigurationFile.model_validate(
            config
        )


class TestLoaderAnchoring:
    @pytest.mark.unit
    def test_a_json_file_anchors_relative_paths_on_its_directory(self, tmp_path, monkeypatch):
        config = write_synthetic_dataset(str(tmp_path))
        relative = json.loads(json.dumps(config))
        for section in ("DIRECTORIES", "RASTERS", "TABLES"):
            relative[section] = {
                key: (os.path.relpath(value, tmp_path) if value else value)
                for key, value in config[section].items()
            }
        path = tmp_path / "config.json"
        path.write_text(json.dumps(relative), encoding="utf8")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        loaded = ModelConfiguration.load(path)

        assert Path(loaded.base_dir) == tmp_path
        assert Path(loaded.raster_files.dem) == Path(config["RASTERS"]["dem"])
        assert Path(loaded.output_directory.path) == Path(config["DIRECTORIES"]["output"])
        assert not any(problem.blocking for problem in loaded.problems)

    @pytest.mark.unit
    def test_a_dictionary_is_anchored_only_when_asked(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        relative = json.loads(json.dumps(config))
        relative["RASTERS"]["dem"] = os.path.relpath(config["RASTERS"]["dem"], tmp_path)

        with pytest.raises(FileNotFoundError):
            ModelConfiguration(relative, validate_input=True)
        loaded = ModelConfiguration.load(relative, base_dir=tmp_path)
        assert Path(loaded.raster_files.dem) == Path(config["RASTERS"]["dem"])

    @pytest.mark.unit
    def test_the_file_model_is_exposed(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))

        loaded = ModelConfiguration(config, validate_input=False)

        assert isinstance(loaded.file, ModelConfigurationFile)
        assert loaded.file.to_dict()["GRID"] == {"grid": 500.0}
        assert loaded.base_dir is None
