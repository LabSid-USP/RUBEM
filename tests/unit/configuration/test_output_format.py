import pytest

from rubem.configuration.output_format import OutputFileFormat


class TestOutputFileFormat:
    @pytest.mark.unit
    def test_members_are_distinct(self):
        assert OutputFileFormat.PCRASTER != OutputFileFormat.GEOTIFF

    @pytest.mark.unit
    def test_combined_flag_contains_both_members(self):
        combined = OutputFileFormat.PCRASTER | OutputFileFormat.GEOTIFF

        assert OutputFileFormat.PCRASTER in combined
        assert OutputFileFormat.GEOTIFF in combined

    @pytest.mark.unit
    def test_single_member_does_not_contain_the_other(self):
        assert OutputFileFormat.GEOTIFF not in OutputFileFormat.PCRASTER
        assert OutputFileFormat.PCRASTER not in OutputFileFormat.GEOTIFF
