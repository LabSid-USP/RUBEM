import logging
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator

from .._paths import as_path

logger = logging.getLogger(__name__)


class OutputDataDirectory(BaseModel):
    """
    Represents an output data directory.

    Construction only checks that the path does not name a file; the directory
    is created, and its existing content reported, by :meth:`ensure_exists`.

    :param output_path: Path to the output directory.
    :type output_path: Union[str, bytes, os.PathLike]

    :raises NotADirectoryError: If the path names an existing file.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str

    def __init__(self, output_path=None, /, **data) -> None:
        if output_path is not None:
            data["path"] = output_path
        super().__init__(**data)

    @field_validator("path", mode="before")
    @classmethod
    def _normalise(cls, value):
        path = as_path(value)
        if path.is_file():
            logger.error("Output path is not a directory: %s", path)
            raise NotADirectoryError(f"{path} is not a directory")
        return str(path)

    def ensure_exists(self) -> Self:
        """Create the directory when it is missing and report existing content.

        :raises OSError: If the directory cannot be created.
        """
        path = Path(self.path)
        if not path.exists():
            logger.warning("Output directory does not exist: %s", self.path)
            try:
                logger.info("Creating output directory: %s", self.path)
                path.mkdir(parents=True)
            except Exception as e:
                logger.error("Failed to create output directory: %s", e)
                raise
        if any(path.iterdir()):
            logger.warning("There is data in the output directory: %s", self.path)
        return self

    def __str__(self) -> str:
        return f"{self.path}"
