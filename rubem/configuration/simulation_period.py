from datetime import date
import logging
from typing import Optional


class SimulationPeriod:
    """
    Represents a period of time for simulation.

    :param start: The start date of the simulation period.
    :type start: date

    :param end: The end date of the simulation period.
    :type end: date

    :param alignment: The date to align the simulation period to. If not provided, the start date is used.
    :type alignment: Optional[date]

    :raises ValueError: If the start date is not before the end date.
    """

    def __init__(self, start: date, end: date, alignment: Optional[date] = None):
        self.logger = logging.getLogger(__name__)

        if start >= end:
            self.logger.error("Start date (%s) must be before end date (%s).", start, end)
            raise ValueError(f"Start date ({start}) must be before end date ({end}).")

        self.start_date = start
        self.end_date = end

        if not alignment:
            self.logger.info("No alignment date provided. Using start date as alignment.")
            alignment = self.start_date

        if alignment < self.start_date or alignment > self.end_date:
            self.logger.error(
                "Date alignment must be between start (%s) and end (%s) dates.",
                self.start_date,
                self.end_date,
            )
            raise ValueError(
                f"Date alignment must be between start ({self.start_date}) and end ({self.end_date}) dates."
            )

        self.first_step = (start.year - alignment.year) * 12 + (start.month - alignment.month) + 1
        self.last_step = (end.year - alignment.year) * 12 + (end.month - alignment.month) + 1

        self.total_steps = self.last_step - self.first_step + 1

    def __str__(self) -> str:
        return f"{self.start_date} to {self.end_date}"
