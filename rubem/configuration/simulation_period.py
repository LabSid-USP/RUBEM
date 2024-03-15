from datetime import date, datetime
import logging
from typing import Optional, Union


class SimulationPeriod:
    """
    Represents a period of time for simulation.

    :param start: The start date of the simulation period.
    :type start: Union[date, datetime]

    :param end: The end date of the simulation period.
    :type end: Union[date, datetime]

    :param alignment: The date to align the simulation period to. If not provided, the start date is used.
    :type alignment: Optional[Union[date, datetime]]

    :raises ValueError: If the start date is not before the end date.
    """

    def __init__(
        self,
        start: Union[date, datetime],
        end: Union[date, datetime],
        alignment: Optional[Union[date, datetime]] = None,
    ):
        self.logger = logging.getLogger(__name__)

        if start >= end:
            self.logger.error("Start date (%s) must be before end date (%s).", start, end)
            raise ValueError(f"Start date ({start}) must be before end date ({end}).")

        self.start_date = start
        self.end_date = end

        if not alignment:
            self.logger.info("No alignment date provided. Using start date as alignment.")
            alignment = self.start_date

        if alignment > self.start_date:
            self.logger.error(
                "Alignment date (%s) is after start date (%s).", alignment, self.start_date
            )
            raise ValueError(
                f"Alignment date ({alignment}) must be before start date ({self.start_date})."
            )

        self.first_step = (start.year - alignment.year) * 12 + (start.month - alignment.month) + 1
        self.last_step = (end.year - alignment.year) * 12 + (end.month - alignment.month) + 1

        self.total_steps = self.last_step - self.first_step + 1

    def __str__(self) -> str:
        return f"{self.start_date} to {self.end_date}"
