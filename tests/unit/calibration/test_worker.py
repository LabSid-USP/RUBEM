"""One evaluation of a candidate: the model run, the record and the failure modes."""

import datetime
import json
import os
import shutil
from pathlib import Path

import pytest

from rubem.api import Model
from rubem.calibration._worker import (
    EvaluationContext,
    _derived_document,
    evaluate,
    simulate_best,
)
from rubem.calibration.objective import INADMISSIBLE_OBJECTIVE, read_series
from rubem.calibration.parameters import (
    FREE_PARAMETERS,
    parameters_to_vector,
    vector_to_parameters,
)
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.configuration.model_configuration_file_v1 import (
    VARIABLE_IDS,
    ModelConfigurationFileV1,
)
from tests.helpers.synthetic import write_synthetic_dataset

TIMESTEPS = 3


class Dataset:
    """The synthetic dataset, its configuration and the series a plain run wrote."""

    def __init__(self, tmp_path):
        self.config = write_synthetic_dataset(str(tmp_path), timesteps=TIMESTEPS)
        self.observed_path = Model.from_config(self.config).run().time_series["arn"][0]
        self.configuration = ModelConfiguration(self.config, validate_input=False)
        self.document = ModelConfigurationFileV1.from_legacy(self.configuration.file).to_dict()
        self.vector = parameters_to_vector(self.configuration.calibration_parameters.model_dump())
        self.temp_dir = tmp_path / "temp"
        self.evaluations_dir = tmp_path / "evaluations"
        self.temp_dir.mkdir()
        self.evaluations_dir.mkdir()

    def context(self, observed_path=None, variable="arn", spinup_steps=0, stations=None):
        """An evaluation context reading ``observed_path``, the plain run by default."""
        return EvaluationContext(
            document=self.document,
            base_dir=self.configuration.base_dir,
            variable=variable,
            observed=read_series(observed_path or self.observed_path),
            spinup_steps=spinup_steps,
            temp_dir=str(self.temp_dir),
            evaluations_dir=str(self.evaluations_dir),
            validate_input=False,
            stations=stations,
        )

    def records(self):
        """Every record written so far, without the files still being staged."""
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(self.evaluations_dir.glob("*.json"))
            if not path.name.startswith(".")
        ]

    def staged(self):
        """The staging files left behind by an interrupted write, if any."""
        return [path.name for path in self.evaluations_dir.iterdir() if ".tmp" in path.name]


@pytest.fixture
def dataset(tmp_path):
    return Dataset(tmp_path)


class TestSuccessfulEvaluation:
    @pytest.mark.unit
    def test_the_configuration_of_the_observations_scores_a_perfect_objective(self, dataset):
        # The observed series is what the configuration itself produced, so its
        # own parameters reproduce it exactly: NSE 1, objective 0.
        value = evaluate(dataset.vector, dataset.context())

        assert value == pytest.approx(0.0, abs=1e-9)
        (record,) = dataset.records()
        assert record["error"] is None
        assert record["nse"] == pytest.approx(1.0, abs=1e-12)
        assert record["objective"] == pytest.approx(0.0, abs=1e-9)
        assert record["station_nse"] == {"1": pytest.approx(1.0), "2": pytest.approx(1.0)}
        assert record["parameters"]["w_3"] == pytest.approx(0.334, abs=1e-12)
        assert record["pid"] == os.getpid()
        assert record["elapsed_seconds"] >= 0.0

    @pytest.mark.unit
    def test_the_temporary_output_directory_is_removed_after_the_run(self, dataset):
        evaluate(dataset.vector, dataset.context())

        assert list(dataset.temp_dir.iterdir()) == []

    @pytest.mark.unit
    def test_the_record_is_installed_by_a_rename_and_leaves_no_staging_file(self, dataset):
        evaluate(dataset.vector, dataset.context())

        assert dataset.staged() == []
        assert len(dataset.records()) == 1

    @pytest.mark.unit
    def test_a_different_candidate_is_evaluated_and_scores_worse(self, dataset):
        vector = dataset.vector.copy()
        vector[FREE_PARAMETERS.index("alpha_gw")] = 0.01

        value = evaluate(vector, dataset.context())

        assert 0.0 < value < INADMISSIBLE_OBJECTIVE
        (record,) = dataset.records()
        assert record["error"] is None
        assert record["nse"] < 1.0


