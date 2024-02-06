import pytest

from rubem.configuration.data_ranges_settings import DataRangesSettings


class TestDataRangesSettings:

    @pytest.mark.unit
    def test_singleton_instance(self):
        instance1 = DataRangesSettings()
        instance2 = DataRangesSettings()
        assert instance1 is instance2
