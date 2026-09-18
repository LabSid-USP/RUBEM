"""The calibration objective: masks, Nash-Sutcliffe efficiency, tables and alignment."""

import dataclasses

import numpy as np
import pytest

from rubem.calibration.objective import (
    INADMISSIBLE_OBJECTIVE,
    MISSING_VALUES,
    PCRASTER_MISSING,
    Series,
    StationMetrics,
    evaluate_series,
    nash_sutcliffe,
    objective,
    read_series,
    station_metrics,
    valid_mask,
)

# The PCRaster missing value as it comes back from a Float32 raster or table:
# 1e31 has no exact Float32 representation, so what is read is slightly below it.
FLOAT32_MISSING = float(np.float32(1e31))

# Every gap marker, used wherever a test drops a pair through one of them.
GAPS = (float("nan"), -9999.0, -1.0, 1e31, FLOAT32_MISSING)


def nse_of(metrics):
    """The efficiency of every station of a mapping of :class:`StationMetrics`."""
    return {station: measured.nse for station, measured in metrics.items()}


def series(steps, **stations):
    """A :class:`Series` built from plain lists, as the readers produce it."""
    return Series(
        steps=np.asarray(steps, dtype=np.int64),
        stations={
            station: np.asarray(values, dtype=np.float64) for station, values in stations.items()
        },
    )


class TestValidMask:
    @pytest.mark.unit
    def test_ordinary_values_are_valid(self):
        assert valid_mask(np.array([0.0, 1.5, 3.25, 1e29])).tolist() == [True] * 4

    @pytest.mark.unit
    @pytest.mark.parametrize("negative", [-1.0, -999.0, -0.5, -9999.0])
    def test_a_negative_value_is_a_gap(self, negative):
        # Every quantity the two series carry is a flux or a storage: a
        # negative entry is a marker of a gap, whichever one a gauge writes.
        assert valid_mask(np.array([negative])).tolist() == [False]

    @pytest.mark.unit
    def test_zero_is_a_value_and_not_a_gap(self):
        # A station may record no flow at all; only the sign below zero is a gap.
        assert valid_mask(np.array([0.0, -0.0])).tolist() == [True, True]

    @pytest.mark.unit
    @pytest.mark.parametrize("gap", GAPS)
    def test_every_gap_marker_is_masked(self, gap):
        assert valid_mask(np.array([1.0, gap, 2.0])).tolist() == [True, False, True]

    @pytest.mark.unit
    def test_the_documented_markers_are_the_ones_the_mask_rejects(self):
        assert MISSING_VALUES == (-9999.0,)
        assert PCRASTER_MISSING == 1e31
        assert not valid_mask(np.array([PCRASTER_MISSING])).any()

    @pytest.mark.unit
    def test_infinities_are_masked(self):
        assert valid_mask(np.array([np.inf, -np.inf])).tolist() == [False, False]

    @pytest.mark.unit
    def test_the_threshold_itself_is_the_first_value_rejected(self):
        # The mask keeps everything strictly below 1e30 and drops 1e30 itself,
        # which is what makes the Float32 round-trip of 1e31 a gap as well.
        below = float(np.nextafter(1e30, 0.0))

        assert valid_mask(np.array([below, 1e30])).tolist() == [True, False]
        assert below < 1e30 < FLOAT32_MISSING


