import argparse
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def file_path_cli_arg_validator(path: str):
    resolved_path = Path(path)

    if not resolved_path.exists():
        logger.error("Specified file path %s does not exist", path)
        raise argparse.ArgumentTypeError(f'Specified file path "{path}" does not exist.')

    if not resolved_path.is_file():
        logger.error("Specified file path %s is not a file", path)
        raise argparse.ArgumentTypeError(f'Specified file path "{path}" is not a valid file.')

    if not os.access(path, os.R_OK):
        logger.error("Specified file path %s is not readable", path)
        raise argparse.ArgumentTypeError(f'Specified file path "{path}" is not readable.')

    if not resolved_path.stat().st_size > 0:
        logger.error("Specified file path %s is empty", path)
        raise argparse.ArgumentTypeError(f'Specified file path "{path}" is empty.')

    if resolved_path.suffix not in [".json"]:
        logger.error("Specified file path %s is not a valid file format", path)
        raise argparse.ArgumentTypeError(
            f'Specified file path "{path}" is not a valid file format. '
            f"Only JSON file format is supported."
        )

    return path
