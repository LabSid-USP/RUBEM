import inspect
import os

import pcraster.framework as pcrfw
import pytest

from rubem.file._timeoutput import TimeoutputTimeseriesAdapter


class _StaticModel:
    def firstTimeStep(self):
        return 1

    def nrTimeSteps(self):
        return 2


class _StochasticModel(_StaticModel):
    nrSamples = 3

    def currentSampleNumber(self):
        return 2


def _adapter_with(model):
    adapter = TimeoutputTimeseriesAdapter.__new__(TimeoutputTimeseriesAdapter)
    adapter._userModel = model
    return adapter


class TestTimeoutputTimeseriesAdapter:
    @pytest.mark.unit
    def test_appends_tss_extension(self):
        adapter = _adapter_with(_StaticModel())
        assert adapter._configureOutputFilename("tss_itp") == "tss_itp.tss"

    @pytest.mark.unit
    def test_preserves_existing_extension(self):
        adapter = _adapter_with(_StaticModel())
        assert adapter._configureOutputFilename("tss_itp.tss") == "tss_itp.tss"

    @pytest.mark.unit
    def test_accepts_absolute_paths(self):
        adapter = _adapter_with(_StaticModel())
        absolute = os.path.join(os.sep, "out", "tss_itp")
        assert adapter._configureOutputFilename(absolute) == absolute + ".tss"

    @pytest.mark.unit
    def test_places_sample_directory_between_directory_and_filename(self):
        adapter = _adapter_with(_StochasticModel())
        absolute = os.path.join(os.sep, "out", "tss_itp")
        expected = os.path.join(os.sep, "out", "2", "tss_itp.tss")
        assert adapter._configureOutputFilename(absolute) == expected

    @pytest.mark.unit
    def test_relative_stochastic_behavior_matches_base_class(self):
        adapter = _adapter_with(_StochasticModel())
        assert adapter._configureOutputFilename("tss_itp") == os.path.join("2", "tss_itp.tss")

    @pytest.mark.unit
    def test_base_class_still_defines_the_overridden_hook(self):
        """Pin the private hook this adapter overrides.

        If a PCRaster upgrade renames ``_configureOutputFilename`` or drops
        its absolute-path assertion, the override silently stops applying;
        this test fails instead.
        """
        hook = getattr(pcrfw.TimeoutputTimeseries, "_configureOutputFilename", None)
        assert hook is not None
        assert "isabs" in inspect.getsource(hook)
