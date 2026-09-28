"""The dynamic model coupled to a mocked PCRaster MODFLOW extension.

The synthetic dataset runs two monthly steps (January 2000, 31 days, and
February 2000, 29 days) with the three-layer section of
:func:`write_modflow_inputs`. The extension is a :class:`unittest.mock.Mock`
whose getters return fields the test controls, so the coupling formulas are
checked against known heads and leakages without ``mf2005``; the runs against
the real executable live in ``tests/integration/test_modflow_coupling.py``.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pcraster as pcr
import pytest

from rubem.configuration.model_configuration import ModelConfiguration
from rubem.core import DynamicFrameworkWrapper
from rubem.hydrological_processes import Evapotranspiration, _modflow
from tests.helpers.compare import compare_csv, compare_rasters
from tests.helpers.synthetic import (
    CELL_SIZE,
    ROOTZONE_DEPTH,
    geotiff_series_name,
    series_name,
    write_minimum_root_depth_table,
    write_modflow_inputs,
    write_synthetic_dataset,
)
from tests.unit.core.test_core import expected_outputs, run_model

pytestmark = pytest.mark.unit

CELL_AREA = CELL_SIZE * CELL_SIZE
DAYS = {1: 31, 2: 29}
LEAKAGE = -2.0  # m3/day, out of the aquifer on every cell
MINIMUM_ROOT_DEPTH = 30.0  # cm


def read(path):
    """A PCRaster map or a GeoTIFF as an array (missing: NaN)."""
    return pcr.pcr2numpy(pcr.scalar(pcr.readmap(str(path))), np.nan)


def dem(config):
    pcr.setclone(config["RASTERS"]["clone"])
    return read(config["RASTERS"]["dem"])


def modflow_outputs(directory):
    return sorted(path.name for path in Path(directory).iterdir() if path.name.startswith("mf"))


class Extension:
    """The mocked extension and what the model did with it."""

    def __init__(self, monkeypatch):
        self.mf = Mock()
        self.mf.converged.return_value = True
        self.mf.getRiverLeakage.side_effect = lambda layer: pcr.spatial(pcr.scalar(LEAKAGE))
        self.mf.getStorage.side_effect = lambda layer: pcr.spatial(pcr.scalar(10.0 * layer))
        self.mf.getDrain.side_effect = lambda layer: pcr.spatial(pcr.scalar(-1.0))
        self.depth_below_dem = 10.0  # m, the head of every layer below the DEM
        self.dem = None
        self.mf.getHeads.side_effect = self._heads
        self.run_directories = []
        self.mf.run.side_effect = self._run
        monkeypatch.setattr(_modflow, "_initialise", lambda clone: self.mf)
        monkeypatch.setattr(_modflow, "ensure_mf2005_on_path", lambda: Path("mf2005"))
        monkeypatch.setattr("rubem.validation.modflow_inputs.missing_groundwater_deps", lambda: [])

    def _heads(self, layer):
        return pcr.numpy2pcr(pcr.Scalar, self.dem - self.depth_below_dem, np.nan)

    def _run(self, directory):
        path = Path(directory)
        assert path.is_dir(), "MODFLOW runs in a directory that exists"
        self.run_directories.append(path)

    def recharge(self):
        """The recharge rate given to the extension at each step [m/day]."""
        return [pcr.pcr2numpy(call.args[0], np.nan) for call in self.mf.setRecharge.call_args_list]


@pytest.fixture(name="extension")
def extension_fixture(monkeypatch):
    return Extension(monkeypatch)


def coupled_config(directory, extension, **section_updates):
    config = write_synthetic_dataset(str(directory))
    section = write_modflow_inputs(config)
    section.update(section_updates)
    config["MODFLOW"] = section
    extension.dem = dem(config)
    return config


def root_depth_coupling(config):
    return {
        "enabled": True,
        "minimum_depth_table": write_minimum_root_depth_table(config, MINIMUM_ROOT_DEPTH),
        "water_table": {"method": "highest_active_head"},
    }


def run(config):
    wrapper = DynamicFrameworkWrapper.load(ModelConfiguration(config, validate_input=False))
    wrapper.run()
    return wrapper.dynamic_model_concept


class TestBaseflow:
    def test_the_baseflow_is_the_aquifer_to_river_leakage_of_the_step(self, tmp_path, extension):
        config = coupled_config(tmp_path, extension)

        run(config)

        out = tmp_path / "out"
        for step, days in DAYS.items():
            expected = -LEAKAGE * days * 1000.0 / CELL_AREA
            np.testing.assert_allclose(read(out / series_name("bfw", step)), expected, rtol=1e-6)

    def test_the_recharge_of_each_step_reaches_modflow_per_day(self, tmp_path, extension):
        config = coupled_config(tmp_path, extension)

        run(config)

        out = tmp_path / "out"
        rates = extension.recharge()
        assert len(rates) == len(DAYS)
        for (step, days), rate in zip(DAYS.items(), rates, strict=True):
            recharge = read(out / series_name("rec", step))
            np.testing.assert_allclose(rate, recharge / (1000.0 * days), rtol=1e-6)
        periods = [call.args[0] for call in extension.mf.updateDISParameter.call_args_list]
        assert periods == list(DAYS.values())

    def test_the_saturated_zone_is_frozen(self, tmp_path, extension):
        config = coupled_config(tmp_path, extension)

        model = run(config)

        initial = config["INITIAL_SOIL_CONDITIONS"]
        storage = pcr.pcr2numpy(pcr.spatial(model.current_soil_sat_zone_storage), np.nan)
        np.testing.assert_array_equal(storage, np.float32(initial["s_sat_ini"]))
        baseflow = pcr.pcr2numpy(pcr.spatial(model.previous_baseflow), np.nan)
        np.testing.assert_array_equal(baseflow, np.float32(initial["bfw_ini"]))


class TestRunDirectory:
    def test_modflow_runs_under_the_output_directory_and_it_is_removed(self, tmp_path, extension):
        config = coupled_config(tmp_path, extension)

        model = run(config)

        run_directory = tmp_path / "out" / "modflow"
        assert extension.run_directories == [run_directory] * len(DAYS)
        assert not run_directory.exists()
        assert model.modflow is None

    def test_a_failed_step_keeps_the_run_directory(self, tmp_path, extension):
        config = coupled_config(tmp_path, extension)
        extension.mf.converged.return_value = False

        with pytest.raises(RuntimeError, match="did not converge in stress period 1"):
            run(config)

        assert (tmp_path / "out" / "modflow").is_dir()

    def test_an_existing_run_directory_is_refused_and_kept(self, tmp_path, extension):
        # The run removes its directory at the end, so it may not adopt one.
        config = coupled_config(tmp_path, extension)
        notes = tmp_path / "out" / "modflow" / "notes.txt"
        notes.parent.mkdir(parents=True)
        notes.write_text("kept", encoding="utf8")

        with pytest.raises(RuntimeError, match="already exists") as error:
            run(config)

        assert str(notes.parent) in str(error.value)
        assert notes.read_text(encoding="utf8") == "kept"
        assert extension.mf.mock_calls == []

    def test_a_failed_start_removes_the_new_run_directory(self, tmp_path, extension, monkeypatch):
        config = coupled_config(tmp_path, extension)

        def missing_extension(clone):
            raise RuntimeError("no extension")

        monkeypatch.setattr(_modflow, "_initialise", missing_extension)

        with pytest.raises(RuntimeError, match="no extension"):
            run(config)

        assert (tmp_path / "out").is_dir()
        assert not (tmp_path / "out" / "modflow").exists()

    def test_the_default_run_creates_no_run_directory(self, tmp_path):
        run_model(str(tmp_path))

        assert not (tmp_path / "out" / "modflow").exists()


class TestDiagnostics:
    def test_heads_and_river_exchange_are_written_in_both_formats(self, tmp_path, extension):
        config = coupled_config(tmp_path, extension)

        run(config)

        out = tmp_path / "out"
        for step in DAYS:
            for prefix in ("mfh1", "mfh2", "mfh3", "mfaq2rv", "mfrv2aq", "mfrvnet"):
                assert (out / series_name(prefix, step)).is_file(), (prefix, step)
                assert (out / geotiff_series_name(prefix, step)).is_file(), (prefix, step)
            np.testing.assert_allclose(read(out / series_name("mfaq2rv", step)), -LEAKAGE)
            np.testing.assert_allclose(read(out / series_name("mfrv2aq", step)), 0.0)
            np.testing.assert_allclose(read(out / series_name("mfrvnet", step)), LEAKAGE)
            np.testing.assert_allclose(
                read(out / series_name("mfh1", step)), extension.dem - 10.0, rtol=1e-6
            )
        assert not [name for name in modflow_outputs(out) if name.startswith(("mfst", "mfdrn"))]

    def test_storage_and_drain_flow_are_written_per_layer(self, tmp_path, extension):
        config = coupled_config(tmp_path, extension)
        section = config["MODFLOW"]
        section["drain"] = {
            "enabled": True,
            "entries": [
                {
                    "layers": [2],
                    "elevation": section["layers"][1]["bottom"],
                    "conductance": section["ghb"]["entries"][0]["conductance"],
                }
            ],
        }
        section["output"] = {"storage": True, "drain_flow": True}

        run(config)

        out = tmp_path / "out"
        for step in DAYS:
            for number in (1, 2, 3):
                storage = read(out / series_name(f"mfst{number}", step))
                # User layer n is extension layer 4 - n.
                np.testing.assert_allclose(storage, 10.0 * (4 - number))
            np.testing.assert_allclose(read(out / series_name("mfdrn2", step)), -1.0)
        assert not [name for name in modflow_outputs(out) if name.startswith(("mfdrn1", "mfdrn3"))]

    def test_disabled_diagnostics_are_not_written(self, tmp_path, extension):
        config = coupled_config(
            tmp_path, extension, output={"heads": False, "river_leakage": False}
        )

        run(config)

        assert modflow_outputs(tmp_path / "out") == []

    def test_nothing_is_written_without_a_raster_format(self, tmp_path, extension):
        config = coupled_config(tmp_path, extension, output={"storage": True})
        config["MODFLOW"]["coupling"] = {"dynamic_root_depth": root_depth_coupling(config)}
        config["MODFLOW"]["output"]["root_depth"] = True
        config["RASTER_FILE_FORMAT"] = {"map_raster_series": False, "tiff_raster_series": False}
        config["GENERATE_FILE"] = {key: False for key in config["GENERATE_FILE"]}

        run(config)

        assert sorted(path.name for path in (tmp_path / "out").iterdir()) == []


class TestRootDepthCoupling:
    """The previous step's water table restricts the vegetation root depth."""

    @pytest.fixture(name="stress")
    def stress_fixture(self, monkeypatch):
        """The soil water stress coefficient of the vegetated and the bare-soil area, per call."""
        calls = {"vegetated": [], "bare": [], "arguments": []}
        vegetated_coef = Evapotranspiration.get_water_stress_coef_et_vegetated_area
        vegetated_et = Evapotranspiration.get_et_vegetated_area
        bare_et = Evapotranspiration.get_water_stress_coef_et_bare_soil_area

        def coef(moisture, wilting_point, field_capacity):
            calls["arguments"].append(
                [
                    pcr.pcr2numpy(pcr.spatial(pcr.scalar(item)), np.nan)
                    for item in (moisture, wilting_point, field_capacity)
                ]
            )
            return vegetated_coef(moisture, wilting_point, field_capacity)

        def vegetated(potential, crop, water_stress):
            calls["vegetated"].append(pcr.pcr2numpy(pcr.spatial(water_stress), np.nan))
            return vegetated_et(potential, crop, water_stress)

        def bare(potential, crop, water_stress):
            calls["bare"].append(pcr.pcr2numpy(pcr.spatial(water_stress), np.nan))
            return bare_et(potential, crop, water_stress)

        monkeypatch.setattr(
            Evapotranspiration, "get_water_stress_coef_et_vegetated_area", staticmethod(coef)
        )
        monkeypatch.setattr(Evapotranspiration, "get_et_vegetated_area", staticmethod(vegetated))
        monkeypatch.setattr(
            Evapotranspiration, "get_water_stress_coef_et_bare_soil_area", staticmethod(bare)
        )
        return calls

    def coupled_run(self, directory, extension, depth_below_dem, coupling=True):
        config = coupled_config(directory, extension, output={"root_depth": True})
        if coupling:
            config["MODFLOW"]["coupling"] = {"dynamic_root_depth": root_depth_coupling(config)}
        extension.depth_below_dem = depth_below_dem
        run(config)
        return directory / "out"

    def test_the_root_depth_follows_the_previous_water_table(self, tmp_path, extension):
        """Head 0.5 m below the DEM: 50 cm of roots at step 2, none of it at step 1."""
        out = self.coupled_run(tmp_path, extension, depth_below_dem=0.5)

        np.testing.assert_allclose(read(out / series_name("mfwt", 1)), extension.dem - 0.5)
        np.testing.assert_allclose(read(out / series_name("mfzr", 1)), ROOTZONE_DEPTH, rtol=1e-6)
        np.testing.assert_allclose(read(out / series_name("mfzfrac", 1)), 1.0)
        assert np.isnan(read(out / series_name("mfgwd", 1))).all()
        np.testing.assert_allclose(read(out / series_name("mfgwd", 2)), 50.0, rtol=1e-4)
        np.testing.assert_allclose(read(out / series_name("mfzr", 2)), 50.0, rtol=1e-4)
        np.testing.assert_allclose(
            read(out / series_name("mfzfrac", 2)), 50.0 / ROOTZONE_DEPTH, rtol=1e-4
        )
        for step in DAYS:
            for prefix in ("mfwt", "mfzr", "mfzfrac", "mfgwd"):
                assert (out / geotiff_series_name(prefix, step)).is_file(), (prefix, step)

    def test_the_minimum_root_depth_bounds_a_shallow_water_table(self, tmp_path, extension):
        out = self.coupled_run(tmp_path, extension, depth_below_dem=0.1)

        np.testing.assert_allclose(read(out / series_name("mfgwd", 2)), 10.0, rtol=1e-3)
        np.testing.assert_allclose(
            read(out / series_name("mfzr", 2)), MINIMUM_ROOT_DEPTH, rtol=1e-6
        )

    def test_a_head_above_the_ground_counts_as_no_depth(self, tmp_path, extension):
        out = self.coupled_run(tmp_path, extension, depth_below_dem=-2.0)

        np.testing.assert_allclose(read(out / series_name("mfgwd", 2)), 0.0)
        np.testing.assert_allclose(
            read(out / series_name("mfzr", 2)), MINIMUM_ROOT_DEPTH, rtol=1e-6
        )

    def test_a_cell_without_a_valid_head_keeps_every_root(self, tmp_path, extension):
        extension.mf.getHeads.side_effect = lambda layer: pcr.spatial(pcr.scalar(_modflow.DRY_HEAD))

        config = coupled_config(tmp_path, extension, output={"root_depth": True})
        config["MODFLOW"]["coupling"] = {"dynamic_root_depth": root_depth_coupling(config)}
        run(config)

        out = tmp_path / "out"
        np.testing.assert_allclose(read(out / series_name("mfzr", 2)), ROOTZONE_DEPTH, rtol=1e-6)
        np.testing.assert_allclose(read(out / series_name("mfzfrac", 2)), 1.0)

    def test_only_the_vegetation_feels_the_restricted_roots(self, tmp_path, extension, stress):
        """Step 2: the vegetated area sees the root fraction, the bare soil does not."""
        self.coupled_run(tmp_path / "plain", extension, depth_below_dem=0.5, coupling=False)
        plain = {key: list(values) for key, values in stress.items()}
        for values in stress.values():
            values.clear()
        self.coupled_run(tmp_path / "coupled", extension, depth_below_dem=0.5)
        coupled = stress

        # The coupled run computes two coefficients per step: soil, then vegetation.
        assert len(plain["arguments"]) == len(DAYS)
        assert len(coupled["arguments"]) == 2 * len(DAYS)
        # Step 1 has no previous head: both runs are the same.
        np.testing.assert_array_equal(coupled["vegetated"][0], plain["vegetated"][0])
        np.testing.assert_array_equal(coupled["bare"][0], plain["bare"][0])
        # Step 2: the soil coefficient is unchanged and feeds the bare soil ...
        np.testing.assert_array_equal(coupled["bare"][1], plain["bare"][1])
        np.testing.assert_array_equal(coupled["arguments"][2], plain["arguments"][1])
        # ... and the vegetation takes the coefficient of the storages scaled by the fraction.
        fraction = np.float32(50.0 / ROOTZONE_DEPTH)
        scaled = coupled["arguments"][3]
        for full, restricted in zip(plain["arguments"][1], scaled, strict=True):
            np.testing.assert_allclose(restricted, full * fraction, rtol=1e-4)
        assert not np.allclose(coupled["vegetated"][1], plain["vegetated"][1])

    def test_a_deep_water_table_changes_nothing(self, tmp_path, extension):
        """Heads 10 m below the DEM leave the roots (Zr about 1.5 m) whole."""
        plain = self.coupled_run(
            tmp_path / "plain", extension, depth_below_dem=10.0, coupling=False
        )
        coupled = self.coupled_run(tmp_path / "coupled", extension, depth_below_dem=10.0)

        for name in expected_outputs():
            compare = compare_csv if name.endswith(".csv") else compare_rasters
            result = compare(plain / name, coupled / name, rtol=0.0, atol=0.0)
            assert result.equal, f"{name}:\n{result.report()}"

    def test_the_root_depth_diagnostics_need_the_output_flag(self, tmp_path, extension):
        config = coupled_config(tmp_path, extension)
        config["MODFLOW"]["coupling"] = {"dynamic_root_depth": root_depth_coupling(config)}

        run(config)

        written = modflow_outputs(tmp_path / "out")
        assert not [name for name in written if name.startswith(("mfwt", "mfzr", "mfgwd"))]

    def test_the_step_fields_are_released(self, tmp_path, extension):
        config = coupled_config(tmp_path, extension, output={"root_depth": True})
        config["MODFLOW"]["coupling"] = {"dynamic_root_depth": root_depth_coupling(config)}

        model = run(config)

        released = ("effective_root_depth", "root_depth_fraction", "groundwater_depth_cm")
        assert [name for name in released if getattr(model, name) is not None] == []
        for name in ("soil_rootzone_depth_min", "surface_elevation", "previous_water_table_head"):
            assert getattr(model, name) is not None, name


