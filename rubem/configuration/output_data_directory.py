import logging
from pathlib import Path

from .._paths import PathInput, as_path


class OutputDataDirectory:
    """
    Represents an output data directory.

    :param output_path: Path to the output directory.
    :type output_path: Union[str, bytes, os.PathLike]
    """

    def __init__(
        self,
        output_path: PathInput,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        path = as_path(output_path)
        self.path = str(path)

        self.__validate_directories(path)

        if not path.exists():
            self.logger.warning("Output directory does not exist: %s", self.path)
            try:
                self.logger.info("Creating output directory: %s", self.path)
                path.mkdir(parents=True)
            except Exception as e:
                self.logger.error("Failed to create output directory: %s", e)
                raise

        if any(path.iterdir()):
            self.logger.warning("There is data in the output directory: %s", self.path)

    def __validate_directories(self, path: Path) -> None:
        if path.is_file():
            self.logger.error("Output path is not a directory: %s", self.path)
            raise NotADirectoryError(f"{self.path} is not a directory")

    def __str__(self) -> str:
        return f"{self.path}"
