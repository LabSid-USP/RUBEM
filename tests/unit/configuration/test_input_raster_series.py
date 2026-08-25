import pytest

from rubem.configuration._problems import Problem
from rubem.configuration.input_raster_series import InputRasterSeries


class TestInputRasterSeries:
    pass


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