class TestDefaultPath:
    def test_an_absent_or_disabled_section_gives_the_same_outputs(self, tmp_path):
        """No output moves when the section is absent, disabled or empty and disabled."""
        reference = tmp_path / "absent"
        run_model(str(reference))

        disabled = tmp_path / "disabled"
        config = write_synthetic_dataset(str(disabled))
        config["MODFLOW"] = {**write_modflow_inputs(config), "enabled": False}
        run_model(str(disabled), config=config)

        empty = tmp_path / "empty"
        config = write_synthetic_dataset(str(empty))
        config["MODFLOW"] = {"enabled": False}
        run_model(str(empty), config=config)

        for other in (disabled, empty):
            names = sorted(path.name for path in (other / "out").iterdir())
            assert names == sorted(path.name for path in (reference / "out").iterdir())
            for name in expected_outputs():
                compare = compare_csv if name.endswith(".csv") else compare_rasters
                result = compare(reference / "out" / name, other / "out" / name, rtol=0.0, atol=0.0)
                assert result.equal, f"{other.name} {name}:\n{result.report()}"

    def test_the_dynamic_model_does_not_import_the_groundwater_module(self):
        code = (
            "import sys, rubem._dynamic_model; "
            "sys.exit('rubem.hydrological_processes._modflow' in sys.modules)"
        )
        completed = subprocess.run([sys.executable, "-c", code], check=False)

        assert completed.returncode == 0
