import pytest

from rubem import _deps


class TestRequireRuntimeDeps:
    @pytest.mark.unit
    def test_present_dependencies_do_not_raise(self):
        _deps.require_runtime_deps()

    @pytest.mark.unit
    def test_missing_dependencies_are_named_with_an_actionable_source(self, monkeypatch):
        monkeypatch.setattr(_deps.importlib.util, "find_spec", lambda name: None)
        with pytest.raises(SystemExit) as error:
            _deps.require_runtime_deps()
        message = str(error.value)
        for name in _deps._CONDA_ONLY_DEPENDENCIES:
            assert name in message
        assert "conda-forge" in message
        assert _deps._ENVIRONMENT_YML_URL in message


class TestRequireCalibrationDeps:
    @pytest.mark.unit
    def test_present_dependencies_do_not_raise(self):
        _deps.require_calibration_deps()

    @pytest.mark.unit
    def test_nothing_is_missing_when_every_dependency_is_importable(self):
        assert _deps.missing_calibration_deps() == []

    @pytest.mark.unit
    def test_an_unimportable_dependency_is_reported_as_missing(self, monkeypatch):
        monkeypatch.setattr(_deps.importlib.util, "find_spec", lambda name: None)

        assert _deps.missing_calibration_deps() == list(_deps._CALIBRATION_DEPENDENCIES)

    @pytest.mark.unit
    def test_a_broken_dependency_counts_as_missing(self, monkeypatch):
        def raise_import_error(name):
            raise ImportError(name)

        monkeypatch.setattr(_deps.importlib.util, "find_spec", raise_import_error)

        assert _deps.missing_calibration_deps() == list(_deps._CALIBRATION_DEPENDENCIES)

    @pytest.mark.unit
    def test_the_message_names_the_dependency_and_the_extra(self):
        message = _deps.calibration_deps_message(["scipy"])

        assert "scipy" in message
        assert 'pip install "rubem[calibration]"' in message

    @pytest.mark.unit
    def test_the_message_defaults_to_every_calibration_dependency(self):
        """The runner asks for the guidance without having computed the list."""
        assert _deps.calibration_deps_message() == _deps.calibration_deps_message(
            list(_deps._CALIBRATION_DEPENDENCIES)
        )

    @pytest.mark.unit
    def test_missing_dependencies_are_named_with_an_actionable_extra(self, monkeypatch):
        monkeypatch.setattr(_deps.importlib.util, "find_spec", lambda name: None)

        with pytest.raises(SystemExit) as error:
            _deps.require_calibration_deps()

        message = str(error.value)
        for name in _deps._CALIBRATION_DEPENDENCIES:
            assert name in message
        assert 'pip install "rubem[calibration]"' in message


class TestGroundwaterDeps:
    @pytest.fixture(name="no_executable_on_path")
    def no_executable_on_path_fixture(self, monkeypatch, tmp_path):
        """``mf2005`` is not on PATH and the interpreter prefix is an empty directory."""
        monkeypatch.setattr(_deps.shutil, "which", lambda name: None)
        monkeypatch.setattr(_deps.sys, "prefix", str(tmp_path))
        return tmp_path

    @pytest.mark.unit
    def test_nothing_is_missing_in_the_conda_environment(self):
        """The conda-forge pcraster package ships the extension and the executable."""
        assert _deps.missing_groundwater_deps() == []

    @pytest.mark.unit
    def test_the_executable_on_path_wins(self, monkeypatch, tmp_path):
        executable = tmp_path / "mf2005"
        monkeypatch.setattr(_deps.shutil, "which", lambda name: str(executable))

        assert _deps.resolve_mf2005() == executable

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "relative", [("bin", "mf2005"), ("Library", "bin", "mf2005.exe")], ids=["unix", "windows"]
    )
    def test_the_executable_is_found_under_the_interpreter_prefix(
        self, no_executable_on_path, relative
    ):
        """conda puts mf2005 in <prefix>/bin, and in <prefix>/Library/bin on Windows."""
        executable = no_executable_on_path.joinpath(*relative)
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"")

        assert _deps.resolve_mf2005() == executable

    @pytest.mark.unit
    def test_a_missing_executable_is_reported(self, no_executable_on_path):
        assert _deps.resolve_mf2005() is None
        assert _deps.missing_groundwater_deps() == ["mf2005"]

    @pytest.mark.unit
    def test_a_missing_extension_is_reported(self, monkeypatch):
        monkeypatch.setattr(_deps.importlib.util, "find_spec", lambda name: None)

        assert _deps.missing_groundwater_deps() == ["pcraster._pcraster_modflow"]

    @pytest.mark.unit
    def test_a_broken_pcraster_counts_as_a_missing_extension(self, monkeypatch):
        """Looking up a submodule imports its parent package, which may raise."""

        def raise_import_error(name):
            raise ImportError(name)

        monkeypatch.setattr(_deps.importlib.util, "find_spec", raise_import_error)

        assert _deps.missing_groundwater_deps() == ["pcraster._pcraster_modflow"]

    @pytest.mark.unit
    def test_the_message_names_what_is_missing_and_where_it_comes_from(self):
        message = _deps.groundwater_deps_message(["mf2005"])

        assert "mf2005" in message
        assert "conda-forge" in message
        assert _deps._ENVIRONMENT_YML_URL in message

    @pytest.mark.unit
    def test_the_message_defaults_to_every_groundwater_dependency(self):
        assert _deps.groundwater_deps_message() == _deps.groundwater_deps_message(
            ["pcraster._pcraster_modflow", "mf2005"]
        )

    @pytest.mark.unit
    def test_the_prefix_directory_is_put_on_path_once(
        self, monkeypatch, no_executable_on_path, caplog
    ):
        """The extension launches ``mf2005`` from PATH, and spawned workers inherit PATH."""
        directory = no_executable_on_path / "bin"
        directory.mkdir()
        (directory / "mf2005").write_bytes(b"")
        monkeypatch.setenv("PATH", "elsewhere")

        with caplog.at_level("INFO", logger=_deps.__name__):
            first = _deps.ensure_mf2005_on_path()
            second = _deps.ensure_mf2005_on_path()

        assert first == second == directory / "mf2005"
        entries = _deps.os.environ["PATH"].split(_deps.os.pathsep)
        assert entries == [str(directory), "elsewhere"]
        assert len([r for r in caplog.records if str(directory) in r.getMessage()]) == 1

    @pytest.mark.unit
    def test_path_is_left_alone_when_the_executable_is_on_it(self, monkeypatch, tmp_path):
        monkeypatch.setattr(_deps.shutil, "which", lambda name: str(tmp_path / "mf2005"))
        monkeypatch.setenv("PATH", "elsewhere")

        assert _deps.ensure_mf2005_on_path() == tmp_path / "mf2005"
        assert _deps.os.environ["PATH"] == "elsewhere"

    @pytest.mark.unit
    def test_nothing_is_put_on_path_without_an_executable(self, monkeypatch, no_executable_on_path):
        monkeypatch.setenv("PATH", "elsewhere")

        assert _deps.ensure_mf2005_on_path() is None
        assert _deps.os.environ["PATH"] == "elsewhere"
