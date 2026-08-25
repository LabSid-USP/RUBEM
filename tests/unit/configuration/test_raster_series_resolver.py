import os
from datetime import date
from pathlib import Path

import pytest

from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.model_configuration_file import ModelConfigurationFile
from rubem.configuration.model_configuration_file_v1 import ModelConfigurationFileV1
from rubem.configuration.raster_series_resolver import (
    DatedSeriesResolver,
    DirectorySeriesResolver,
    MissingStep,
    MonthlySeriesResolver,
    check_coverage,
    check_series_member_crs,
    date_to_step,
    resolvers_from_legacy,
    resolvers_from_v1,
    step_to_date,
    validate_resolved_series,
)
from tests.helpers.synthetic import geotiff_series_name, series_name, write_synthetic_dataset

ALIGNMENT = date(2000, 1, 1)


class TestStepDates:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        "step, expected",
        [
            (1, date(2000, 1, 1)),
            (12, date(2000, 12, 1)),
            (13, date(2001, 1, 1)),
            (228, date(2018, 12, 1)),
        ],
    )
    def test_steps_map_to_months_and_back(self, step, expected):
        assert step_to_date(step, ALIGNMENT) == expected
        assert date_to_step(expected, ALIGNMENT) == step

    @pytest.mark.unit
    def test_the_alignment_day_is_ignored(self):
        assert step_to_date(2, date(2000, 1, 15)) == date(2000, 2, 1)
        assert date_to_step(date(2000, 2, 28), date(2000, 1, 15)) == 2

    @pytest.mark.unit
    def test_steps_start_at_one(self):
        with pytest.raises(ValueError, match="steps start at 1"):
            step_to_date(0, ALIGNMENT)


