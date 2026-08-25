import os
import re

import pytest

from rubem.file._naming import (
    get_raster_series_filepath,
    output_raster_filename,
    raster_series_filename,
    raster_series_pattern,
)


class TestRasterSeriesFilename:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        "prefix, timestep, expected",
        [
            ("prec", 1, "prec0000.001"),
            ("prec", 999, "prec0000.999"),
            ("prec", 1000, "prec0001.000"),
            ("kp", 12, "kp000000.012"),
            ("a", 1234567, "a0001234.567"),
            ("prefix7", 1, "prefix70.001"),
            ("ndvi", 228, "ndvi0000.228"),
        ],
    )
    def test_follows_the_pcraster_convention(self, prefix, timestep, expected):
        assert raster_series_filename(prefix, timestep) == expected

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "prefix, timestep",
        [
            (prefix, timestep)
            for prefix in ("prec", "kp", "a", "prefix7", "n")
            for timestep in (1, 9, 10, 99, 100, 999, 1000, 12345)
            # Eleven digits are shared by the prefix and the step in both implementations.
            if len(prefix) + len(str(timestep)) <= 11
        ],
    )
    def test_agrees_with_the_framework_generator(self, prefix, timestep):
        """The model reads its series through the PCRaster framework; the
        validators must look for exactly the same file names."""
        from pcraster.framework import generateNameT

        assert raster_series_filename(prefix, timestep) == generateNameT(prefix, timestep)

    @pytest.mark.unit
    @pytest.mark.parametrize("prefix", ["", "prefix08", "toolongprefix", "a.b", "a/b", "a\\b"])
    def test_rejects_unusable_prefixes(self, prefix):
        with pytest.raises(ValueError):
            raster_series_filename(prefix, 1)

    @pytest.mark.unit
    @pytest.mark.parametrize("timestep", [0, -1, 1.5, True, "1"])
    def test_rejects_non_positive_or_non_integer_steps(self, timestep):
        with pytest.raises(ValueError):
            raster_series_filename("prec", timestep)

    @pytest.mark.unit
    def test_rejects_a_step_that_does_not_fit(self):
        with pytest.raises(ValueError, match="does not fit"):
            raster_series_filename("prefix7", 10000)


class TestGetRasterSeriesFilepath:
    @pytest.mark.unit
    def test_joins_the_directory_and_returns_an_absolute_path(self, tmp_path):
        path = get_raster_series_filepath(tmp_path / "rain", "prec", 3)

        assert os.path.isabs(path)
        assert path == os.path.join(os.path.abspath(tmp_path / "rain"), "prec0000.003")

    @pytest.mark.unit
    def test_accepts_a_relative_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        assert get_raster_series_filepath("rain", "prec", 1) == os.path.join(
            os.path.abspath("rain"), "prec0000.001"
        )


class TestRasterSeriesPattern:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        "name, matches",
        [
            ("prec0000.001", True),
            ("PREC0000.001", True),
            ("prec0001.000", True),
            ("prec000.001", False),
            ("prec00000.001", False),
            ("prec0000.01", False),
            ("precipitation.001", False),
            ("rain0000.001", False),
            ("prec0000.001.aux.xml", False),
        ],
    )
    def test_matches_only_members_of_the_series(self, name, matches):
        assert bool(raster_series_pattern("prec").match(name)) is matches

    @pytest.mark.unit
    def test_treats_the_prefix_literally(self):
        """A prefix with a regular-expression metacharacter must not widen the match."""
        pattern = raster_series_pattern("a+b")

        assert pattern.match("a+b00000.001")
        assert not pattern.match("aab00000.001")
        assert not pattern.match("aaab0000.001")

    @pytest.mark.unit
    def test_generated_names_match_their_own_pattern(self):
        for prefix in ("prec", "kp", "prefix7"):
            pattern = raster_series_pattern(prefix)
            for timestep in (1, 999, 1000):
                assert pattern.match(raster_series_filename(prefix, timestep))

    @pytest.mark.unit
    def test_returns_a_compiled_pattern(self):
        assert isinstance(raster_series_pattern("prec"), re.Pattern)


class TestOutputRasterFilename:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        "prefix, timestep, expected",
        [
            ("itp", 1, "itp0000001.tif"),
            ("arn", 228, "arn0000228.tif"),
            ("itp", 1234567, "itp1234567.tif"),
            ("runoff", 1, "runoff0001.tif"),
        ],
    )
    def test_pads_the_step_to_ten_characters(self, prefix, timestep, expected):
        assert output_raster_filename(prefix, timestep, "tif") == expected

    @pytest.mark.unit
    def test_rejects_a_step_that_does_not_fit(self):
        with pytest.raises(ValueError, match="does not fit"):
            output_raster_filename("runoff", 12345, "tif")

    @pytest.mark.unit
    @pytest.mark.parametrize("prefix", ["", "tenletters"])
    def test_rejects_unusable_prefixes(self, prefix):
        with pytest.raises(ValueError):
            output_raster_filename(prefix, 1, "tif")

    @pytest.mark.unit
    @pytest.mark.parametrize("timestep", [0, -3, True, 2.0])
    def test_rejects_non_positive_or_non_integer_steps(self, timestep):
        with pytest.raises(ValueError):
            output_raster_filename("itp", timestep, "tif")
