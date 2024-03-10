import os
import logging
import argparse

logger = logging.getLogger(__name__)


def file_path_cli_arg_validator(path: str):
    if not os.path.exists(path):
        logger.error("Specified file path %s does not exist", path)
        raise argparse.ArgumentTypeError(f'Specified file path "{path}" does not exist.')

    if not os.path.isfile(path):
        logger.error("Specified file path %s is not a file", path)
        raise argparse.ArgumentTypeError(f'Specified file path "{path}" is not a valid file.')

    if not os.access(path, os.R_OK):
        logger.error("Specified file path %s is not readable", path)
        raise argparse.ArgumentTypeError(f'Specified file path "{path}" is not readable.')

    if not os.path.getsize(path) > 0:
        logger.error("Specified file path %s is empty", path)
        raise argparse.ArgumentTypeError(f'Specified file path "{path}" is empty.')

    if not os.path.splitext(path)[1] in [".json", ".ini"]:
        logger.error("Specified file path %s is not a valid file format", path)
        raise argparse.ArgumentTypeError(
            f'Specified file path "{path}" is not a valid file format. '
            f"Only JSON and INI file formats are supported."
        )

    return path
