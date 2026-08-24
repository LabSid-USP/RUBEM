import os
import shutil

import pytest

from tests.helpers.compare import compare_rasters
from tests.helpers.synthetic import series_name, write_synthetic_dataset
from tests.unit.core.test_core import expected_outputs, run_model


class TestDynamicModelBehavior:
    @pytest.mark.unit
    def test_ndvi_and_landuse_gaps_fall_back_to_the_previous_step(self, tmp_path):
        """Missing NDVI/LULC steps after the first reuse the previous raster.

        The gap run is compared with two controls: one whose second-step
        rasters duplicate the first step, which it must reproduce exactly, and
        the untouched dataset, whose distinct second-step NDVI it must not
        reproduce. Checking only that the outputs exist would pass for any
        fallback value.
        """
        gap_dir = tmp_path / "gap"
        duplicate_dir = tmp_path / "duplicate"
        distinct_dir = tmp_path / "distinct"

        gap_config = write_synthetic_dataset(str(gap_dir))
        os.remove(gap_dir / "maps" / "ndvi" / series_name("ndvi", 2))
        os.remove(gap_dir / "maps" / "lulc" / series_name("cob", 2))
        run_model(str(gap_dir), validate_input=False, config=gap_config)

        duplicate_config = write_synthetic_dataset(str(duplicate_dir))
        for directory, prefix in (("ndvi", "ndvi"), ("lulc", "cob")):
            maps = duplicate_dir / "maps" / directory
            shutil.copyfile(maps / series_name(prefix, 1), maps / series_name(prefix, 2))
        run_model(str(duplicate_dir), config=duplicate_config)

        run_model(str(distinct_dir))

        missing = [n for n in expected_outputs() if not (gap_dir / "out" / n).is_file()]
        assert not missing, f"missing outputs: {missing}"

        for variable in ("itp", "eta", "srn"):
            name = series_name(variable, 2)
            same = compare_rasters(gap_dir / "out" / name, duplicate_dir / "out" / name)
            assert same.equal, f"{name} differs from the duplicated-input control:\n{same.report()}"

        interception = series_name("itp", 2)
        assert not compare_rasters(
            gap_dir / "out" / interception, distinct_dir / "out" / interception
        ), "the fallback reproduced the second-step NDVI instead of the first"

    @pytest.mark.unit
    def test_disabling_tss_produces_no_time_series(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        config["GENERATE_FILE"]["tss"] = False

        run_model(str(tmp_path), config=config)

        output_dir = tmp_path / "out"
        assert not list(output_dir.glob("tss_*.csv"))
        assert not list(output_dir.glob("*.tss"))

    @pytest.mark.unit
    def test_disabling_a_variable_skips_its_rasters_and_time_series(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        config["GENERATE_FILE"]["itp"] = False

        run_model(str(tmp_path), config=config)

        output_dir = tmp_path / "out"
        assert not list(output_dir.glob("itp*"))
        assert not (output_dir / "tss_itp.csv").exists()
        assert (output_dir / "bfw00000.001").is_file()
        assert (output_dir / "tss_bfw.csv").is_file()

    @pytest.mark.unit
    def test_stale_tss_files_in_the_output_directory_are_left_alone(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        stale = tmp_path / "out" / "stale.tss"
        stale.write_text("1 42.0\n", encoding="utf8")

        run_model(str(tmp_path), config=config)

        assert stale.exists()
        assert not (tmp_path / "out" / "stale.csv").exists()
