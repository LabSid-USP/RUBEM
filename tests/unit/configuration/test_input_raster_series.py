import os
from pathlib import Path

import pytest

from rubem.configuration._problems import Problem
from rubem.configuration.input_raster_series import InputRasterSeries


def _series(config, **overrides):
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
        validate_input=False,
    )
    keywords.update(overrides)
    return InputRasterSeries(**keywords)


class TestInputRasterSeries:
    @pytest.mark.unit
    def test_relative_directories_are_absolutised_and_frozen_at_construction(
        self, tmp_path, monkeypatch
    ):
        from tests.helpers.synthetic import write_synthetic_dataset

        config = write_synthetic_dataset(str(tmp_path))
        monkeypatch.chdir(tmp_path)
        relative_etp = os.path.relpath(config["DIRECTORIES"]["etp"], tmp_path)

        series = _series(config, etp=relative_etp)

        before = series.etp_directory
        assert Path(before).is_absolute()

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        assert series.etp_directory == before
        assert Path(series.etp).parent == Path(before)


class TestInputRasterSeriesProblems:
    @pytest.mark.unit
    def test_data_rule_violations_record_exactly_one_dict_per_problem(self, tmp_path):
        import numpy as np
        import pcraster as pcr

        from tests.helpers.synthetic import write_synthetic_dataset

        config = write_synthetic_dataset(str(tmp_path))
        bad_ndvi = np.full((3, 3), 1.5, dtype=np.float32)
        pcr.report(
            pcr.numpy2pcr(pcr.Scalar, bad_ndvi, -9999.0),
            str(tmp_path / "maps" / "ndvi" / "ndvi0000.001"),
        )

        series = InputRasterSeries(
            etp=config["DIRECTORIES"]["etp"],
            etp_filename_prefix="etp",
            precipitation=config["DIRECTORIES"]["prec"],
            precipitation_filename_prefix="prec",
            ndvi=config["DIRECTORIES"]["ndvi"],
            ndvi_filename_prefix="ndvi",
            kp=config["DIRECTORIES"]["kp"],
            kp_filename_prefix="kp",
            landuse=config["DIRECTORIES"]["landuse"],
            landuse_filename_prefix="cob",
            validate_input=True,
        )

        assert series.problems, "the out-of-range NDVI raster must be reported"
        assert all(isinstance(problem, Problem) for problem in series.problems)

    @pytest.mark.unit
    def test_a_geotiff_member_with_another_crs_is_a_blocking_problem(self, tmp_path):
        from osgeo import gdal

        from tests.helpers.compare import ensure_gdal_drivers
        from tests.helpers.synthetic import geotiff_series_name, write_synthetic_dataset

        config = write_synthetic_dataset(str(tmp_path), raster_format="tif")
        ensure_gdal_drivers()
        gdal.UseExceptions()
        member = str(tmp_path / "maps" / "rain" / geotiff_series_name("prec", 1))
        dataset = gdal.OpenEx(member, gdal.GA_Update)
        dataset.SetProjection('LOCAL_CS["Grid B",UNIT["foot",0.3048]]')
        dataset = None

        series = InputRasterSeries(
            etp=config["DIRECTORIES"]["etp"],
            etp_filename_prefix="etp",
            precipitation=config["DIRECTORIES"]["prec"],
            precipitation_filename_prefix="prec",
            ndvi=config["DIRECTORIES"]["ndvi"],
            ndvi_filename_prefix="ndvi",
            kp=config["DIRECTORIES"]["kp"],
            kp_filename_prefix="kp",
            landuse=config["DIRECTORIES"]["landuse"],
            landuse_filename_prefix="cob",
            validate_input=True,
            clone_projection='LOCAL_CS["Grid A",UNIT["metre",1]]',
        )

        blocking = [
            p
            for p in series.problems
            if p.blocking and "coordinate reference system" in p.description
        ]
        assert blocking, series.problems

    @pytest.mark.unit
    def test_blocking_content_rules_ignore_files_outside_the_required_window(self, tmp_path):
        import numpy as np
        import pcraster as pcr

        from tests.helpers.synthetic import series_name, write_synthetic_dataset

        config = write_synthetic_dataset(str(tmp_path))
        # An archived Kp raster at step 3, outside the 1-2 simulated window,
        # with a non-positive value that would otherwise block the run.
        archived_kp = os.path.join(config["DIRECTORIES"]["kp"], series_name("kp", 3))
        pcr.report(
            pcr.numpy2pcr(pcr.Scalar, np.full((3, 3), -1.0, dtype=np.float32), -9999.0),
            archived_kp,
        )

        series = _series(config, validate_input=True, required_steps=(1, 2))

        assert not any(problem.blocking for problem in series.problems)

    @pytest.mark.unit
    def test_blocking_content_rules_apply_to_files_inside_the_required_window(self, tmp_path):
        import numpy as np
        import pcraster as pcr

        from tests.helpers.synthetic import series_name, write_synthetic_dataset

        config = write_synthetic_dataset(str(tmp_path))
        bad_kp = os.path.join(config["DIRECTORIES"]["kp"], series_name("kp", 1))
        pcr.report(
            pcr.numpy2pcr(pcr.Scalar, np.full((3, 3), -1.0, dtype=np.float32), -9999.0),
            bad_kp,
        )

        series = _series(config, validate_input=True, required_steps=(1, 2))

        assert any(problem.blocking for problem in series.problems)