class TestNashSutcliffe:
    @pytest.mark.unit
    def test_an_exact_simulation_gives_one(self):
        # residuals 0 / variability 2 -> NSE = 1 - 0 = 1.0
        observed = np.array([1.0, 2.0, 3.0])

        assert nash_sutcliffe(observed.copy(), observed) == 1.0

    @pytest.mark.unit
    def test_the_mean_of_the_observations_gives_zero(self):
        # observed [1, 2, 3], mean 2; simulated [2, 2, 2]
        # residuals (1 + 0 + 1) = 2, variability (1 + 0 + 1) = 2 -> NSE = 1 - 2/2 = 0.0
        assert nash_sutcliffe(np.array([2.0, 2.0, 2.0]), np.array([1.0, 2.0, 3.0])) == 0.0

    @pytest.mark.unit
    def test_a_reversed_simulation_gives_a_negative_efficiency(self):
        # observed [1, 2, 3], mean 2; simulated [3, 2, 1]
        # residuals (4 + 0 + 4) = 8, variability 2 -> NSE = 1 - 8/2 = -3.0
        assert nash_sutcliffe(np.array([3.0, 2.0, 1.0]), np.array([1.0, 2.0, 3.0])) == -3.0

    @pytest.mark.unit
    @pytest.mark.parametrize("gap", GAPS)
    def test_a_gap_in_the_observations_drops_the_pair(self, gap):
        # The fourth pair is dropped, the first three are exact -> NSE = 1.0
        simulated = np.array([1.0, 2.0, 3.0, 99.0])
        observed = np.array([1.0, 2.0, 3.0, gap])

        assert nash_sutcliffe(simulated, observed) == 1.0

    @pytest.mark.unit
    @pytest.mark.parametrize("gap", GAPS)
    def test_a_gap_in_the_simulation_drops_the_pair(self, gap):
        # Dropping the fourth pair leaves observed [1, 2, 3] with mean 2 and
        # simulated [3, 2, 1]: residuals 8, variability 2 -> NSE = -3.0
        simulated = np.array([3.0, 2.0, 1.0, gap])
        observed = np.array([1.0, 2.0, 3.0, 4.0])

        assert nash_sutcliffe(simulated, observed) == -3.0

    @pytest.mark.unit
    def test_a_gap_is_dropped_from_the_mean_of_the_observations(self):
        # The third pair is dropped by the simulation, so the mean is that of
        # [1, 3] = 2 and not that of [1, 3, 8]: variability (1 + 1) = 2,
        # residuals (1 + 1) = 2 -> NSE = 1 - 2/2 = 0.0
        simulated = np.array([2.0, 2.0, float("nan")])
        observed = np.array([1.0, 3.0, 8.0])

        assert nash_sutcliffe(simulated, observed) == 0.0

    @pytest.mark.unit
    def test_a_single_valid_pair_has_no_efficiency(self):
        assert nash_sutcliffe(np.array([1.0, 2.0]), np.array([1.0, float("nan")])) is None

    @pytest.mark.unit
    def test_a_station_without_one_valid_pair_has_no_efficiency(self):
        # No pair survives the mask at all: the count guard must answer before
        # anything is read out of the empty selection.
        assert nash_sutcliffe(np.array([1.0, -9999.0]), np.array([np.nan, 2.0])) is None
        assert nash_sutcliffe(np.array([np.nan, np.nan]), np.array([np.nan, np.nan])) is None

    @pytest.mark.unit
    def test_two_valid_pairs_are_enough(self):
        # observed [1, 3], mean 2, variability 2; simulated [1, 3] -> NSE = 1.0
        simulated = np.array([1.0, 3.0, 5.0])
        observed = np.array([1.0, 3.0, -9999.0])

        assert nash_sutcliffe(simulated, observed) == 1.0

    @pytest.mark.unit
    def test_observations_without_variance_have_no_efficiency(self):
        # The sum of the squared deviations of [0.1, 0.1, 0.1] is not exactly
        # zero in floating point, so constancy is what the guard must test.
        assert nash_sutcliffe(np.array([0.1, 0.2, 0.3]), np.array([0.1, 0.1, 0.1])) is None

    @pytest.mark.unit
    def test_only_the_valid_observations_decide_the_variance(self):
        # The valid observations are [5, 5]: constant, so there is no efficiency
        # although the series as written also carries a 7.
        assert nash_sutcliffe(np.array([5.0, 5.0, np.nan]), np.array([5.0, 5.0, 7.0])) is None

    @pytest.mark.unit
    def test_series_of_different_lengths_are_refused(self):
        with pytest.raises(ValueError, match="same shape"):
            nash_sutcliffe(np.array([1.0, 2.0]), np.array([1.0, 2.0, 3.0]))


