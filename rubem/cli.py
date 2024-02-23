import os
import logging
import logging.handlers
import argparse
from datetime import datetime

import humanize

from rubem import __release__
from rubem.configuration.app_settings import AppSettings
from rubem.configuration.data_ranges_settings import DataRangesSettings
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
    """Main function of the RUBEM CLI.

    This function is called when the user runs the RUBEM command.

    :raises SystemExit(0): If the program finishes successfully.
    :raises SystemExit(1): If the program exits with an error.
    :raises SystemExit(2): If the program is interrupted by the user.
    """
    app_settings = AppSettings()

    try:
        i18n_settings = app_settings.get_setting("i18n")
        language = i18n_settings.get("language") if i18n_settings else None
        if language and language != "en_US":
            humanize.i18n.activate(language)
    except Exception as e:
        logger.error("Failed to set language: %s, using 'en_US' as default language", e)

    _ = DataRangesSettings(app_settings.get_setting("value_ranges"))

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
    parser.add_argument(
        "-s",
        "--skip-inputs-validation",
        action="store_false",
        help="disable input files validation before running the model",
        required=False,
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
        model_config = ModelConfiguration(args.configfile, args.skip_inputs_validation)
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
