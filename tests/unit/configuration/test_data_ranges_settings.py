import sys

import pytest

from rubem.configuration.data_ranges_settings import DataRangesSettings


@pytest.fixture
def fresh_data_ranges_settings():
    """Reset the singleton so a fresh construction runs ``__init__`` again."""
    saved_instance = DataRangesSettings._DataRangesSettings__instance
    DataRangesSettings._DataRangesSettings__instance = None
    yield
    DataRangesSettings._DataRangesSettings__instance = saved_instance


class TestDataRangesSettings:
    @pytest.mark.unit
    def test_singleton_instance(self):
        instance1 = DataRangesSettings()
        instance2 = DataRangesSettings()
        assert instance1 is instance2

    @pytest.mark.unit
    def test_missing_data_raises(self, fresh_data_ranges_settings):
        with pytest.raises(ValueError, match="Missing data"):
            DataRangesSettings(None)

    @pytest.mark.unit
    def test_empty_data_raises(self, fresh_data_ranges_settings):
        with pytest.raises(ValueError, match="Missing data"):
            DataRangesSettings({})

    @pytest.mark.unit
    def test_missing_rasters_section_raises(self, fresh_data_ranges_settings):
        data = {"variables": {"tss": {"min": 0.0, "max": 1.0}}}
        with pytest.raises(ValueError, match="Missing 'rasters' section"):
            DataRangesSettings(data)

    @pytest.mark.unit
    def test_missing_variables_section_raises(self, fresh_data_ranges_settings):
        data = {"rasters": {"dem": {"min": 0.0, "max": 1.0}}}
        with pytest.raises(ValueError, match="Missing 'variables' section"):
            DataRangesSettings(data)

    @pytest.mark.unit
    def test_entry_missing_min_raises(self, fresh_data_ranges_settings):
        data = {
            "rasters": {"dem": {"max": 1.0}},
            "variables": {},
        }
        with pytest.raises(ValueError, match="Missing 'min' value in 'rasters.dem'"):
            DataRangesSettings(data)

    @pytest.mark.unit
    def test_entry_missing_max_raises(self, fresh_data_ranges_settings):
        data = {
            "rasters": {"dem": {"min": 0.0}},
            "variables": {},
        }
        with pytest.raises(ValueError, match="Missing 'max' value in 'rasters.dem'"):
            DataRangesSettings(data)

    @pytest.mark.unit
    def test_variables_entry_missing_min_raises(self, fresh_data_ranges_settings):
        data = {
            "rasters": {},
            "variables": {"tss": {"max": 1.0}},
        }
        with pytest.raises(ValueError, match="Missing 'min' value in 'variables.tss'"):
            DataRangesSettings(data)

    @pytest.mark.unit
    def test_min_greater_than_max_raises(self, fresh_data_ranges_settings):
        data = {
            "rasters": {"dem": {"min": 10.0, "max": 1.0}},
            "variables": {},
        }
        with pytest.raises(
            ValueError, match="'max' value must be greater than 'min' value in 'rasters.dem'"
        ):
            DataRangesSettings(data)

    @pytest.mark.unit
    def test_min_equal_to_max_raises(self, fresh_data_ranges_settings):
        data = {
            "rasters": {"dem": {"min": 1.0, "max": 1.0}},
            "variables": {},
        }
        with pytest.raises(
            ValueError, match="'max' value must be greater than 'min' value in 'rasters.dem'"
        ):
            DataRangesSettings(data)

    @pytest.mark.unit
    def test_valid_payload_exposes_rasters_and_variables(self, fresh_data_ranges_settings):
        data = {
            "rasters": {"dem": {"min": -100.0, "max": 10000.0}},
            "variables": {"tss": {"min": 0.0, "max": 1.0}},
        }
        instance = DataRangesSettings(data)

        assert instance.rasters == {"dem": {"min": -100.0, "max": 10000.0}}
        assert instance.variables == {"tss": {"min": 0.0, "max": 1.0}}

    @pytest.mark.unit
    def test_infinity_strings_are_converted_before_validation(self, fresh_data_ranges_settings):
        data = {
            "rasters": {"soil": {"min": "-Infinity", "max": "Infinity"}},
            "variables": {},
        }
        instance = DataRangesSettings(data)

        assert instance.rasters["soil"]["min"] == -sys.float_info.max
        assert instance.rasters["soil"]["max"] == sys.float_info.max

    @pytest.mark.unit
    def test_infinity_strings_are_converted_recursively(self, fresh_data_ranges_settings):
        data = {
            "rasters": {
                "soil": {
                    "min": 0.0,
                    "max": 1.0,
                    "nested": {"low": "-Infinity", "high": "Infinity"},
                }
            },
            "variables": {},
        }
        instance = DataRangesSettings(data)

        nested = instance.rasters["soil"]["nested"]
        assert nested["low"] == -sys.float_info.max
        assert nested["high"] == sys.float_info.max