class TestDerivedConfiguration:
    @pytest.mark.unit
    def test_it_disables_every_raster_series_and_keeps_one_time_series(self, dataset):
        document = _derived_document(
            dataset.context(), vector_to_parameters(dataset.vector), "/output"
        )
        output = document["model_simulation_output"]
        rasters = output["raster_series"]
        samples = output["time_series_samples"]

        assert output["dir_path"] == "/output"
        assert rasters["formats"] == []
        assert [name for name in VARIABLE_IDS if rasters.get(name)] == []
        assert [name for name in VARIABLE_IDS if samples.get(name)] == ["arn"]
        assert samples["formats"] == ["CSV"]
        assert samples["aggregation"] == "point"
        # What the worker hands to the model has to be a configuration again.
        ModelConfigurationFileV1.model_validate(document)

    @pytest.mark.unit
    def test_the_run_writes_nothing_but_the_table_of_the_calibrated_variable(
        self, dataset, monkeypatch
    ):
        # The output directory is listed on its way out, so that the listing is
        # of the directory the evaluation really wrote and the removal still
        # happens exactly as it does without the test.
        listed = []
        removal = shutil.rmtree

        def spy(path, **kwargs):
            listed.extend(sorted(entry.name for entry in Path(path).rglob("*")))
            removal(path, **kwargs)

        monkeypatch.setattr(shutil, "rmtree", spy)

        evaluate(dataset.vector, dataset.context())

        assert listed == ["metadata.json", "tss_arn.csv"]


class TestRejectedCandidate:
    @pytest.mark.unit
    def test_an_inadmissible_candidate_is_recorded_without_a_model_run(self, dataset):
        vector = dataset.vector.copy()
        vector[FREE_PARAMETERS.index("w_1")] = 0.6
        vector[FREE_PARAMETERS.index("w_2")] = 0.6

        value = evaluate(vector, dataset.context())

        assert value == INADMISSIBLE_OBJECTIVE
        (record,) = dataset.records()
        assert record["error"] == "inadmissible"
        assert record["nse"] is None
        assert record["objective"] == INADMISSIBLE_OBJECTIVE
        assert list(dataset.temp_dir.iterdir()) == [], "no output directory was created"


class TestRecord:
    @pytest.mark.unit
    def test_the_record_is_staged_in_the_directory_it_is_renamed_into(self, dataset, monkeypatch):
        # A rename is atomic only inside one filesystem, so the staging file has
        # to be a sibling of the record and not a file in the system temporary
        # directory, which may be a different mount.
        renames = []
        rename = Path.replace

        def spy(self, target):
            renames.append((Path(self), Path(target)))
            return rename(self, target)

        monkeypatch.setattr(Path, "replace", spy)

        evaluate(dataset.vector, dataset.context())

        installed = [pair for pair in renames if pair[1].parent == dataset.evaluations_dir]
        assert len(installed) == 1, "the record was installed by exactly one rename"
        temporary, target = installed[0]
        assert temporary.parent == dataset.evaluations_dir
        assert temporary.name.startswith(".")
        assert target.name.endswith(".json")


class TestFailedEvaluation:
    @pytest.mark.unit
    def test_observations_of_another_station_are_recorded_as_the_error(self, dataset, tmp_path):
        foreign = tmp_path / "foreign.csv"
        foreign.write_text("0;A;B\n1;1.0;2.0\n2;2.0;3.0\n3;3.0;4.0\n", encoding="utf8")

        value = evaluate(dataset.vector, dataset.context(observed_path=foreign))

        assert value == INADMISSIBLE_OBJECTIVE
        (record,) = dataset.records()
        assert "no station in common" in record["error"]
        assert record["error"].startswith("ValueError: ")
        assert record["nse"] is None
        assert list(dataset.temp_dir.iterdir()) == [], "the output directory was removed anyway"

    @pytest.mark.unit
    def test_a_variable_the_run_does_not_write_is_recorded_as_the_error(self, dataset):
        value = evaluate(dataset.vector, dataset.context(variable="nope"))

        assert value == INADMISSIBLE_OBJECTIVE
        (record,) = dataset.records()
        assert record["error"]
        assert list(dataset.temp_dir.iterdir()) == []


