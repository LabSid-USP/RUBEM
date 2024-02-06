import pytest
from datetime import date

from rubem.date._date_calc import totalSteps, daysOfMonth


class TestDateUtilities:

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "start_date, end_date, expected_first_step, expected_last_step, expected_num_months",
        [
            (date(2020, 1, 1), date(2022, 12, 31), 1, 36, 36),
            (date(2022, 1, 1), date(2022, 12, 31), 1, 12, 12),
            (date(2022, 1, 1), date(2022, 1, 2), 1, 1, 1),
            (date(2022, 1, 1), date(2022, 2, 1), 1, 2, 2),
        ],
    )
    def test_total_steps(
        self, start_date, end_date, expected_first_step, expected_last_step, expected_num_months
    ):
        first_step, last_step, num_months = totalSteps(start_date, end_date)
        assert first_step == expected_first_step
        assert last_step == expected_last_step
        assert num_months == expected_num_months

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "source_date, timestep, expected_days",
        [
            (date(2022, 1, 1), 1, 31),
            (date(2022, 2, 1), 1, 28),
            (date(2022, 2, 1), 2, 31),
            (date(2022, 12, 1), 1, 31),
        ],
    )
    def test_days_of_month(self, source_date, timestep, expected_days):
        days = daysOfMonth(source_date, timestep)
        assert days == expected_days