class TestObjective:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("nse", "expected"),
        [
            # 1000 * (100 * (1 - 1))^2 = 0
            (1.0, 0.0),
            # 1000 * (100 * 1)^2 = 1000 * 10000 = 1e7
            (0.0, 1.0e7),
            # 1000 * (100 * 2)^2 = 1000 * 40000 = 4e7
            (-1.0, 4.0e7),
        ],
    )
    def test_the_objective_of_a_known_efficiency(self, nse, expected):
        assert objective(nse) == expected

    @pytest.mark.unit
    def test_the_inadmissible_objective_is_far_above_any_run(self):
        # An NSE of -100 is an absurd simulation and still gives ~1.02e11.
        assert objective(-100.0) < INADMISSIBLE_OBJECTIVE / 1e10
        assert np.isfinite(INADMISSIBLE_OBJECTIVE)


class TestReadSeries:
    @pytest.mark.unit
    def test_a_handwritten_table_in_the_model_csv_layout(self, tmp_path):
        path = tmp_path / "tss_arn.csv"
        path.write_text("0;1;2\n1;1.5;2.5\n2;3.5;4.5\n3;5.5;6.5\n", encoding="utf8")

        table = read_series(path)

        assert table.steps.tolist() == [1, 2, 3]
        assert sorted(table.stations) == ["1", "2"]
        assert table.stations["1"].tolist() == [1.5, 3.5, 5.5]
        assert table.stations["2"].tolist() == [2.5, 4.5, 6.5]

    @pytest.mark.unit
    def test_gaps_of_a_csv_table_are_kept_as_written(self, tmp_path):
        path = tmp_path / "observed.csv"
        path.write_text("0;A;B\n1;-9999;2.0\n2;1e31;\n", encoding="utf8")

        table = read_series(path)

        assert table.stations["A"].tolist() == [-9999.0, 1e31]
        assert table.stations["B"][0] == 2.0
        assert np.isnan(table.stations["B"][1]), "an empty cell is a gap"
        assert valid_mask(table.stations["A"]).tolist() == [False, False]

    @pytest.mark.unit
    def test_the_ids_of_a_real_run_are_the_ids_of_the_sample_raster(self, tmp_path):
        """The table the model writes must be readable exactly as it lands."""
        from tests.unit.core.test_core import run_model

        run_model(str(tmp_path))

        table = read_series(tmp_path / "out" / "tss_arn.csv")

        # The synthetic dataset marks two sample locations, with the ids 1 and 2.
        assert sorted(table.stations) == ["1", "2"]
        assert table.steps.tolist() == [1, 2]
        for values in table.stations.values():
            assert values.shape == (2,)
            assert valid_mask(values).all()

    @pytest.mark.unit
    def test_the_windows_line_endings_the_model_writes(self, tmp_path):
        # rubem.file._file_conversions.tss2csv writes through csv.writer, whose
        # line terminator is CRLF; the reader must not take the carriage return
        # for part of the last value of a row.
        path = tmp_path / "tss_arn.csv"
        path.write_bytes(b"0;1;2\r\n1;1.5;2.5\r\n2;3.5;4.5\r\n")

        table = read_series(path)

        assert table.steps.tolist() == [1, 2]
        assert table.stations["2"].tolist() == [2.5, 4.5]

    @pytest.mark.unit
    def test_the_exponent_spellings_of_the_pcraster_missing_value(self, tmp_path):
        path = tmp_path / "observed.csv"
        path.write_text("0;A\n1;1e+31\n2;1E31\n3;2.0\n", encoding="utf8")

        table = read_series(path)

        assert valid_mask(table.stations["A"]).tolist() == [False, False, True]

    @pytest.mark.unit
    def test_a_handwritten_pcraster_time_series(self, tmp_path):
        path = tmp_path / "observed.tss"
        path.write_text(
            "Observed streamflow\n3\ntimestep\n11\n22\n1 1.5 2.5\n2 3.5 4.5\n",
            encoding="utf8",
        )

        table = read_series(path)

        assert table.steps.tolist() == [1, 2]
        assert sorted(table.stations) == ["11", "22"]
        assert table.stations["11"].tolist() == [1.5, 3.5]
        assert table.stations["22"].tolist() == [2.5, 4.5]

    @pytest.mark.unit
    def test_a_pcraster_header_whose_count_carries_trailing_spaces(self, tmp_path):
        # The number of columns is read from a line of its own, which a writer
        # may pad; the title above it carries spaces of its own and is not read.
        path = tmp_path / "observed.tss"
        path.write_text(
            "timeseries scalar\n3   \ntimestep\n11\n22\n1 1.5 2.5\n2 3.5 4.5\n",
            encoding="utf8",
        )

        table = read_series(path)

        assert sorted(table.stations) == ["11", "22"]
        assert table.stations["22"].tolist() == [2.5, 4.5]

    @pytest.mark.unit
    def test_the_windows_line_endings_of_a_pcraster_time_series(self, tmp_path):
        # The carriage return must not be taken for part of the number of
        # columns, of a station id or of the last value of a row.
        path = tmp_path / "observed.tss"
        path.write_bytes(
            b"timeseries scalar\r\n3\r\ntimestep\r\n11\r\n22\r\n1 1.5 2.5\r\n2 3.5 4.5\r\n"
        )

        table = read_series(path)

        assert sorted(table.stations) == ["11", "22"]
        assert table.steps.tolist() == [1, 2]
        assert table.stations["22"].tolist() == [2.5, 4.5]

    @pytest.mark.unit
    def test_a_pcraster_time_series_without_the_header_is_refused(self, tmp_path):
        # Numbering the columns 1..N would label them with a guess: the columns
        # of a time series are stations, and nothing here says which.
        path = tmp_path / "observed.tss"
        path.write_text("1 1.5 2.5\n2 3.5 4.5\n", encoding="utf8")

        with pytest.raises(ValueError, match="PCRaster time series files carry") as failure:
            read_series(path)

        message = str(failure.value)
        assert "has no header" in message
        assert "0;<id>;<id>..." in message, "the message names both accepted layouts"
        assert "title line" in message

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "content",
        [
            "Observed streamflow\n1\ntimestep\n1 1.5\n",
            "Observed streamflow\n3\ntimestep\n11\n",
            "1 1.5 2.5\n",
        ],
        ids=["one column", "fewer names than the count", "a single row"],
    )
    def test_a_truncated_pcraster_header_is_refused(self, tmp_path, content):
        path = tmp_path / "observed.tss"
        path.write_text(content, encoding="utf8")

        with pytest.raises(ValueError, match="PCRaster time series files carry"):
            read_series(path)

    @pytest.mark.unit
    def test_a_csv_table_without_the_header_is_refused(self, tmp_path):
        # The first record is already a time step, so the ids would be read
        # from it and the first step would be lost from the series.
        path = tmp_path / "observed.csv"
        path.write_text("1;16.33;22.94\n2;14.86;19.95\n", encoding="utf8")

        with pytest.raises(ValueError, match="has no header") as failure:
            read_series(path)

        message = str(failure.value)
        assert "'1'" in message, "the message quotes the line it refused"
        assert "0;<id>;<id>..." in message, "the message names both accepted layouts"
        assert "PCRaster time series" in message

    @pytest.mark.unit
    def test_a_byte_order_mark_is_not_part_of_the_step_column_label(self, tmp_path):
        # An editor that writes UTF-8 with a byte order mark puts it at the
        # start of the first line, where it would otherwise become part of the
        # first header cell.
        path = tmp_path / "observed.csv"
        path.write_bytes("﻿0;A;B\n1;1.5;2.5\n2;3.5;4.5\n".encode("utf8"))

        table = read_series(path)

        assert sorted(table.stations) == ["A", "B"]
        assert table.steps.tolist() == [1, 2]
        assert table.stations["A"].tolist() == [1.5, 3.5]

    @pytest.mark.unit
    def test_a_byte_order_mark_does_not_hide_a_missing_csv_header(self, tmp_path):
        # The mark would turn the first time step into a word, and a word is
        # the label of a step column: the refusal must not depend on it.
        path = tmp_path / "observed.csv"
        path.write_bytes("﻿1;16.33;22.94\n2;14.86;19.95\n".encode("utf8"))

        with pytest.raises(ValueError, match="has no header") as failure:
            read_series(path)

        assert "'1'" in str(failure.value), "the mark is not part of the line it quotes"

    @pytest.mark.unit
    def test_a_byte_order_mark_before_the_title_of_a_time_series(self, tmp_path):
        path = tmp_path / "observed.tss"
        path.write_bytes(
            "﻿timeseries scalar\n3\ntimestep\n11\n22\n1 1.5 2.5\n2 3.5 4.5\n".encode("utf8")
        )

        table = read_series(path)

        assert sorted(table.stations) == ["11", "22"]
        assert table.steps.tolist() == [1, 2]

    @pytest.mark.unit
    @pytest.mark.parametrize("label", ["0", "timestep", "step", ""])
    def test_the_accepted_spellings_of_the_step_column_label(self, tmp_path, label):
        path = tmp_path / "observed.csv"
        path.write_text(f"{label};A\n1;1.0\n2;2.0\n", encoding="utf8")

        table = read_series(path)

        assert table.steps.tolist() == [1, 2]
        assert table.stations["A"].tolist() == [1.0, 2.0]

    @pytest.mark.unit
    def test_a_row_that_does_not_start_with_a_time_step_names_the_file(self, tmp_path):
        path = tmp_path / "observed.csv"
        path.write_text("0;A\n2000-01-01;1.0\n2000-01-02;2.0\n", encoding="utf8")

        with pytest.raises(ValueError, match="Row 2 .* does not start with a time step"):
            read_series(path)

    @pytest.mark.unit
    def test_a_repeated_station_id_is_refused(self, tmp_path):
        path = tmp_path / "observed.csv"
        path.write_text("0;1;1\n1;1.0;2.0\n", encoding="utf8")

        with pytest.raises(ValueError, match="repeated station ids: 1"):
            read_series(path)

    @pytest.mark.unit
    def test_a_row_that_does_not_match_the_header_is_refused(self, tmp_path):
        path = tmp_path / "observed.csv"
        path.write_text("0;1;2\n1;1.0;2.0\n2;3.0\n", encoding="utf8")

        with pytest.raises(ValueError, match="Row 3"):
            read_series(path)

    @pytest.mark.unit
    def test_an_empty_table_is_refused(self, tmp_path):
        path = tmp_path / "observed.csv"
        path.write_text("", encoding="utf8")

        with pytest.raises(ValueError, match="empty"):
            read_series(path)


