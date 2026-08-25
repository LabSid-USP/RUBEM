import math
from typing import Self

from pydantic import BaseModel, ConfigDict, computed_field, model_validator


class RasterGrid(BaseModel):
    """Properties of the raster grid.

    :param size: Cell size, in metres. Must be a finite positive number whose square is finite.
    :type size: float
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    size: float

    def __init__(self, size: float | None = None, /, **data) -> None:
        if size is not None:
            data["size"] = size
        super().__init__(**data)

    @model_validator(mode="after")
    def _check_size(self) -> Self:
        # ``size ** 2`` raises OverflowError for huge values while ``size * size``
        # saturates to ``inf``, which ``isfinite`` catches.
        if (
            not math.isfinite(self.size)
            or self.size <= 0
            or not math.isfinite(self.size * self.size)
        ):
            raise ValueError(f"Invalid grid area: {self.size}")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def area(self) -> float:
        """Cell area, in square metres."""
        return self.size * self.size

    def __str__(self) -> str:
        return f"{self.area} [m²]"
