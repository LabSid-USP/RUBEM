import logging
from datetime import date, datetime
from typing import Self

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field, model_validator

DATE_FORMAT = "%d/%m/%Y"

logger = logging.getLogger(__name__)


class SimulationPeriod(BaseModel):
    """Period of time covered by a simulation, in monthly steps.

    :param start: The start date of the simulation period (also accepted as ``start_date``).
    :type start: Union[date, datetime]

    :param end: The end date of the simulation period (also accepted as ``end_date``).
    :type end: Union[date, datetime]

    :param alignment: The date the step numbering is aligned to. If not provided, the start date is used.
    :type alignment: Optional[Union[date, datetime]]

    :raises ValueError: If the start date is not before the end date, or the alignment date is after the start date.
    """

    model_config = ConfigDict(
        frozen=True, extra="forbid", validate_by_name=True, validate_by_alias=True
    )

    start_date: date | datetime = Field(validation_alias=AliasChoices("start", "start_date"))
    end_date: date | datetime = Field(validation_alias=AliasChoices("end", "end_date"))
    alignment: date | datetime | None = None

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.start_date >= self.end_date:
            logger.error(
                "Start date (%s) must be before end date (%s).",
                self.start_date.strftime(DATE_FORMAT),
                self.end_date.strftime(DATE_FORMAT),
            )
            raise ValueError(
                f"Start date ({self.start_date.strftime(DATE_FORMAT)}) must be before "
                f"end date ({self.end_date.strftime(DATE_FORMAT)})."
            )
        if self.alignment is None:
            logger.info("No alignment date provided. Using start date as alignment.")
        elif self.alignment > self.start_date:
            logger.error(
                "Alignment date (%s) is after start date (%s).",
                self.alignment.strftime(DATE_FORMAT),
                self.start_date.strftime(DATE_FORMAT),
            )
            raise ValueError(
                f"Alignment date ({self.alignment.strftime(DATE_FORMAT)}) must be before "
                f"start date ({self.start_date.strftime(DATE_FORMAT)})."
            )
        return self

    @property
    def _alignment_date(self) -> date | datetime:
        return self.alignment if self.alignment is not None else self.start_date

    @computed_field  # type: ignore[prop-decorator]
    @property
    def first_step(self) -> int:
        """Number of the first simulated step, counted from the alignment month."""
        alignment = self._alignment_date
        return (
            (self.start_date.year - alignment.year) * 12
            + (self.start_date.month - alignment.month)
            + 1
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def last_step(self) -> int:
        """Number of the last simulated step, counted from the alignment month."""
        alignment = self._alignment_date
        return (
            (self.end_date.year - alignment.year) * 12 + (self.end_date.month - alignment.month) + 1
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_steps(self) -> int:
        """Number of simulated steps."""
        return self.last_step - self.first_step + 1

    def __str__(self) -> str:
        return f"{self.start_date} to {self.end_date}"