class TestEvaluateSeries:
    @pytest.mark.unit
    def test_the_mean_over_the_stations(self):
        # Station A: exact -> 1.0. Station B: observed [1, 2, 3] with the
        # simulation reversed -> -3.0. Mean = (1.0 - 3.0) / 2 = -1.0
        simulated = series([1, 2, 3], A=[4.0, 5.0, 6.0], B=[3.0, 2.0, 1.0])
        observed = series([1, 2, 3], A=[4.0, 5.0, 6.0], B=[1.0, 2.0, 3.0])

        mean, per_station = evaluate_series(simulated, observed)

        assert nse_of(per_station) == {"A": 1.0, "B": -3.0}
        assert mean == -1.0

    @pytest.mark.unit
    def test_only_the_shared_steps_are_compared(self):
        # The shared steps are 3 and 4: observed [1, 3] with mean 2 and
        # variability 2, simulated [1, 3] -> NSE = 1.0
        simulated = series([1, 2, 3, 4], A=[99.0, 99.0, 1.0, 3.0])
        observed = series([3, 4, 5], A=[1.0, 3.0, 99.0])

        mean, per_station = evaluate_series(simulated, observed)

        assert nse_of(per_station) == {"A": 1.0}
        assert per_station["A"].pairs == 2, "only the shared steps are a pair"
        assert mean == 1.0

    @pytest.mark.unit
    def test_the_spin_up_steps_are_excluded(self):
        # Without the spin-up the first step would make the simulation exact;
        # with two spin-up steps only the steps 3 and 4 are compared:
        # observed [1, 3], mean 2, variability 2; simulated [3, 1]
        # -> residuals (4 + 4) = 8 -> NSE = 1 - 8/2 = -3.0
        simulated = series([1, 2, 3, 4], A=[0.0, 0.0, 3.0, 1.0])
        observed = series([1, 2, 3, 4], A=[0.0, 0.0, 1.0, 3.0])

        mean, per_station = evaluate_series(simulated, observed, spinup_steps=2)

        assert nse_of(per_station) == {"A": -3.0}
        assert mean == -3.0

    @pytest.mark.unit
    def test_a_station_present_on_one_side_only_is_ignored(self):
        simulated = series([1, 2, 3], A=[1.0, 2.0, 3.0], B=[1.0, 2.0, 3.0])
        observed = series([1, 2, 3], A=[1.0, 2.0, 3.0], C=[1.0, 2.0, 3.0])

        mean, per_station = evaluate_series(simulated, observed)

        assert nse_of(per_station) == {"A": 1.0}
        assert mean == 1.0

    @pytest.mark.unit
    def test_a_station_without_variance_is_reported_and_left_out_of_the_mean(self):
        # Station A is exact -> 1.0; station B has constant observations -> None.
        # The mean is that of the stations with a value: 1.0
        simulated = series([1, 2, 3], A=[1.0, 2.0, 3.0], B=[0.1, 0.2, 0.3])
        observed = series([1, 2, 3], A=[1.0, 2.0, 3.0], B=[0.1, 0.1, 0.1])

        mean, per_station = evaluate_series(simulated, observed)

        assert nse_of(per_station) == {"A": 1.0, "B": None}
        assert per_station["B"].pairs == 3, "the station is measured even without an efficiency"
        assert mean == 1.0

    @pytest.mark.unit
    def test_no_shared_station_names_both_sides(self):
        simulated = series([1, 2], A=[1.0, 2.0])
        observed = series([1, 2], B=[1.0, 2.0])

        with pytest.raises(ValueError, match="no station in common") as error:
            evaluate_series(simulated, observed)

        assert "A" in str(error.value) and "B" in str(error.value)

    @pytest.mark.unit
    def test_no_shared_step_names_the_steps(self):
        simulated = series([1, 2], A=[1.0, 2.0])
        observed = series([7, 8], A=[1.0, 2.0])

        with pytest.raises(ValueError, match="no time step in common") as error:
            evaluate_series(simulated, observed)

        assert "[1, 2]" in str(error.value) and "[7, 8]" in str(error.value)

    @pytest.mark.unit
    def test_a_spin_up_that_eats_every_step_is_an_error(self):
        simulated = series([1, 2], A=[1.0, 2.0])
        observed = series([1, 2], A=[1.0, 2.0])

        with pytest.raises(ValueError, match="no time step in common"):
            evaluate_series(simulated, observed, spinup_steps=2)

    @pytest.mark.unit
    def test_no_station_with_an_efficiency_is_an_error(self):
        simulated = series([1, 2, 3], A=[1.0, 2.0, 3.0], B=[1.0, 2.0, 3.0])
        observed = series([1, 2, 3], A=[5.0, 5.0, 5.0], B=[1.0, -9999.0, np.nan])

        with pytest.raises(ValueError, match="No station has a Nash-Sutcliffe") as error:
            evaluate_series(simulated, observed)

        assert "A, B" in str(error.value)


