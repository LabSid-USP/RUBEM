import os

import pytest

from tests.helpers.synthetic import write_synthetic_dataset
from tests.unit.core.test_core import expected_outputs, run_model


class TestDynamicModelBehavior:
    @pytest.mark.unit
    def test_ndvi_and_landuse_gaps_fall_back_to_the_previous_step(self, tmp_path):
        """Missing NDVI/LULC steps after the first reuse the previous raster."""
        config = write_synthetic_dataset(str(tmp_path))
        os.remove(tmp_path / "maps" / "ndvi" / "ndvi0000.002")
        os.remove(tmp_path / "maps" / "lulc" / "cob00000.002")

        run_model(str(tmp_path), validate_input=False, config=config)

        output_dir = tmp_path / "out"
        missing = [n for n in expected_outputs() if not (output_dir / n).is_file()]
        assert not missing, f"missing outputs: {missing}"

    @pytest.mark.unit
    def test_disabling_tss_produces_no_time_series(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        config["GENERATE_FILE"]["tss"] = False

        run_model(str(tmp_path), config=config)

        output_dir = tmp_path / "out"
        assert not list(output_dir.glob("tss_*.csv"))
        assert not list(output_dir.glob("*.tss"))

    @pytest.mark.unit
    def test_disabling_a_variable_skips_its_rasters(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        config["GENERATE_FILE"]["itp"] = False

        run_model(str(tmp_path), config=config)

        output_dir = tmp_path / "out"
        assert not list(output_dir.glob("itp*"))
        assert (output_dir / "bfw00000.001").is_file()
