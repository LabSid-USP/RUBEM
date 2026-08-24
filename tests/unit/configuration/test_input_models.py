import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from rubem.configuration._problems import ConfigurationError, Problem
from rubem.configuration.input_raster_files import InputRasterFiles
from rubem.configuration.input_raster_series import InputRasterSeries
from rubem.configuration.input_table_files import InputTableFiles
from tests.helpers.synthetic import write_synthetic_dataset


def raster_files(config, **overrides):
    rasters = config["RASTERS"]
    keywords = dict(
        dem=rasters["dem"],
        clone=rasters["clone"],
        ndvi_max=rasters["ndvi_max"],
        ndvi_min=rasters["ndvi_min"],
        soil=rasters["soil"],
        sample_locations=rasters["samples"],
        ldd=rasters["ldd"],
    )
    keywords.update(overrides)
    return InputRasterFiles(**keywords)


def raster_series(config, **overrides):
    directories = config["DIRECTORIES"]
    prefixes = config["FILENAME_PREFIXES"]
    keywords = dict(
        etp=directories["etp"],
        etp_filename_prefix=prefixes["etp_prefix"],
        precipitation=directories["prec"],
        precipitation_filename_prefix=prefixes["prec_prefix"],
        ndvi=directories["ndvi"],
        ndvi_filename_prefix=prefixes["ndvi_prefix"],
        kp=directories["kp"],
        kp_filename_prefix=prefixes["kp_prefix"],
        landuse=directories["landuse"],
        landuse_filename_prefix=prefixes["landuse_prefix"],
    )
    keywords.update(overrides)
    return InputRasterSeries(**keywords)


def table_files(config, **overrides):
    tables = config["TABLES"]
    keywords = dict(
        rainy_days=tables["rainydays"],
        a_i=tables["a_i"],
        a_o=tables["a_o"],
        a_s=tables["a_s"],
        a_v=tables["a_v"],
        manning=tables["manning"],
        bulk_density=tables["bulk_density"],
        k_sat=tables["k_sat"],
        t_fcap=tables["t_fcap"],
        t_sat=tables["t_sat"],
        t_wp=tables["t_wp"],
        rootzone_depth=tables["rootzone_depth"],
        kc_min=tables["k_c_min"],
        kc_max=tables["k_c_max"],
    )
    keywords.update(overrides)
    return InputTableFiles(**keywords)


class TestProblem:
    @pytest.mark.unit
    def test_str_joins_the_parts_that_are_present(self):
        assert str(Problem(description="A", reason="b")) == "A: b"
        assert str(Problem(description="A", reason="b", implication="c", file="f")) == "A: b c f"

    @pytest.mark.unit
    def test_configuration_error_lists_the_blocking_problems(self):
        problems = [
            Problem(description="Warn", reason="soft"),
            Problem(description="Stop", reason="hard", blocking=True),
        ]

        error = ConfigurationError(problems)

        assert isinstance(error, ValueError)
        assert error.problems == problems
        assert "1 blocking problem" in str(error)
        assert "Stop: hard" in str(error) and "Warn" not in str(error)


class TestInputTableFiles:
    @pytest.mark.unit
    def test_paths_are_normalised_and_frozen(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))

        tables = table_files(config)

        assert Path(tables.rainy_days) == Path(config["TABLES"]["rainydays"])
        assert "Rainy Days:" in str(tables)
        with pytest.raises(ValidationError):
            tables.manning = "x"
        assert "validate_input" not in tables.model_dump()
        assert InputTableFiles.model_validate(tables.model_dump()) == tables

    @pytest.mark.unit
    def test_missing_and_empty_files_are_rejected_only_when_validating(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        missing = str(tmp_path / "absent.txt")

        with pytest.raises(FileNotFoundError, match="Invalid input lookuptable file"):
            table_files(config, manning=missing)
        assert table_files(config, manning=missing, validate_input=False).manning == missing

        empty = tmp_path / "empty.txt"
        empty.write_text("", encoding="utf8")
        with pytest.raises(ValueError, match="Empty input lookuptable file"):
            table_files(config, manning=empty)

    @pytest.mark.unit
    def test_bytes_paths_are_deprecated(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))

        with pytest.warns(DeprecationWarning, match="bytes paths"):
            tables = table_files(config, manning=os.fsencode(config["TABLES"]["manning"]))

        assert Path(tables.manning) == Path(config["TABLES"]["manning"])


