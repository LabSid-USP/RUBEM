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
