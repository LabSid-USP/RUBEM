from datetime import datetime

import numpy as np
import pytest
from osgeo import gdal

from rubem.configuration.simulation_period import SimulationPeriod
from tests.helpers.synthetic import series_name, write_synthetic_dataset
from tests.unit.core.test_core import expected_outputs, run_model

gdal.UseExceptions()

DATE_FORMAT = "%d/%m/%Y"


def read_map(path):
    dataset = gdal.Open(str(path))
    return dataset.GetRasterBand(1).ReadAsArray().astype(float)


class TestSyntheticDataset:
    @pytest.mark.unit
    def test_a_single_step_is_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="at least 2"):
            write_synthetic_dataset(str(tmp_path), timesteps=1)

    @pytest.mark.unit
    @pytest.mark.parametrize("timesteps", [2, 12, 13, 25])
    def test_the_period_spans_the_requested_steps(self, tmp_path, timesteps):
        """Beyond one calendar year the end date must roll into the next."""
        config = write_synthetic_dataset(str(tmp_path), timesteps=timesteps)

        period = SimulationPeriod(
            start=datetime.strptime(config["SIM_TIME"]["start"], DATE_FORMAT),
            end=datetime.strptime(config["SIM_TIME"]["end"], DATE_FORMAT),
        )

        assert period.total_steps == timesteps

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "step, expected",
        [
            (1, "ndvi0000.001"),
            (999, "ndvi0000.999"),
            (1000, "ndvi0001.000"),
            (12345, "ndvi0012.345"),
        ],
    )
    def test_series_names_keep_the_pcraster_8_3_convention(self, step, expected):
        """Digits beyond the three-character extension move into the stem."""
        assert series_name("ndvi", step) == expected

    @pytest.mark.unit
    def test_land_use_alternates_between_classes(self, tmp_path):
        """Tests that compare land-use handling need consecutive steps to differ."""
        write_synthetic_dataset(str(tmp_path), timesteps=4)
        classes = [
            set(np.unique(read_map(tmp_path / "maps" / "lulc" / series_name("cob", step))))
            for step in range(1, 5)
        ]
        assert classes[0] != classes[1], "consecutive land-use steps must differ"
        assert classes[0] == classes[2], "the land-use series must cycle"

    @pytest.mark.unit
    def test_ndvi_stays_within_the_declared_bounds(self, tmp_path):
        """NDVI must never reach 1.0, where the simple ratio divides by zero."""
        config = write_synthetic_dataset(str(tmp_path), timesteps=25)
        low = read_map(config["RASTERS"]["ndvi_min"]).min()
        high = read_map(config["RASTERS"]["ndvi_max"]).max()

        for step in range(1, 26):
            values = read_map(tmp_path / "maps" / "ndvi" / series_name("ndvi", step))
            assert values.min() >= low, f"step {step} is below ndvi_min"
            assert values.max() <= high, f"step {step} is above ndvi_max"

    @pytest.mark.unit
    def test_a_year_crossing_run_produces_finite_outputs(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path), timesteps=13)

        run_model(str(tmp_path), config=config)

        output_dir = tmp_path / "out"
        missing = [n for n in expected_outputs(timesteps=13) if not (output_dir / n).is_file()]
        assert not missing, f"missing outputs: {missing}"
        values = read_map(output_dir / "eta00000.010")
        assert np.isfinite(values[values != -9999.0]).all()
