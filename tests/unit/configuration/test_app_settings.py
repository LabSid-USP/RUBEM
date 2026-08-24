import importlib
import json
import os
import pathlib
import re

import pytest

import rubem.configuration.app_settings as app_settings_module
from rubem.configuration.app_settings import AppSettings

# The module builds its default path with ``os.path.abspath``, which keeps
# symbolic links; the expectations are built the same way.
PACKAGE_DIR = pathlib.Path(os.path.abspath(app_settings_module.__file__)).parent.parent
DEFAULT_APPSETTINGS_FILE = PACKAGE_DIR / "appsettings.json"


@pytest.fixture
def env_reload(monkeypatch):
    """Set PYTHON_ENVIRONMENT/cwd, reload the module, then restore both and reload again.

    The env/cwd are undone immediately in the finalizer (rather than left to monkeypatch's
    own teardown) so the module is reloaded back to its default state before the test ends.
    """

    def _set(env_value=None, cwd=None):
        if cwd is not None:
            monkeypatch.chdir(cwd)
        if env_value is None:
            monkeypatch.delenv("PYTHON_ENVIRONMENT", raising=False)
        else:
            monkeypatch.setenv("PYTHON_ENVIRONMENT", env_value)
        return importlib.reload(app_settings_module)

    yield _set

    monkeypatch.undo()
    importlib.reload(app_settings_module)


@pytest.fixture
def restore_default_settings():
    yield
    AppSettings().load()


class TestSingleton:
    @pytest.mark.unit
    def test_two_constructions_return_the_same_instance(self):
        assert AppSettings() is AppSettings()

    @pytest.mark.unit
    def test_second_construction_does_not_reload_settings(self, restore_default_settings):
        first = AppSettings()
        first.settings = {"marker": "sentinel"}

        second = AppSettings()

        assert second is first
        assert second.settings == {"marker": "sentinel"}


class TestDefaultFile:
    @pytest.mark.unit
    def test_default_file_is_the_packaged_appsettings_json(self):
        assert AppSettings._AppSettings__default_appsettings_file == str(DEFAULT_APPSETTINGS_FILE)

    @pytest.mark.unit
    def test_default_settings_match_the_packaged_file(self):
        with open(DEFAULT_APPSETTINGS_FILE, encoding="utf8") as file:
            expected = json.load(file)

        assert AppSettings().get_setting("value_ranges") == expected["value_ranges"]


class TestLoad:
    @pytest.mark.unit
    def test_load_explicit_file_replaces_settings(self, tmp_path, restore_default_settings):
        custom_file = tmp_path / "custom_appsettings.json"
        custom_file.write_text(json.dumps({"value_ranges": {"custom": 1}}), encoding="utf8")

        AppSettings().load(str(custom_file))

        assert AppSettings().get_setting("value_ranges") == {"custom": 1}

    @pytest.mark.unit
    def test_load_accepts_a_pathlib_path(self, tmp_path, restore_default_settings):
        custom_file = tmp_path / "custom_appsettings.json"
        custom_file.write_text(json.dumps({"value_ranges": {"from_path": True}}), encoding="utf8")

        AppSettings().load(custom_file)

        assert AppSettings().get_setting("value_ranges") == {"from_path": True}

    @pytest.mark.unit
    def test_load_missing_file_raises_with_the_absolute_path(self, tmp_path):
        missing_file = tmp_path / "absent.json"

        with pytest.raises(FileNotFoundError, match=re.escape(str(missing_file))):
            AppSettings().load(missing_file)


class TestGetSetting:
    @pytest.mark.unit
    def test_unknown_key_returns_none(self):
        assert AppSettings().get_setting("this_key_does_not_exist") is None


class TestEnvironmentSelection:
    @pytest.mark.unit
    def test_development_environment_selects_the_packaged_development_file(self, env_reload):
        module = env_reload("Development")
        expected_file = PACKAGE_DIR / "appsettings.Development.json"

        assert module.AppSettings._AppSettings__default_appsettings_file == str(expected_file)
        with open(expected_file, encoding="utf8") as file:
            expected_settings = json.load(file)
        assert module.AppSettings().get_setting("value_ranges") == expected_settings["value_ranges"]

    @pytest.mark.unit
    def test_environment_file_only_present_in_the_working_directory_is_selected(
        self, env_reload, tmp_path
    ):
        custom_file = tmp_path / "appsettings.CustomEnv.json"
        custom_file.write_text(json.dumps({"value_ranges": {"cwd_only": True}}), encoding="utf8")

        module = env_reload("CustomEnv", cwd=tmp_path)

        selected = pathlib.Path(module.AppSettings._AppSettings__default_appsettings_file)
        assert selected.resolve() == custom_file.resolve()
        assert module.AppSettings().get_setting("value_ranges") == {"cwd_only": True}

    @pytest.mark.unit
    def test_environment_missing_everywhere_falls_back_to_the_default_file(
        self, env_reload, tmp_path
    ):
        module = env_reload("NoSuchEnvironment", cwd=tmp_path)

        assert module.AppSettings._AppSettings__default_appsettings_file == str(
            DEFAULT_APPSETTINGS_FILE
        )

    @pytest.mark.unit
    def test_environment_file_present_but_empty_falls_back_to_the_default_file(
        self, env_reload, tmp_path
    ):
        empty_file = tmp_path / "appsettings.EmptyEnv.json"
        empty_file.write_text("", encoding="utf8")

        module = env_reload("EmptyEnv", cwd=tmp_path)

        assert module.AppSettings._AppSettings__default_appsettings_file == str(
            DEFAULT_APPSETTINGS_FILE
        )

    @pytest.mark.unit
    def test_empty_environment_variable_falls_back_to_the_default_file(self, env_reload):
        module = env_reload("")

        assert module.AppSettings._AppSettings__default_appsettings_file == str(
            DEFAULT_APPSETTINGS_FILE
        )

    @pytest.mark.unit
    def test_module_is_left_on_its_default_settings(self):
        """Sanity check that the env_reload fixture always restores the module afterward."""
        assert app_settings_module.AppSettings().get_setting("value_ranges") is not None
