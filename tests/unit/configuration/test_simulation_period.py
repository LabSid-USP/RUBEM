from datetime import date
import pytest

from rubem.configuration.simulation_period import SimulationPeriod


class TestSimulationPeriod:

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "start, end",
        [
            (date(2024, 1, 1), date(2024, 1, 1)),
            (date(2024, 1, 1), date(2023, 12, 31)),
        ],
    )
    def test_simulation_period_constructor_bad_args(self, start, end):
        with pytest.raises(Exception):
            SimulationPeriod(start=start, end=end)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "start, end",
        [
            (date(2024, 1, 1), date(2024, 12, 31)),
            (date(2024, 1, 1), date(2024, 1, 2)),
        ],
    )
    def test_simulation_period_constructor_good_args(self, start, end):
        SimulationPeriod(start=start, end=end)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "start, end, first_step, last_step, total_steps",
        [
            (date(2024, 1, 1), date(2024, 3, 31), 1, 3, 3),
            (date(2024, 1, 1), date(2024, 12, 31), 1, 12, 12),
            (date(2020, 1, 1), date(2024, 12, 31), 1, 60, 60),
        ],
    )
    def test_simulation_period_step_calculation(
        self, start, end, first_step, last_step, total_steps
    ):
        sp = SimulationPeriod(start=start, end=end)
        assert sp.first_step == first_step
        assert sp.last_step == last_step
        assert sp.total_steps == total_steps

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "start, end, alignment, expected_first_step, expected_last_step, expected_total_steps",
        [
            (date(2024, 1, 1), date(2024, 3, 31), date(2024, 1, 1), 1, 3, 3),
            (date(2024, 1, 1), date(2024, 12, 31), date(2019, 1, 1), 61, 72, 12),
            (date(2020, 1, 1), date(2024, 12, 31), date(2020, 1, 1), 1, 60, 60),
            (date(2021, 1, 1), date(2024, 3, 31), date(2019, 1, 1), 25, 63, 39),
            (date(2022, 1, 1), date(2024, 12, 31), date(2019, 1, 1), 37, 72, 36),
            (date(2020, 1, 1), date(2024, 12, 31), date(2019, 1, 1), 13, 72, 60),
        ],
    )
    def test_simulation_period_alignment(
        self, start, end, alignment, expected_first_step, expected_last_step, expected_total_steps
    ):
        sp = SimulationPeriod(start=start, end=end, alignment=alignment)
        assert sp.first_step == expected_first_step
        assert sp.last_step == expected_last_step
        assert sp.total_steps == expected_total_steps

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "start, end, alignment",
        [
            (date(2024, 1, 1), date(2024, 3, 31), date(2024, 1, 2)),
            (date(2024, 1, 1), date(2024, 12, 31), date(2024, 12, 31)),
            (date(2020, 1, 1), date(2024, 12, 31), date(2025, 1, 1)),
        ],
    )
    def test_simulation_period_alignment_bad_args(self, start, end, alignment):
        with pytest.raises(Exception):
            SimulationPeriod(start=start, end=end, alignment=alignment)
