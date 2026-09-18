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
