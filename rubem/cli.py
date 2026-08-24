import argparse
import logging
import logging.config
import logging.handlers
from typing import Optional, Sequence

from . import __release__
from ._deps import require_runtime_deps
from .configuration.app_settings import AppSettings
from .configuration.data_ranges_settings import DataRangesSettings
from .validation.cli_validators import file_path_cli_arg_validator

logger = logging.getLogger(__name__)

# Serilog Like {Level:u3}
logging.addLevelName(logging.DEBUG, "DBG")
logging.addLevelName(logging.INFO, "INF")
logging.addLevelName(logging.WARNING, "WRN")
logging.addLevelName(logging.ERROR, "ERR")
logging.addLevelName(logging.FATAL, "FTL")


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Run the RUBEM command line.

    This is the console script entry point; it returns normally when the
    simulation finishes successfully.

    :param argv: Command line arguments, without the program name. Defaults to
        ``None``, which reads ``sys.argv``.
    :type argv: Sequence[str], optional

    :raises SystemExit(1): If the simulation fails.
    :raises SystemExit(2): If the arguments are invalid or the program is
        interrupted by the user.
    """
    setup_logging()
    app_settings = AppSettings()
    custom_logging_config = app_settings.get_setting("logging")
    if custom_logging_config:
        setup_logging(custom_logging_config)

    try:
        i18n_settings = app_settings.get_setting("i18n")
        language = i18n_settings.get("language") if i18n_settings else None
        if language and language != "en_US":
            import humanize

            humanize.i18n.activate(language)
    except Exception as e:
        logger.error("Failed to set language: %s, using 'en_US' as default language", e)

    _ = DataRangesSettings(app_settings.get_setting("value_ranges"))

    # Configure CLI
    parser = argparse.ArgumentParser(
        prog="rubem",
        description="Rainfall rUnoff Balance Enhanced Model (RUBEM)",
        epilog=(
            f"RUBEM {__release__} Copyright (C) 2020-2024 - LabSid/PHA/EPUSP - "
            "This program comes with ABSOLUTELY NO WARRANTY. "
            "This is a free software, and you are welcome to redistribute it "
            "under certain conditions."
        ),
    )
    parser.add_argument(
        "-c",
        "--configfile",
        type=file_path_cli_arg_validator,
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

    args = parser.parse_args(argv)

    require_runtime_deps()

    try:
        import time

        import humanize

        from .configuration.model_configuration import ModelConfiguration
        from .core import DynamicFrameworkWrapper

        # The library only logs; the progress a command-line run is expected to
        # show (see doc/source/tutorials.rst) is written here, so that an
        # embedded run stays silent unless its host configures logging.
        validating = " and validating inputs" if args.skip_inputs_validation else ""
        print(f"Loading configuration{validating}...", flush=True)
        model_config = ModelConfiguration(args.configfile, args.skip_inputs_validation)
        model = DynamicFrameworkWrapper.load(model_config)

        print("Simulation started...", flush=True)
        started = time.time()
        try:
            model.run()
            print("Simulation finished successfully!", flush=True)
        finally:
            elapsed = humanize.precisedelta(time.time() - started, minimum_unit="seconds")
            print(f"Elapsed time: {elapsed}", flush=True)
    except Exception as e:
        logger.critical("RUBEM unexpectedly quit.")
        logger.exception(e)
        raise SystemExit(1) from e
    except KeyboardInterrupt as e:
        logger.critical("RUBEM was interrupted by the user.")
        raise SystemExit(2) from e

    logger.info("RUBEM successfully finished!")


def setup_logging(custom_logging_config: Optional[dict] = None):
    log_format = "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s"
    console_handler_config = {
        "class": "logging.StreamHandler",
        "formatter": "basic_formatter",
        "level": logging.WARNING,
    }
    basic_formatter_config = {"format": log_format, "datefmt": "%Y-%m-%dT%H:%M:%S%z"}
    # Progress records carry a message meant for a person, so they are printed
    # verbatim on stdout. The library only emits them; without this handler an
    # embedded run says nothing.
    progress_handler_config = {
        "class": "logging.StreamHandler",
        "formatter": "progress_formatter",
        "level": logging.INFO,
        "stream": "ext://sys.stdout",
    }
    default_logging_config = {
        "version": 1,
        # Every module logger, this one included, is created at import time, before
        # this runs. ``dictConfig`` disables pre-existing loggers unless told not to,
        # which would silently discard everything they log afterwards.
        "disable_existing_loggers": False,
        "formatters": {
            "basic_formatter": basic_formatter_config,
            "progress_formatter": {"format": "%(message)s"},
        },
        "handlers": {"console": console_handler_config, "progress": progress_handler_config},
        "loggers": {
            "rubem.progress": {
                "handlers": ["progress"],
                "level": logging.INFO,
                "propagate": False,
            }
        },
        "root": {"handlers": ["console"], "level": logging.DEBUG},
    }

    if custom_logging_config:
        try:
            # A custom configuration that omits the flag gets the same treatment;
            # one that sets it explicitly keeps its own value.
            logging.config.dictConfig({"disable_existing_loggers": False, **custom_logging_config})
        except Exception:
            logging.config.dictConfig(default_logging_config)
    else:
        logging.config.dictConfig(default_logging_config)
