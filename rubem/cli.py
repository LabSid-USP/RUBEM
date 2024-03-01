import argparse
from datetime import datetime
import logging
import logging.config
import logging.handlers
import os
from typing import Optional

import humanize

from rubem import __release__
from rubem.configuration.app_settings import AppSettings
from rubem.configuration.data_ranges_settings import DataRangesSettings
from rubem.core import Model
from rubem.validation._validators import filePathArgValidator
from rubem.configuration.model_configuration import ModelConfiguration

logger = logging.getLogger(__name__)

# Serilog Like {Level:u3}
logging.addLevelName(logging.DEBUG, "DBG")
logging.addLevelName(logging.INFO, "INF")
logging.addLevelName(logging.WARNING, "WRN")
logging.addLevelName(logging.ERROR, "ERR")
logging.addLevelName(logging.FATAL, "FTL")


def main():
    """Main function of the RUBEM CLI.

    This function is called when the user runs the RUBEM command.

    :raises SystemExit(0): If the program finishes successfully.
    :raises SystemExit(1): If the program exits with an error.
    :raises SystemExit(2): If the program is interrupted by the user.
    """
    app_settings = AppSettings()
    setup_logging(app_settings.get_setting("logging"))

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

    try:
        model_config = ModelConfiguration(args.configfile, args.skip_inputs_validation)
        model = Model.load(model_config)
        model.run()
    except Exception as e:
        logger.critical("RUBEM unexpectedly quit.")
        logger.exception(e)
        raise SystemExit(1)
    except KeyboardInterrupt:
        logger.critical("RUBEM was interrupted by the user.")
        raise SystemExit(2)
    else:
        logger.info("RUBEM successfully finished!")
        raise SystemExit(0)


def setup_logging(custom_logging_config: Optional[dict] = None):
    log_format = "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s"
    console_handler_config = {
        "class": "logging.StreamHandler",
        "formatter": "basic_formatter",
        "level": logging.WARNING,
    }
    rotating_file_handler_config = {
        "class": "logging.handlers.RotatingFileHandler",
        "formatter": "basic_formatter",
        "filename": os.path.join(
            os.path.expanduser("~"), ".rubem", f"rubem-{datetime.today().strftime('%d%m%Y')}.log"
        ),
        "maxBytes": 5242880,
        "backupCount": 3,
        "level": logging.INFO,
    }
    basic_formatter_config = {"format": log_format, "datefmt": "%Y-%m-%dT%H:%M:%S%z"}
    default_logging_config = {
        "version": 1,
        "formatters": {"basic_formatter": basic_formatter_config},
        "handlers": {"console": console_handler_config, "file": rotating_file_handler_config},
        "root": {"handlers": ["console", "file"], "level": logging.DEBUG},
    }

    if custom_logging_config:
        try:
            logging.config.dictConfig(custom_logging_config)
        except Exception:
            logging.config.dictConfig(default_logging_config)
    else:
        logging.config.dictConfig(default_logging_config)
