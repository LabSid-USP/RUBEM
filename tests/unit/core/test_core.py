import numpy as np
import pytest
from osgeo import gdal

from rubem.configuration.model_configuration import ModelConfiguration
from rubem.core import DynamicFrameworkWrapper
from tests.helpers.synthetic import series_name, write_synthetic_dataset

gdal.UseExceptions()

VARIABLES = ("itp", "bfw", "srn", "eta", "lfw", "rec", "smc", "rnf", "arn")


def expected_outputs(timesteps=2):
    names = []
    for variable in VARIABLES:
        for step in range(1, timesteps + 1):
            names.append(series_name(variable, step))
            names.append(f"{variable}{step:07d}.tif")
        names.append(f"tss_{variable}.csv")
    return names


def run_model(base_dir, validate_input=True, config=None):
    config = config or write_synthetic_dataset(base_dir)
    model_config = ModelConfiguration(config, validate_input=validate_input)
    DynamicFrameworkWrapper.load(model_config).run()
    return config


class TestDynamicFrameworkWrapper:
    @pytest.mark.unit
    def test_full_run_produces_every_output_family(self, tmp_path):
        run_model(str(tmp_path))
        output_dir = tmp_path / "out"
        missing = [n for n in expected_outputs() if not (output_dir / n).is_file()]
        assert not missing, f"missing outputs: {missing}"
        assert not list(output_dir.glob("*.tss")), "tss files must be converted to csv"

    @pytest.mark.unit
    def test_an_embedded_run_writes_nothing_to_stdout(self, tmp_path, capsys):
        """The library reports through logging; only a front end prints."""
        run_model(str(tmp_path))

        assert capsys.readouterr().out == ""

    @pytest.mark.unit
    def test_outputs_are_finite_on_valid_cells(self, tmp_path):
        run_model(str(tmp_path))
        for variable in VARIABLES:
            name = series_name(variable, 1)
            dataset = gdal.Open(str(tmp_path / "out" / name))
            band = dataset.GetRasterBand(1)
            values = band.ReadAsArray().astype(float)
            nodata = band.GetNoDataValue()
            valid = values[~np.isclose(values, nodata)]
            assert valid.size
            assert np.isfinite(valid).all(), f"{name} has non-finite cells"

    @pytest.mark.unit
    def test_time_series_cover_every_station_and_step(self, tmp_path):
        run_model(str(tmp_path))
        data = np.genfromtxt(str(tmp_path / "out" / "tss_arn.csv"), delimiter=";", skip_header=1)
        data = np.atleast_2d(data)
        assert data.shape[0] == 2, "one row per timestep"
        assert data.shape[1] == 3, "step column plus one column per station id"
        assert np.isfinite(data).all()

    @pytest.mark.unit
    def test_two_sequential_runs_in_the_same_process(self, tmp_path):
        first = tmp_path / "first"
        second = tmp_path / "second"
        first.mkdir()
        second.mkdir()
        run_model(str(first))
        run_model(str(second))
        for base in (first, second):
            assert (base / "out" / "tss_arn.csv").is_file()


class TestRunFailureHandling:
    @pytest.mark.unit
    def test_failed_runs_do_not_convert_time_series(self, tmp_path, mocker):
        config = write_synthetic_dataset(str(tmp_path))
        model_config = ModelConfiguration(config, validate_input=False)
        wrapper = DynamicFrameworkWrapper.load(model_config)

        stale_tss = tmp_path / "out" / "tss_itp.tss"
        stale_tss.write_text("1 42.0\n", encoding="utf8")
        mocker.patch.object(wrapper.dynamic_model, "run", side_effect=RuntimeError("boom"))

        with pytest.raises(RuntimeError, match="boom"):
            wrapper.run()

        assert stale_tss.exists(), "sources must survive a failed run"
        assert not (tmp_path / "out" / "tss_itp.csv").exists()