class TestInputRasterFiles:
    @pytest.mark.unit
    def test_optional_rasters_default_to_none_and_empty_means_absent(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))

        files = raster_files(config, sample_locations="", ldd=None, georeference="")

        assert files.sample_locations is None and files.ldd is None
        assert files.georeference is None
        assert "Not specified." in str(files)
        assert files.problems == []

    @pytest.mark.unit
    def test_problems_are_typed_and_non_blocking(self, tmp_path):
        import numpy as np
        import pcraster as pcr

        config = write_synthetic_dataset(str(tmp_path))
        pcr.setclone(config["RASTERS"]["clone"])
        pcr.report(
            pcr.numpy2pcr(pcr.Scalar, np.full((3, 3), 1.5, dtype=np.float32), -9999.0),
            config["RASTERS"]["ndvi_max"],
        )

        files = raster_files(config)

        assert files.problems
        assert all(isinstance(problem, Problem) for problem in files.problems)
        assert not any(problem.blocking for problem in files.problems)
        assert Path(files.problems[0].file) == Path(config["RASTERS"]["ndvi_max"])

    @pytest.mark.unit
    def test_validation_can_be_skipped(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))

        files = raster_files(config, dem=str(tmp_path / "absent.map"), validate_input=False)

        assert files.dem.endswith("absent.map")
        assert files.problems == []

    @pytest.mark.unit
    def test_a_missing_raster_is_rejected(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))

        with pytest.raises(FileNotFoundError):
            raster_files(config, dem=str(tmp_path / "absent.map"))

    @pytest.mark.unit
    def test_is_frozen_and_round_trips(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        files = raster_files(config)

        with pytest.raises(ValidationError):
            files.dem = "x"
        assert InputRasterFiles.model_validate(files.model_dump()) == files


class TestInputRasterSeries:
    @pytest.mark.unit
    def test_series_paths_join_the_directory_and_the_prefix(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))

        series = raster_series(config)

        assert Path(series.etp).is_absolute()
        assert Path(series.etp).name == "etp"
        assert Path(series.etp).parent == Path(config["DIRECTORIES"]["etp"]).absolute()
        assert Path(series.precipitation).name == "prec"
        assert Path(series.etp_directory) == Path(config["DIRECTORIES"]["etp"])
        assert series.problems == []

    @pytest.mark.unit
    def test_attribute_names_are_accepted_as_keywords_too(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        series = raster_series(config)

        rebuilt = InputRasterSeries.model_validate(series.model_dump())

        assert rebuilt == series
        assert rebuilt.ndvi == series.ndvi

    @pytest.mark.unit
    def test_a_long_prefix_is_rejected_before_touching_the_disk(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))

        with pytest.raises(ValueError, match="Prefix too long"):
            raster_series(config, etp_filename_prefix="prefix08", validate_input=False)

    @pytest.mark.unit
    def test_directory_problems_keep_their_exceptions(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        empty = tmp_path / "empty"
        empty.mkdir()

        with pytest.raises(NotADirectoryError, match="Invalid input data directory"):
            raster_series(config, etp=str(tmp_path / "absent"))
        with pytest.raises(ValueError, match="Empty input data directory"):
            raster_series(config, etp=str(empty))
        with pytest.raises(FileNotFoundError, match="No files found with prefix"):
            raster_series(config, etp_filename_prefix="xyz")

    @pytest.mark.unit
    def test_validation_can_be_skipped(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))

        series = raster_series(config, etp=str(tmp_path / "absent"), validate_input=False)

        assert series.etp.endswith(os.path.join("absent", "etp"))
