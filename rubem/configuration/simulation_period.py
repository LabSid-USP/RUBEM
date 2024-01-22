from datetime import date
import logging

from rubem.date._date_calc import totalSteps


class SimulationPeriod:
    """
    Represents a period of time for simulation.

    :param start: The start date of the simulation period.
    :type start: date
    :param end: The end date of the simulation period.
    :type end: date

    :raises ValueError: If the start date is not before the end date.
    """

    def __init__(self, start: date, end: date):
        self.logger = logging.getLogger(__name__)
        if start >= end:
            self.logger.error("Start date must be before end date.")
            raise ValueError("Start date must be before end date.")
        self.start_date = start
        self.end_date = end
        self.first_step, self.last_step, self.total_steps = totalSteps(
            self.start_date, self.end_date
        )

    def __str__(self) -> str:
        return f"{self.start_date} to {self.end_date}"