class TestStationMetrics:
    @pytest.mark.unit
    def test_every_statistic_of_a_hand_computed_pair_of_series(self):
        # observed [1, 2, 6], simulated [2, 2, 5].
        # mean_observed = (1 + 2 + 6) / 3 = 3
        # mean_simulated = (2 + 2 + 5) / 3 = 3
        # deviations: observed [-2, -1, 3], simulated [-1, -1, 2]
        # std_observed = sqrt((4 + 1 + 9) / 2) = sqrt(7)
        # std_simulated = sqrt((1 + 1 + 4) / 2) = sqrt(3)
        # r = (2 + 1 + 6) / sqrt(14 * 6) = 9 / sqrt(84)
        # rmse = sqrt(((2-1)^2 + 0 + (5-6)^2) / 3) = sqrt(2/3)
        # nse = 1 - (1 + 0 + 1) / 14 = 1 - 2/14 = 6/7
        measured = station_metrics(np.array([2.0, 2.0, 5.0]), np.array([1.0, 2.0, 6.0]))

        assert measured.pairs == 3
        assert measured.mean_observed == pytest.approx(3.0)
        assert measured.mean_simulated == pytest.approx(3.0)
        assert measured.std_observed == pytest.approx(np.sqrt(7.0))
        assert measured.std_simulated == pytest.approx(np.sqrt(3.0))
        assert measured.r == pytest.approx(9.0 / np.sqrt(84.0))
        assert measured.rmse == pytest.approx(np.sqrt(2.0 / 3.0))
        assert measured.nse == pytest.approx(6.0 / 7.0)

    @pytest.mark.unit
    def test_it_is_a_frozen_record_of_eight_fields(self):
        measured = station_metrics(np.array([1.0, 2.0]), np.array([1.0, 2.0]))

        assert isinstance(measured, StationMetrics)
        assert list(dataclasses.asdict(measured)) == [
            "pairs",
            "mean_observed",
            "std_observed",
            "mean_simulated",
            "std_simulated",
            "r",
            "rmse",
            "nse",
        ]
        with pytest.raises(dataclasses.FrozenInstanceError):
            measured.nse = 0.0

    @pytest.mark.unit
    def test_only_the_pairs_valid_in_both_series_are_measured(self):
        # The third step is a gap in the simulation and the fourth a negative
        # observation: the sample is observed [1, 3] and simulated [1, 3].
        # mean 2 on both sides, std sqrt(((1)^2 + (1)^2) / 1) = sqrt(2)
        measured = station_metrics(
            np.array([1.0, 3.0, np.nan, 9.0]), np.array([1.0, 3.0, 8.0, -1.0])
        )

        assert measured.pairs == 2
        assert measured.mean_observed == pytest.approx(2.0)
        assert measured.std_observed == pytest.approx(np.sqrt(2.0))
        assert measured.rmse == 0.0
        assert measured.nse == 1.0

    @pytest.mark.unit
    def test_a_single_pair_has_a_mean_and_an_error_but_no_spread(self):
        # One pair: the mean and the root mean squared error are defined, a
        # standard deviation with one degree of freedom and an efficiency are not.
        measured = station_metrics(np.array([3.0, np.nan]), np.array([1.0, 2.0]))

        assert measured.pairs == 1
        assert measured.mean_observed == 1.0
        assert measured.mean_simulated == 3.0
        assert measured.rmse == 2.0
        assert measured.std_observed is None
        assert measured.std_simulated is None
        assert measured.r is None
        assert measured.nse is None

    @pytest.mark.unit
    def test_a_station_without_one_valid_pair_has_nothing(self):
        measured = station_metrics(np.array([1.0, -9999.0]), np.array([np.nan, 2.0]))

        assert measured.pairs == 0
        assert dataclasses.astuple(measured) == (0, None, None, None, None, None, None, None)

    @pytest.mark.unit
    def test_a_constant_series_has_no_correlation(self):
        # The simulation never moves, so its own spread is zero and the
        # correlation has no denominator; the efficiency is still defined,
        # since the observations vary.
        measured = station_metrics(np.array([2.0, 2.0, 2.0]), np.array([1.0, 2.0, 3.0]))

        assert measured.std_simulated == 0.0
        assert measured.r is None
        assert measured.nse == 0.0

    @pytest.mark.unit
    def test_constant_observations_leave_neither_a_correlation_nor_an_efficiency(self):
        measured = station_metrics(np.array([0.1, 0.2, 0.3]), np.array([0.1, 0.1, 0.1]))

        # The spread of a constant series is only approximately zero in
        # floating point, which is why the guards test the values themselves.
        assert measured.std_observed == pytest.approx(0.0, abs=1e-15)
        assert measured.r is None
        assert measured.nse is None

    @pytest.mark.unit
    def test_series_of_different_lengths_are_refused(self):
        with pytest.raises(ValueError, match="same shape"):
            station_metrics(np.array([1.0, 2.0]), np.array([1.0, 2.0, 3.0]))