class TestDirectorySeriesResolver:
    @pytest.mark.unit
    def test_answers_the_pcraster_file_names(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        resolver = DirectorySeriesResolver("precipitation", config["DIRECTORIES"]["prec"], "prec")

        first = resolver.path_for_step(1)

        assert os.path.basename(first) == series_name("prec", 1)
        assert os.path.isabs(first) and os.path.isfile(first)
        missing = resolver.path_for_step(3)
        assert isinstance(missing, MissingStep)
        assert missing.series == "precipitation" and missing.step == 3
        assert "does not exist" in str(missing)

    @pytest.mark.unit
    def test_a_relative_directory_is_absolutised_and_frozen(self, tmp_path, monkeypatch):
        config = write_synthetic_dataset(str(tmp_path))
        monkeypatch.chdir(tmp_path)
        relative = os.path.relpath(config["DIRECTORIES"]["prec"], tmp_path)

        resolver = DirectorySeriesResolver("precipitation", relative, "prec")

        before = resolver.directory
        assert os.path.isabs(before)

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        assert resolver.directory == before


class TestDatedSeriesResolver:
    @pytest.mark.unit
    def test_entries_cover_whole_months_inclusively(self):
        resolver = DatedSeriesResolver(
            "landuse",
            [
                ("/maps/a.map", date(2000, 1, 1), date(2000, 2, 28)),
                ("/maps/b.map", date(2000, 3, 15), date(2000, 4, 1)),
            ],
            ALIGNMENT,
        )

        assert Path(resolver.path_for_step(1)) == Path("/maps/a.map")
        assert Path(resolver.path_for_step(2)) == Path("/maps/a.map")
        assert Path(resolver.path_for_step(3)) == Path("/maps/b.map")
        assert Path(resolver.path_for_step(4)) == Path("/maps/b.map")
        missing = resolver.path_for_step(5)
        assert isinstance(missing, MissingStep) and "2000-05" in missing.reason

    @pytest.mark.unit
    def test_rejects_inverted_and_overlapping_entries(self):
        with pytest.raises(ValueError, match="after to"):
            DatedSeriesResolver("landuse", [("/a", date(2000, 2, 1), date(2000, 1, 1))], ALIGNMENT)
        with pytest.raises(ValueError, match="overlap"):
            DatedSeriesResolver(
                "landuse",
                [
                    ("/a", date(2000, 1, 1), date(2000, 3, 1)),
                    ("/b", date(2000, 3, 1), date(2000, 4, 1)),
                ],
                ALIGNMENT,
            )

    @pytest.mark.unit
    def test_disjoint_entries_given_out_of_order_are_accepted(self):
        resolver = DatedSeriesResolver(
            "landuse",
            [
                ("/b", date(2000, 3, 1), date(2000, 4, 30)),
                ("/a", date(2000, 1, 1), date(2000, 2, 28)),
            ],
            ALIGNMENT,
        )

        assert Path(resolver.path_for_step(1)) == Path("/a")
        assert Path(resolver.path_for_step(2)) == Path("/a")
        assert Path(resolver.path_for_step(3)) == Path("/b")
        assert Path(resolver.path_for_step(4)) == Path("/b")

    @pytest.mark.unit
    def test_entries_sharing_a_month_are_rejected_even_when_days_differ(self):
        with pytest.raises(ValueError, match="overlap"):
            DatedSeriesResolver(
                "landuse",
                [
                    ("/a", date(2000, 1, 1), date(2000, 1, 1)),
                    ("/b", date(2000, 1, 31), date(2000, 1, 31)),
                ],
                ALIGNMENT,
            )


class TestMonthlySeriesResolver:
    @pytest.mark.unit
    def test_repeats_the_twelve_rasters_every_year(self):
        resolver = MonthlySeriesResolver(
            "ndvi", {m: f"/maps/ndvi{m:02d}.map" for m in range(1, 13)}, ALIGNMENT
        )

        assert Path(resolver.path_for_step(1)) == Path("/maps/ndvi01.map")
        assert Path(resolver.path_for_step(14)) == Path("/maps/ndvi02.map")
        assert Path(resolver.path_for_step(24)) == Path("/maps/ndvi12.map")

    @pytest.mark.unit
    def test_the_yearly_raster_replaces_the_set_from_its_year_on(self):
        resolver = MonthlySeriesResolver(
            "ndvi",
            {m: f"/maps/ndvi{m:02d}.map" for m in range(1, 13)},
            ALIGNMENT,
            yearly_from=2001,
            yearly_file_path="/maps/ndvipr.map",
        )

        assert Path(resolver.path_for_step(12)) == Path("/maps/ndvi12.map")
        assert Path(resolver.path_for_step(13)) == Path("/maps/ndvipr.map")
        assert Path(resolver.path_for_step(30)) == Path("/maps/ndvipr.map")

    @pytest.mark.unit
    def test_rejects_incomplete_months_and_half_yearly_settings(self):
        with pytest.raises(ValueError, match="twelve months"):
            MonthlySeriesResolver("ndvi", {1: "/a"}, ALIGNMENT)
        with pytest.raises(ValueError, match="together"):
            MonthlySeriesResolver(
                "ndvi", {m: "/a" for m in range(1, 13)}, ALIGNMENT, yearly_from=2001
            )


class TestCheckCoverage:
    @pytest.mark.unit
    def test_strict_series_block_and_fallback_series_warn(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        resolvers = {
            "precipitation": DirectorySeriesResolver(
                "precipitation", config["DIRECTORIES"]["prec"], "prec"
            ),
            "ndvi": DirectorySeriesResolver("ndvi", config["DIRECTORIES"]["ndvi"], "ndvi"),
        }
        os.remove(os.path.join(config["DIRECTORIES"]["prec"], series_name("prec", 2)))
        os.remove(os.path.join(config["DIRECTORIES"]["ndvi"], series_name("ndvi", 2)))

        problems = check_coverage(resolvers, 1, 2)

        by_description = {p.description: p for p in problems}
        assert by_description["The precipitation raster series is incomplete."].blocking
        assert not by_description["The ndvi raster series has gaps."].blocking
        assert len(problems) == 2

    @pytest.mark.unit
    def test_a_missing_first_fallback_step_blocks(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        os.remove(os.path.join(config["DIRECTORIES"]["ndvi"], series_name("ndvi", 1)))
        resolvers = {"ndvi": DirectorySeriesResolver("ndvi", config["DIRECTORIES"]["ndvi"], "ndvi")}

        problems = check_coverage(resolvers, 1, 2)

        assert [p.blocking for p in problems] == [True]
        assert "lacks the first step" in problems[0].description

    @pytest.mark.unit
    def test_paths_of_dated_entries_must_exist(self, tmp_path):
        resolver = DatedSeriesResolver(
            "landuse",
            [(str(tmp_path / "absent.map"), date(2000, 1, 1), date(2000, 12, 1))],
            ALIGNMENT,
        )

        problems = check_coverage({"landuse": resolver}, 1, 2)

        assert problems and problems[0].blocking

    @pytest.mark.unit
    def test_a_complete_series_reports_nothing(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))

        assert (
            check_coverage(
                resolvers_from_legacy(
                    ModelConfiguration(config, validate_input=False).raster_series
                ),
                1,
                2,
            )
            == []
        )


class TestFactories:
    @pytest.mark.unit
    def test_legacy_resolvers_match_the_directory_series(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        loaded = ModelConfiguration(config, validate_input=False)

        resolvers = loaded.series_resolvers

        assert set(resolvers) == {"precipitation", "etp", "kp", "ndvi", "landuse"}
        assert resolvers["etp"].path_for_step(2).endswith(series_name("etp", 2))
        assert resolvers["landuse"].prefix == "cob"

    @pytest.mark.unit
    def test_v1_resolvers_cover_the_three_specifications(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        legacy = ModelConfigurationFile.model_validate(config)
        document = ModelConfigurationFileV1.from_legacy(legacy).to_dict()
        ndvi_dir = config["DIRECTORIES"]["ndvi"]
        document["raster_series"]["ndvi"] = {
            "monthly": [
                {
                    "month": m,
                    "file_path": os.path.join(ndvi_dir, series_name("ndvi", 1 if m % 2 else 2)),
                }
                for m in range(1, 13)
            ]
        }
        landuse_dir = config["DIRECTORIES"]["landuse"]
        document["raster_series"]["landuse"] = [
            {
                "file_path": os.path.join(landuse_dir, series_name("cob", 1)),
                "from": {"$ref": "#/simulation_period/start"},
                "to": {"$ref": "#/simulation_period/finish"},
            }
        ]
        file = ModelConfigurationFileV1.model_validate(document)

        resolvers = resolvers_from_v1(file)

        assert isinstance(resolvers["etp"], DirectorySeriesResolver)
        assert isinstance(resolvers["ndvi"], MonthlySeriesResolver)
        assert isinstance(resolvers["landuse"], DatedSeriesResolver)
        assert resolvers["ndvi"].path_for_step(2).endswith(series_name("ndvi", 2))
        assert resolvers["landuse"].path_for_step(2).endswith(series_name("cob", 1))
        assert check_coverage(resolvers, 1, 2) == []


class TestCheckSeriesMemberCrs:
    @pytest.mark.unit
    def test_none_when_the_reference_projection_is_unknown(self, tmp_path):
        import numpy as np

        from rubem.preprocessing._io import write_geotiff
        from tests.helpers.compare import ensure_gdal_drivers

        ensure_gdal_drivers()
        member = write_geotiff(
            tmp_path / "m.tif", np.ones((2, 2), np.float32), (0.0, 1.0, 0.0, 2.0, 0.0, -1.0)
        )

        assert check_series_member_crs(str(member), None) is None
        assert check_series_member_crs(str(member), "") is None

    @pytest.mark.unit
    def test_none_for_a_pcraster_map_member(self):
        assert (
            check_series_member_crs("/maps/prec0000.001", 'LOCAL_CS["Grid A",UNIT["metre",1]]')
            is None
        )

    @pytest.mark.unit
    def test_blocks_a_mismatched_crs(self, tmp_path):
        import numpy as np

        from rubem.preprocessing._io import write_geotiff
        from tests.helpers.compare import ensure_gdal_drivers

        ensure_gdal_drivers()
        member = write_geotiff(
            tmp_path / "m.tif",
            np.ones((2, 2), np.float32),
            (0.0, 1.0, 0.0, 2.0, 0.0, -1.0),
            projection='LOCAL_CS["Grid B",UNIT["foot",0.3048]]',
        )

        problem = check_series_member_crs(str(member), 'LOCAL_CS["Grid A",UNIT["metre",1]]')

        assert problem is not None and problem.blocking
        assert "coordinate reference system" in problem.description

    @pytest.mark.unit
    def test_accepts_a_matching_crs(self, tmp_path):
        import numpy as np

        from rubem.preprocessing._io import write_geotiff
        from tests.helpers.compare import ensure_gdal_drivers

        ensure_gdal_drivers()
        member = write_geotiff(
            tmp_path / "m.tif",
            np.ones((2, 2), np.float32),
            (0.0, 1.0, 0.0, 2.0, 0.0, -1.0),
            projection='LOCAL_CS["Grid A",UNIT["metre",1]]',
        )

        assert check_series_member_crs(str(member), 'LOCAL_CS["Grid A",UNIT["metre",1]]') is None


class TestValidateResolvedSeriesCrs:
    @pytest.mark.unit
    def test_a_mismatched_member_crs_is_a_blocking_problem(self, tmp_path):
        from osgeo import gdal

        from tests.helpers.compare import ensure_gdal_drivers

        ensure_gdal_drivers()
        gdal.UseExceptions()
        config = write_synthetic_dataset(str(tmp_path), raster_format="tif")
        loaded = ModelConfiguration(config, validate_input=False)
        member = os.path.join(config["DIRECTORIES"]["prec"], geotiff_series_name("prec", 1))
        dataset = gdal.OpenEx(member, gdal.GA_Update)
        dataset.SetProjection('LOCAL_CS["Grid B",UNIT["foot",0.3048]]')
        dataset = None

        problems = validate_resolved_series(
            loaded.series_resolvers, 1, 2, reference_projection='LOCAL_CS["Grid A",UNIT["metre",1]]'
        )

        blocking = [
            p for p in problems if p.blocking and "coordinate reference system" in p.description
        ]
        assert blocking, problems
