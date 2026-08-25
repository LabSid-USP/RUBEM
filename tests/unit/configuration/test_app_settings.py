import json
import os
import sys

import pytest
from pydantic import ValidationError

from rubem.configuration.app_settings import (
    DEFAULT_SETTINGS_FILE,
    PACKAGE_DIR,
    AppSettings,
    ValueRange,
    ValueRanges,
)


def packaged_settings():
    with open(DEFAULT_SETTINGS_FILE, encoding="utf8") as file:
        return json.load(file)


class TestValueRange:
    @pytest.mark.unit
    def test_infinities_become_the_largest_finite_floats(self):
        valid_range = ValueRange(min="-Infinity", max="Infinity")

        assert valid_range.min == -sys.float_info.max
        assert valid_range.max == sys.float_info.max

    @pytest.mark.unit
    @pytest.mark.parametrize("payload", [{"min": 1, "max": 1}, {"min": 2, "max": 1}])
    def test_max_must_exceed_min(self, payload):
        with pytest.raises(ValidationError, match="greater than 'min'"):
            ValueRange(**payload)

    @pytest.mark.unit
    @pytest.mark.parametrize("value", ["nan", "inf", "one", True, None])
    def test_rejects_non_numeric_bounds(self, value):
        with pytest.raises(ValidationError):
            ValueRange(min=value, max=1.0)

    @pytest.mark.unit
    def test_ranges_are_frozen_and_reject_unknown_keys(self):
        with pytest.raises(ValidationError):
            ValueRange(min=0, max=1, mean=0.5)
        with pytest.raises(ValidationError):
            ValueRanges(rasters={}, variables={}, other={})


class TestValueRangesMappingsAreReadOnly:
    @pytest.mark.unit
    def test_the_cached_default_cannot_be_mutated_through_its_mappings(self):
        settings = AppSettings.default()

        with pytest.raises(TypeError):
            settings.value_ranges.rasters["ndvi"] = ValueRange(min=0, max=1)
        with pytest.raises(TypeError):
            del settings.value_ranges.rasters["ndvi"]
        assert not hasattr(settings.value_ranges.variables, "clear")

    @pytest.mark.unit
    def test_the_mappings_still_behave_like_dicts(self):
        ranges = ValueRanges(
            rasters={"ndvi": {"min": -1, "max": 1}}, variables={"alpha": {"min": 0, "max": 1}}
        )

        assert ranges.rasters["ndvi"].max == 1
        assert set(ranges.rasters) == {"ndvi"}
        assert len(ranges.variables) == 1
        assert ranges.model_dump()["rasters"]["ndvi"] == {"min": -1.0, "max": 1.0}


class TestDefaultSettings:
    @pytest.mark.unit
    def test_the_packaged_file_is_the_default(self, monkeypatch):
        monkeypatch.delenv("PYTHON_ENVIRONMENT", raising=False)

        assert AppSettings.default_file() == DEFAULT_SETTINGS_FILE.absolute()

    @pytest.mark.unit
    def test_default_settings_match_the_packaged_file(self, monkeypatch):
        monkeypatch.delenv("PYTHON_ENVIRONMENT", raising=False)
        expected = packaged_settings()

        settings = AppSettings.default()

        assert (
            settings.get_setting("value_ranges")
            == ValueRanges.model_validate(expected["value_ranges"]).model_dump()
        )
        assert settings.i18n.language == expected["i18n"]["language"]
        assert settings.logging == expected["logging"]

    @pytest.mark.unit
    def test_default_is_read_once_per_file(self, monkeypatch):
        monkeypatch.delenv("PYTHON_ENVIRONMENT", raising=False)

        assert AppSettings.default() is AppSettings.default()

    @pytest.mark.unit
    def test_get_setting_returns_none_for_unknown_keys(self):
        assert AppSettings.default().get_setting("this_key_does_not_exist") is None


class TestLoad:
    @pytest.mark.unit
    def test_loads_an_explicit_file(self, tmp_path):
        custom = tmp_path / "custom.json"
        payload = packaged_settings()
        payload["i18n"] = {"language": "pt_BR"}
        custom.write_text(json.dumps(payload), encoding="utf8")

        settings = AppSettings.load(custom)

        assert settings.i18n.language == "pt_BR"
        assert settings.value_ranges.variables["alpha"].max == 10.0

    @pytest.mark.unit
    def test_a_missing_file_names_its_absolute_path(self, tmp_path):
        missing = tmp_path / "absent.json"

        with pytest.raises(FileNotFoundError, match="absent.json"):
            AppSettings.load(missing)

    @pytest.mark.unit
    def test_unknown_top_level_keys_are_ignored_and_ranges_are_required(self, tmp_path):
        custom = tmp_path / "custom.json"
        custom.write_text(json.dumps({"value_ranges": {"rasters": {}, "variables": {}}, "x": 1}))
        assert AppSettings.load(custom).get_setting("x") is None

        custom.write_text(json.dumps({"i18n": {"language": "en_US"}}))
        with pytest.raises(ValidationError, match="value_ranges"):
            AppSettings.load(custom)

    @pytest.mark.unit
    def test_settings_are_frozen(self):
        settings = AppSettings.default()

        with pytest.raises(ValidationError):
            settings.logging = {"version": 1}


class TestEnvironmentSelection:
    @pytest.mark.unit
    def test_the_packaged_environment_file_is_selected(self, monkeypatch):
        monkeypatch.setenv("PYTHON_ENVIRONMENT", "Development")

        assert (
            AppSettings.default_file() == (PACKAGE_DIR / "appsettings.Development.json").absolute()
        )
        with open(PACKAGE_DIR / "appsettings.Development.json", encoding="utf8") as file:
            expected = json.load(file)
        assert AppSettings.default().logging == expected["logging"]

    @pytest.mark.unit
    def test_a_file_in_the_working_directory_is_selected(self, monkeypatch, tmp_path):
        payload = packaged_settings()
        payload["i18n"] = {"language": "pt_BR"}
        (tmp_path / "appsettings.CustomEnv.json").write_text(json.dumps(payload), encoding="utf8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PYTHON_ENVIRONMENT", "CustomEnv")

        assert AppSettings.default_file() == (tmp_path / "appsettings.CustomEnv.json").absolute()
        assert AppSettings.default().i18n.language == "pt_BR"

    @pytest.mark.unit
    @pytest.mark.parametrize("environment", ["NoSuchEnvironment", ""])
    def test_missing_or_empty_environments_fall_back_to_the_packaged_file(
        self, monkeypatch, tmp_path, environment
    ):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PYTHON_ENVIRONMENT", environment)

        assert AppSettings.default_file() == DEFAULT_SETTINGS_FILE.absolute()

    @pytest.mark.unit
    def test_an_empty_environment_file_is_skipped(self, monkeypatch, tmp_path):
        (tmp_path / "appsettings.EmptyEnv.json").write_text("", encoding="utf8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PYTHON_ENVIRONMENT", "EmptyEnv")

        assert AppSettings.default_file() == DEFAULT_SETTINGS_FILE.absolute()

    @pytest.mark.unit
    def test_the_selection_happens_at_call_time(self, monkeypatch, tmp_path):
        """No module reload is needed: the environment is read on every call."""
        monkeypatch.delenv("PYTHON_ENVIRONMENT", raising=False)
        before = AppSettings.default_file()
        monkeypatch.setenv("PYTHON_ENVIRONMENT", "Development")

        assert AppSettings.default_file() != before
        assert os.path.basename(AppSettings.default_file()) == "appsettings.Development.json"
