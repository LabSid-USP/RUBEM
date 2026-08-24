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
