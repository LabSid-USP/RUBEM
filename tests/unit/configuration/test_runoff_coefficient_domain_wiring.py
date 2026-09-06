"""The loader reports the runoff coefficient domain of the tables and the weights."""

from pathlib import Path

import pytest

from rubem.configuration._problems import ConfigurationError
from rubem.configuration.model_configuration import ModelConfiguration
from tests.helpers.synthetic import write_synthetic_dataset


@pytest.fixture(name="config")
def config_fixture(tmp_path):
    config = write_synthetic_dataset(str(tmp_path))
    import pcraster as pcr

    pcr.setclone(config["RASTERS"]["clone"])
    return config


def rewrite_manning(config, roughness):
    """Give both synthetic land use classes the same Manning roughness."""
    Path(config["TABLES"]["manning"]).write_text(f"3 {roughness}\n4 {roughness}\n", encoding="utf8")


class TestRunoffCoefficientDomainThroughTheLoader:
    @pytest.mark.unit
    def test_the_synthetic_configuration_reports_no_domain_problem(self, config):
        """Supplement S5-S9, PDF page 6: the synthetic tables keep C_wp well below 1."""
        loaded = ModelConfiguration(config)

        assert not any("runoff coefficient" in str(p).lower() for p in loaded.problems)

    @pytest.mark.unit
    def test_a_roughness_that_pushes_the_coefficient_above_one_blocks(self, config):
        """Supplement S9, PDF page 6: n = 0.005 with w1 = 0.333 gives B >= 1.33 for class 3.

        B = (1 - 0) (0.333 * 0.02 / 0.005 + 0.333 * 0.12 / (1 - 0.12)) = 1.3774
        """
        expected = 0.333 * 0.02 / 0.005 + 0.333 * 0.12 / (1 - 0.12)
        assert expected > 1.0
        rewrite_manning(config, 0.005)

        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(config)

        assert any(
            p.blocking and p.description == "Weighted runoff coefficient exceeds 1."
            for p in error.value.problems
        )

    @pytest.mark.unit
    def test_a_roughness_that_only_the_slope_can_push_above_one_warns(self, config):
        """Supplement S9, PDF page 6: n = 0.008 leaves B < 1 <= B + (1 - A) w3.

        Class 3 (A = 0): B = 0.333 * 0.02 / 0.008 + 0.333 * 0.12 / 0.88 = 0.8779
        and B + w3 = 0.8779 + 0.334 = 1.2119, so C_wp reaches 1 on steep cells.
        """
        b = 0.333 * 0.02 / 0.008 + 0.333 * 0.12 / (1 - 0.12)
        assert b < 1.0 <= b + 0.334
        rewrite_manning(config, 0.008)

        loaded = ModelConfiguration(config)

        reported = [
            p
            for p in loaded.problems
            if p.description == "Weighted runoff coefficient may exceed 1 on steep cells."
        ]
        assert reported
        assert not any(p.blocking for p in reported)

    @pytest.mark.unit
    def test_the_domain_is_not_checked_when_the_input_validation_is_off(self, config):
        """The check runs with the other input checks only, under ``validate_input``.

        The same tables that block with the validation on (n = 0.005, Supplement S9,
        PDF page 6) must load without a problem and without raising when it is off.
        """
        rewrite_manning(config, 0.005)

        loaded = ModelConfiguration(config, validate_input=False)

        assert not any("runoff coefficient" in str(p).lower() for p in loaded.problems)

    @pytest.mark.unit
    def test_an_unreadable_table_is_reported_once_by_the_lookup_table_check(self, config):
        """The domain check runs after check_lookup_tables and defers to it.

        A manning table that cannot be parsed is a problem of the table itself, so
        only check_lookup_tables reports it and no C_wp problem is added on top.
        """
        Path(config["TABLES"]["manning"]).write_text("not a table\n", encoding="utf8")

        with pytest.raises(ConfigurationError) as error:
            ModelConfiguration(config)

        problems = error.value.problems
        assert any("lookup table cannot be read" in p.description.lower() for p in problems)
        assert not any("runoff coefficient" in p.description.lower() for p in problems)