class TestStationSelection:
    @pytest.mark.unit
    def test_the_mean_is_taken_over_the_selection_and_every_station_is_measured(self):
        # Station A is exact -> 1.0, station B reversed -> -3.0, station C
        # exact -> 1.0. The objective averages A and C: (1.0 + 1.0) / 2 = 1.0,
        # and B is measured all the same.
        simulated = series([1, 2, 3], A=[1.0, 2.0, 3.0], B=[3.0, 2.0, 1.0], C=[4.0, 5.0, 6.0])
        observed = series([1, 2, 3], A=[1.0, 2.0, 3.0], B=[1.0, 2.0, 3.0], C=[4.0, 5.0, 6.0])

        mean, per_station = evaluate_series(simulated, observed, stations=("A", "C"))

        assert mean == 1.0
        assert nse_of(per_station) == {"A": 1.0, "B": -3.0, "C": 1.0}

    @pytest.mark.unit
    def test_a_selected_station_without_an_efficiency_is_left_out_of_the_mean(self):
        # B has constant observations and no efficiency, so the mean of the
        # selection is that of A alone.
        simulated = series([1, 2, 3], A=[1.0, 2.0, 3.0], B=[0.1, 0.2, 0.3])
        observed = series([1, 2, 3], A=[1.0, 2.0, 3.0], B=[0.1, 0.1, 0.1])

        mean, _ = evaluate_series(simulated, observed, stations=("A", "B"))

        assert mean == 1.0

    @pytest.mark.unit
    def test_a_station_of_the_selection_the_series_do_not_share_is_ignored(self):
        simulated = series([1, 2, 3], A=[1.0, 2.0, 3.0], B=[3.0, 2.0, 1.0])
        observed = series([1, 2, 3], A=[1.0, 2.0, 3.0], B=[1.0, 2.0, 3.0])

        mean, per_station = evaluate_series(simulated, observed, stations=("A", "Z"))

        assert mean == 1.0
        assert sorted(per_station) == ["A", "B"]

    @pytest.mark.unit
    def test_a_selection_that_names_no_shared_station_names_the_ids(self):
        simulated = series([1, 2, 3], A=[1.0, 2.0, 3.0])
        observed = series([1, 2, 3], A=[1.0, 2.0, 3.0])

        with pytest.raises(ValueError, match="none of the stations") as failure:
            evaluate_series(simulated, observed, stations=("Y", "Z"))

        message = str(failure.value)
        assert "Y, Z" in message
        assert "A" in message

    @pytest.mark.unit
    def test_no_selected_station_with_an_efficiency_names_the_selection(self):
        simulated = series([1, 2, 3], A=[1.0, 2.0, 3.0], B=[1.0, 2.0, 3.0])
        observed = series([1, 2, 3], A=[5.0, 5.0, 5.0], B=[1.0, 2.0, 3.0])

        with pytest.raises(ValueError, match="No station has a Nash-Sutcliffe") as failure:
            evaluate_series(simulated, observed, stations=("A",))

        assert "(A)" in str(failure.value), "only the selection is named"
