import os
import logging
import logging.handlers
import argparse
from datetime import datetime

from rubem import __release__
from rubem.core import Model
from rubem.validation._validators import filePathArgValidator
from rubem.configuration.model_configuration import ModelConfiguration

logger = logging.getLogger(__name__)
LOG_FILE_DIR = os.path.join(os.path.expanduser("~"), ".rubem")
os.path.exists(LOG_FILE_DIR) or os.makedirs(LOG_FILE_DIR)
LOG_FILENAME = f"rubem-{datetime.today().strftime('%d-%m-%Y')}.log"

LOG_FILE_PATH = os.path.join(LOG_FILE_DIR, LOG_FILENAME)
LOG_FILE_SIZE_LIM = 5 * 1024 * 1024
LOG_FILE_BACKUP_COUNT = 1
LOG_MSG_FMT = "%(asctime)s %(name)s %(levelname)s:%(message)s"
LOG_MSG_DTFMT = "%m/%d/%Y %H:%M:%S"
LOG_LEVEL_DEFAULT_FILE = logging.INFO
LOG_LEVEL_DEFAULT_TERM = logging.ERROR


def main():
    """[summary]

    :raises SystemExit: [description]
    """
    # Configure CLI
    parser = argparse.ArgumentParser(
        prog="rubem",
        description="Rainfall rUnoff Balance Enhanced Model (RUBEM)",
        epilog=(
            f"RUBEM {__release__} Copyright (C) 2020-2024 - LabSid/PHA/EPUSP -"
            "This program comes with ABSOLUTELY NO WARRANTY."
            "This is free software, and you are welcome to redistribute it "
            "under certain conditions."
        ),
    )
    parser.add_argument(
        "-c",
        "--configfile",
        type=filePathArgValidator,
        help="path to configuration file",
        required=True,
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"RUBEM v{__release__}",
        help="show version and exit",
    )

    args = parser.parse_args()

    rotating_file_handler = logging.handlers.RotatingFileHandler(
        filename=LOG_FILE_PATH,
        encoding="utf-8",
        maxBytes=LOG_FILE_SIZE_LIM,
        backupCount=LOG_FILE_BACKUP_COUNT,
        delay=20.0,
    )

    stream_handler = logging.StreamHandler()
    rotating_file_handler.setLevel(LOG_LEVEL_DEFAULT_FILE)
    stream_handler.setLevel(LOG_LEVEL_DEFAULT_TERM)

    logging.basicConfig(
        format=LOG_MSG_FMT,
        datefmt=LOG_MSG_DTFMT,
        level=logging.DEBUG,
        handlers=[rotating_file_handler, stream_handler],
    )

    try:
        model_config = ModelConfiguration(args.configfile)
        print(model_config)
        model = Model.load(model_config)
        model.run()

    except Exception as e:
        logger.critical("RUBEM unexpectedly quit (-_-;)")
        logger.exception(e)
        raise SystemExit(1)
    except KeyboardInterrupt:
        logger.critical("RUBEM was interrupted by the user ¯\_(ツ)_/¯")
        raise SystemExit(2)
    else:
        logger.info("RUBEM successfully finished! ヽ(•‿•)ノ")
        raise SystemExit(0)
