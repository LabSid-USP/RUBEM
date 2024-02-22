import logging
import os
from typing import Union


class OutputDataDirectory:
    """
    Represents an output data directory.

    :param output_path: Path to the output directory.
    :type output_path: Union[str, bytes, os.PathLike]
    """

    def __init__(
        self,
        output_path: Union[str, bytes, os.PathLike],
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.path = str(output_path)

        self.__validate_directories()

        if not os.path.exists(self.path):
            self.logger.warning("Output directory does not exist: %s", self.path)
            try:
                self.logger.info("Creating output directory: %s", self.path)
                os.makedirs(self.path)
            except Exception as e:
                self.logger.error("Failed to create output directory: %s", e)
                raise

    def __validate_directories(self) -> None:
        if os.path.isfile(self.path):
            self.logger.error("Output path is not a directory: %s", self.path)
            raise NotADirectoryError(f"{self.path} is not a directory")

        if os.listdir(self.path):
            self.logger.warning("There is data in the output directory: %s", self.path)

    def __str__(self) -> str:
        return f"{self.path}"
