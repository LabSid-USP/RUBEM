import pytest

from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.output_format import OutputFileFormat
from tests.helpers.synthetic import write_synthetic_dataset


@pytest.fixture(name="config")
def config_fixture(tmp_path):
    return write_synthetic_dataset(str(tmp_path))


def load(config):
    return ModelConfiguration(config, validate_input=False)


class TestRasterFileFormatFlags:
    @pytest.mark.unit
    def test_both_formats_when_both_flags_are_true(self, config):
        formats = load(config).output_variables.file_formats

        assert OutputFileFormat.PCRASTER in formats
        assert OutputFileFormat.GEOTIFF in formats

    @pytest.mark.unit
    def test_pcraster_maps_are_the_default_when_the_section_is_absent(self, config):
        del config["RASTER_FILE_FORMAT"]

        assert load(config).output_variables.file_formats == OutputFileFormat.PCRASTER

    @pytest.mark.unit
    def test_map_raster_series_false_disables_the_pcraster_maps(self, config):
        config["RASTER_FILE_FORMAT"] = {"map_raster_series": False, "tiff_raster_series": True}

        assert load(config).output_variables.file_formats == OutputFileFormat.GEOTIFF

    @pytest.mark.unit
    def test_tiff_raster_series_defaults_to_false(self, config):
        config["RASTER_FILE_FORMAT"] = {"map_raster_series": True}

        assert load(config).output_variables.file_formats == OutputFileFormat.PCRASTER

    @pytest.mark.unit
    @pytest.mark.parametrize("value", ["true", "True", "1", "yes"])
    def test_string_flags_are_accepted(self, config, value):
        config["RASTER_FILE_FORMAT"] = {"map_raster_series": "false", "tiff_raster_series": value}

        assert load(config).output_variables.file_formats == OutputFileFormat.GEOTIFF

    @pytest.mark.unit
    def test_no_format_with_output_variables_is_rejected(self, config):
        config["RASTER_FILE_FORMAT"] = {"map_raster_series": False, "tiff_raster_series": False}

        with pytest.raises(ValueError, match="No raster file format is enabled"):
            load(config)

    @pytest.mark.unit
    def test_no_format_without_output_variables_is_accepted(self, config):
        config["RASTER_FILE_FORMAT"] = {"map_raster_series": False, "tiff_raster_series": False}
        config["GENERATE_FILE"] = {key: False for key in config["GENERATE_FILE"]}

        assert not load(config).output_variables.file_formats


class TestNoDataValue:
    @pytest.mark.unit
    def test_defaults_to_minus_9999(self, config):
        assert load(config).output_variables.no_data_value == -9999

    @pytest.mark.unit
    def test_defaults_when_the_section_is_absent(self, config):
        del config["RASTER_FILE_FORMAT"]

        assert load(config).output_variables.no_data_value == -9999

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "value, expected", [(-1, -1.0), (0, 0.0), ("-32768", -32768.0), (1e20, 1e20)]
    )
    def test_reads_numbers_and_numeric_strings(self, config, value, expected):
        config["RASTER_FILE_FORMAT"]["no_data_value"] = value

        assert load(config).output_variables.no_data_value == expected

    @pytest.mark.unit
    @pytest.mark.parametrize("value", ["none", "", None, True, "nan", "inf", [1]])
    def test_rejects_values_that_are_not_finite_numbers(self, config, value):
        config["RASTER_FILE_FORMAT"]["no_data_value"] = value

        with pytest.raises(ValueError, match="no_data_value"):
            load(config)

    @pytest.mark.unit
    @pytest.mark.parametrize("value", [3.5e38, -3.5e38, 1e40, -1e40])
    def test_rejects_values_outside_the_float32_range(self, config, value):
        config["RASTER_FILE_FORMAT"]["no_data_value"] = value

        with pytest.raises(ValueError, match="no_data_value"):
            load(config)

    @pytest.mark.unit
    @pytest.mark.parametrize("value", [3.4e38, -3.4e38])
    def test_accepts_values_within_the_float32_range(self, config, value):
        config["RASTER_FILE_FORMAT"]["no_data_value"] = value

        assert load(config).output_variables.no_data_value == value
