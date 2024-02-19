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

    def __validate_directories(self) -> None:
        try:
            if not os.path.isdir(self.path):
                os.makedirs(self.path)
        except Exception as e:
            self.logger.error("Failed to create output directory: %s", e)
            raise

        if os.listdir(self.path):
            self.logger.warning("There is data in the output directory: %s", self.path)

    def __str__(self) -> str:
        return f"{self.path}"