class TestRecordedMetrics:
    @pytest.mark.unit
    def test_the_record_carries_the_moment_the_evaluation_started(self, dataset):
        before = datetime.datetime.now(datetime.UTC)

        evaluate(dataset.vector, dataset.context())

        (record,) = dataset.records()
        started_at = datetime.datetime.fromisoformat(record["started_at"])
        assert started_at.tzinfo is not None, "the moment carries its time zone"
        assert started_at.utcoffset() == datetime.timedelta(0)
        # The wall-clock moment is what puts the records back in the order they
        # were made in, so it has to be the moment of this evaluation.
        assert before <= started_at <= datetime.datetime.now(datetime.UTC)

    @pytest.mark.unit
    def test_the_record_carries_the_goodness_of_fit_of_every_station(self, dataset):
        evaluate(dataset.vector, dataset.context())

        (record,) = dataset.records()
        metrics = record["station_metrics"]

        assert sorted(metrics) == ["1", "2"]
        for measured in metrics.values():
            assert sorted(measured) == [
                "mean_observed",
                "mean_simulated",
                "nse",
                "pairs",
                "r",
                "rmse",
                "std_observed",
                "std_simulated",
            ]
            # The observations are what this very configuration wrote, so the
            # simulation reproduces them exactly.
            assert measured["pairs"] == TIMESTEPS
            assert measured["nse"] == pytest.approx(1.0, abs=1e-12)
            assert measured["rmse"] == pytest.approx(0.0, abs=1e-9)
            assert measured["mean_observed"] == pytest.approx(measured["mean_simulated"])

    @pytest.mark.unit
    def test_the_efficiencies_are_the_ones_of_the_statistics(self, dataset):
        # ``station_nse`` stays for the readers that only want the efficiency;
        # it is taken from the statistics, so the two can never disagree.
        evaluate(dataset.vector, dataset.context())

        (record,) = dataset.records()

        assert record["station_nse"] == {
            station: measured["nse"] for station, measured in record["station_metrics"].items()
        }

    @pytest.mark.unit
    def test_a_rejected_candidate_still_carries_the_moment_and_no_statistics(self, dataset):
        from rubem.calibration.parameters import FREE_PARAMETERS

        vector = dataset.vector.copy()
        vector[FREE_PARAMETERS.index("w_1")] = 0.6
        vector[FREE_PARAMETERS.index("w_2")] = 0.6

        evaluate(vector, dataset.context())

        (record,) = dataset.records()
        assert record["error"] == "inadmissible"
        assert record["station_metrics"] == {}
        assert datetime.datetime.fromisoformat(record["started_at"]).tzinfo is not None

    @pytest.mark.unit
    def test_a_station_outside_the_objective_is_measured_all_the_same(self, dataset):
        # The objective averages station 1 alone; station 2 is reported anyway,
        # which is the validation half of a calibration/validation split.
        value = evaluate(dataset.vector, dataset.context(stations=("1",)))

        assert value == pytest.approx(0.0, abs=1e-9)
        (record,) = dataset.records()
        assert sorted(record["station_metrics"]) == ["1", "2"]
        assert record["nse"] == pytest.approx(1.0, abs=1e-12)

    @pytest.mark.unit
    def test_a_selection_that_names_no_shared_station_fails_the_evaluation(self, dataset):
        from rubem.calibration.objective import INADMISSIBLE_OBJECTIVE

        value = evaluate(dataset.vector, dataset.context(stations=("nowhere",)))

        assert value == INADMISSIBLE_OBJECTIVE
        (record,) = dataset.records()
        assert "none of the stations" in record["error"]


class TestSimulateBest:
    @pytest.mark.unit
    def test_it_runs_the_candidate_and_keeps_the_table_it_wrote(self, dataset, tmp_path):
        from rubem.calibration.parameters import vector_to_parameters

        output_dir = tmp_path / "best"
        output_dir.mkdir()

        table = simulate_best(
            dataset.document,
            dataset.configuration.base_dir,
            vector_to_parameters(dataset.vector),
            str(output_dir),
            "arn",
        )

        # The directory is left in place, which is the whole point: the series
        # of the chosen candidate has to be readable after the run.
        assert Path(table).is_file()
        assert Path(table).parent == output_dir
        assert sorted(entry.name for entry in output_dir.iterdir()) == [
            "metadata.json",
            "tss_arn.csv",
        ]
        series = read_series(table)
        assert sorted(series.stations) == ["1", "2"]
        assert series.steps.tolist() == list(range(1, TIMESTEPS + 1))

    @pytest.mark.unit
    def test_it_reproduces_the_series_of_the_configuration_it_is_given(self, dataset, tmp_path):
        from rubem.calibration.parameters import vector_to_parameters

        output_dir = tmp_path / "best"
        output_dir.mkdir()

        table = simulate_best(
            dataset.document,
            dataset.configuration.base_dir,
            vector_to_parameters(dataset.vector),
            str(output_dir),
            "arn",
        )

        simulated = read_series(table)
        observed = read_series(dataset.observed_path)
        for station, values in observed.stations.items():
            assert simulated.stations[station].tolist() == pytest.approx(values.tolist())

    @pytest.mark.unit
    def test_a_variable_the_run_does_not_write_raises(self, dataset, tmp_path):
        from rubem.calibration.parameters import vector_to_parameters

        output_dir = tmp_path / "best"
        output_dir.mkdir()

        # Unlike an evaluation, this one has nothing to rank a failure behind.
        with pytest.raises(Exception, match="nope"):
            simulate_best(
                dataset.document,
                dataset.configuration.base_dir,
                vector_to_parameters(dataset.vector),
                str(output_dir),
                "nope",
            )
