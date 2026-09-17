"""The ``rubem`` command line.

``rubem run -c <config.json> [-s]`` runs a simulation; ``rubem calibrate``
fits the calibration parameters to an observed series; ``rubem config schema``
prints the JSON Schema of the configuration file. The former ``rubem -c
<config.json>`` spelling still works for one minor release and emits a
``DeprecationWarning``.
"""

import json
import logging
import logging.config
import logging.handlers
import math
import sys
import warnings
from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from . import __release__
from ._deps import require_calibration_deps, require_runtime_deps
from .configuration._problems import ConfigurationError
from .configuration.app_settings import AppSettings
from .preprocessing.cli import app as preprocess_app
from .validation.cli_validators import file_path_cli_arg_validator

logger = logging.getLogger(__name__)

# Serilog Like {Level:u3}
logging.addLevelName(logging.DEBUG, "DBG")
logging.addLevelName(logging.INFO, "INF")
logging.addLevelName(logging.WARNING, "WRN")
logging.addLevelName(logging.ERROR, "ERR")
logging.addLevelName(logging.FATAL, "FTL")

EPILOG = (
    f"RUBEM {__release__} Copyright (C) 2020-2024 - LabSid/PHA/EPUSP - "
    "This program comes with ABSOLUTELY NO WARRANTY. "
    "This is a free software, and you are welcome to redistribute it "
    "under certain conditions."
)

_CONTEXT = {"help_option_names": ["-h", "--help"]}

app = typer.Typer(
    name="rubem",
    help="Rainfall rUnoff Balance Enhanced Model (RUBEM)",
    epilog=EPILOG,
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
    context_settings=_CONTEXT,
)
config_app = typer.Typer(
    help="Inspect the configuration file format.",
    no_args_is_help=True,
    context_settings=_CONTEXT,
)
app.add_typer(config_app, name="config")
app.add_typer(preprocess_app, name="preprocess")


class SchemaFormat(StrEnum):
    """Configuration file formats whose schema can be printed."""

    v1 = "v1"
    legacy = "legacy"


class InitMethod(StrEnum):
    """Initial populations the differential evolution can be started from."""

    sobol = "sobol"
    latinhypercube = "latinhypercube"
    halton = "halton"
    random = "random"


def _parse_bounds(values: list[str] | None) -> dict[str, tuple[float, float]]:
    """Return the ``--bound NAME=MIN:MAX`` options as a mapping of ranges.

    Only the shape of the text is checked here; whether the range narrows the
    range of the application settings is settled by the calibration itself,
    which knows the parameters.

    :param values: The options as they were written, or ``None``.
    :type values: list[str] | None

    :return: The ``(minimum, maximum)`` range of each named parameter.
    :rtype: dict[str, tuple[float, float]]

    :raises typer.BadParameter: If an option is not ``NAME=MIN:MAX``, or if a
        parameter is bounded twice.
    """
    parsed: dict[str, tuple[float, float]] = {}
    for entry in values or []:
        name, separator, rest = entry.partition("=")
        minimum, colon, maximum = rest.partition(":")
        if not separator or not colon or not name.strip():
            raise typer.BadParameter(
                f"'{entry}' is not a bound; write it as NAME=MIN:MAX, as in 'rcd=2:5'.",
                param_hint="'--bound'",
            )
        parsed[_unique(name.strip(), parsed, "--bound")] = (
            _as_number(minimum, entry, "--bound"),
            _as_number(maximum, entry, "--bound"),
        )
    return parsed


def _parse_fixed(values: list[str] | None) -> dict[str, float]:
    """Return the ``--fix NAME=VALUE`` options as a mapping of pinned values.

    :param values: The options as they were written, or ``None``.
    :type values: list[str] | None

    :return: The value each named parameter is pinned to.
    :rtype: dict[str, float]

    :raises typer.BadParameter: If an option is not ``NAME=VALUE``, or if a
        parameter is fixed twice.
    """
    parsed: dict[str, float] = {}
    for entry in values or []:
        name, separator, value = entry.partition("=")
        if not separator or not name.strip():
            raise typer.BadParameter(
                f"'{entry}' is not a fixed parameter; write it as NAME=VALUE, as in 'x=0'.",
                param_hint="'--fix'",
            )
        parsed[_unique(name.strip(), parsed, "--fix")] = _as_number(value, entry, "--fix")
    return parsed


def _parse_stations(value: str | None) -> tuple[str, ...]:
    """Return the ``--stations ID[,ID...]`` option as the ids it names.

    :param value: The option as it was written, or ``None``.
    :type value: str | None

    :return: The station ids, in the order they were given.
    :rtype: tuple[str, ...]

    :raises typer.BadParameter: If the option names no station, or leaves one of
        the comma-separated ids empty.
    """
    if value is None:
        return ()
    stations = tuple(station.strip() for station in value.split(","))
    if not all(stations):
        raise typer.BadParameter(
            f"'{value}' does not name the stations; write them as ID[,ID...], as in '1,2,3'.",
            param_hint="'--stations'",
        )
    return stations


def _as_number(text: str, entry: str, option: str) -> float:
    """Return a number written on the command line.

    :raises typer.BadParameter: If the text is not a finite number.
    """
    try:
        value = float(text)
    except ValueError as error:
        raise typer.BadParameter(
            f"'{text.strip()}' of '{entry}' is not a number.", param_hint=f"'{option}'"
        ) from error
    if not math.isfinite(value):
        raise typer.BadParameter(
            f"'{text.strip()}' of '{entry}' is not a finite number.", param_hint=f"'{option}'"
        )
    return value


def _unique(name: str, parsed: dict, option: str) -> str:
    """Return a parameter name that was not given twice on the command line.

    :raises typer.BadParameter: If the name is already in the mapping.
    """
    if name in parsed:
        raise typer.BadParameter(f"'{name}' is given more than once.", param_hint=f"'{option}'")
    return name


def _version_callback(value: bool) -> None:
    if value:
        print(f"RUBEM v{__release__}")
        raise typer.Exit()


def _configfile_callback(value: Path) -> Path:
    try:
        file_path_cli_arg_validator(str(value))
    except Exception as e:  # argparse.ArgumentTypeError carries the message
        raise typer.BadParameter(str(e)) from e
    return value


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Rainfall rUnoff Balance Enhanced Model (RUBEM)."""
    _configure_process()
    if _legacy_invocation:
        logger.warning("'rubem -c <config>' is deprecated; use 'rubem run -c <config>'.")


@app.command()
def run(
    configfile: Annotated[
        Path,
        typer.Option(
            "-c",
            "--configfile",
            callback=_configfile_callback,
            help="Path to the configuration file (JSON).",
        ),
    ],
    skip_inputs_validation: Annotated[
        bool,
        typer.Option(
            "-s",
            "--skip-inputs-validation",
            help="Disable input files validation before running the model.",
        ),
    ] = False,
) -> None:
    """Run a simulation from a configuration file."""
    require_runtime_deps()

    validate_input = not skip_inputs_validation
    try:
        import time

        import humanize

        from .configuration.model_configuration import ModelConfiguration
        from .core import DynamicFrameworkWrapper

        # The library only logs; the progress a command-line run is expected to
        # show (see doc/source/tutorials.rst) is written here, so that an
        # embedded run stays silent unless its host configures logging.
        validating = " and validating inputs" if validate_input else ""
        print(f"Loading configuration{validating}...", flush=True)
        model_config = ModelConfiguration(configfile, validate_input)
        model = DynamicFrameworkWrapper.load(model_config)
    except (ConfigurationError, ValidationError, ValueError) as e:
        # A configuration the user can fix: no traceback, the message says what.
        logger.critical("Invalid configuration: %s", e)
        raise typer.Exit(code=1) from e
    except KeyboardInterrupt as e:
        logger.critical("RUBEM was interrupted by the user.")
        raise typer.Exit(code=2) from e
    except Exception as e:
        logger.critical("RUBEM unexpectedly quit.")
        logger.exception(e)
        raise typer.Exit(code=1) from e

    # Once the configuration has loaded and the model is built, a failure is no
    # longer something the user can fix by editing the configuration file: even
    # a ``ValueError`` here (from the run itself or from exporting its tables)
    # is an unexpected crash and gets the traceback.
    try:
        print("Simulation started...", flush=True)
        started = time.time()
        try:
            model.run()
            print("Simulation finished successfully!", flush=True)
        finally:
            elapsed = humanize.precisedelta(time.time() - started, minimum_unit="seconds")
            print(f"Elapsed time: {elapsed}", flush=True)
    except KeyboardInterrupt as e:
        logger.critical("RUBEM was interrupted by the user.")
        raise typer.Exit(code=2) from e
    except Exception as e:
        logger.critical("RUBEM unexpectedly quit.")
        logger.exception(e)
        raise typer.Exit(code=1) from e

    logger.info("RUBEM successfully finished!")


@app.command()
def calibrate(
    configfile: Annotated[
        Path,
        typer.Option(
            "-c",
            "--configfile",
            callback=_configfile_callback,
            help="Path to the configuration file (JSON).",
        ),
    ],
    observed: Annotated[
        Path,
        typer.Option(
            "--observed",
            exists=True,
            dir_okay=False,
            help="Observed series at the sample stations (CSV or PCRaster TSS).",
        ),
    ],
    run_dir: Annotated[
        Path,
        typer.Option("-o", "--run-dir", help="Directory for the calibration artifacts."),
    ],
    variable: Annotated[
        str, typer.Option("--variable", help="Output variable compared with the observed series.")
    ] = "arn",
    spinup_steps: Annotated[
        int,
        typer.Option("--spinup-steps", min=0, help="Leading time steps excluded from the NSE."),
    ] = 0,
    maxiter: Annotated[
        int, typer.Option("--maxiter", min=1, help="Maximum number of generations.")
    ] = 100,
    popsize: Annotated[
        int, typer.Option("--popsize", min=1, help="Population multiplier of the search.")
    ] = 15,
    seed: Annotated[
        int | None, typer.Option("--seed", help="Seed of the differential evolution.")
    ] = None,
    workers: Annotated[
        int | None,
        typer.Option("--workers", min=1, help="Parallel evaluations (default: all cores but one)."),
    ] = None,
    temp_dir: Annotated[
        Path | None,
        typer.Option("--temp-dir", help="Parent of the per-evaluation output directories."),
    ] = None,
    bound: Annotated[
        list[str] | None,
        typer.Option("--bound", help="Narrow the range of one parameter: NAME=MIN:MAX."),
    ] = None,
    fix: Annotated[
        list[str] | None,
        typer.Option("--fix", help="Keep one parameter out of the search: NAME=VALUE."),
    ] = None,
    stations: Annotated[
        str | None,
        typer.Option(
            "--stations",
            help="Station ids of the objective, comma-separated (default: every shared station).",
        ),
    ] = None,
    init: Annotated[
        InitMethod, typer.Option("--init", help="Initial population of the search.")
    ] = InitMethod.sobol,
    strategy: Annotated[
        str, typer.Option("--strategy", help="Differential evolution strategy.")
    ] = "best1exp",
    polish: Annotated[
        bool,
        typer.Option("--polish/--no-polish", help="Refine the best candidate with a local search."),
    ] = False,
) -> None:
    """Calibrate the model parameters against an observed series."""
    # The options that carry a small language of their own are read first, so
    # that a typo costs nothing but the message naming the form expected.
    bounds = _parse_bounds(bound)
    fixed = _parse_fixed(fix)
    selected_stations = _parse_stations(stations)

    require_runtime_deps()
    require_calibration_deps()

    from .calibration.runner import CalibrationError, CalibrationSettings
    from .calibration.runner import calibrate as run_calibration

    settings_arguments: dict = {
        "variable": variable,
        "spinup_steps": spinup_steps,
        "maxiter": maxiter,
        "popsize": popsize,
        "seed": seed,
        "init": init.value,
        "strategy": strategy,
        "polish": polish,
    }
    if workers is not None:
        settings_arguments["workers"] = workers
    if temp_dir is not None:
        settings_arguments["temp_dir"] = str(temp_dir)
    if bounds:
        settings_arguments["bounds"] = bounds
    if fixed:
        settings_arguments["fixed"] = fixed
    if selected_stations:
        settings_arguments["stations"] = selected_stations

    try:
        # The library only logs; the progress a command-line calibration is
        # expected to show is written here, so that an embedded calibration
        # stays silent unless its host configures logging.
        print("Loading configuration and validating inputs...", flush=True)
        print("Calibration started...", flush=True)
        result = run_calibration(
            configfile, observed, run_dir, CalibrationSettings(**settings_arguments)
        )
    except (ConfigurationError, ValidationError, ValueError) as e:
        # A configuration the user can fix: no traceback, the message says what.
        logger.critical("Invalid configuration: %s", e)
        raise typer.Exit(code=1) from e
    except CalibrationError as e:
        # The calibration itself refused to run or produced nothing usable;
        # the message says what, so no traceback either.
        logger.critical("Calibration failed: %s", e)
        raise typer.Exit(code=1) from e
    except KeyboardInterrupt as e:
        logger.critical("RUBEM was interrupted by the user.")
        raise typer.Exit(code=2) from e
    except Exception as e:
        logger.critical("RUBEM unexpectedly quit.")
        logger.exception(e)
        raise typer.Exit(code=1) from e

    best_nse = "n/a" if result.best_nse is None else f"{result.best_nse:.6f}"
    print("Calibration finished successfully!", flush=True)
    print(f"Best NSE: {best_nse}", flush=True)
    print(f"Best objective: {result.best_objective:.6g}", flush=True)
    print(f"Evaluations: {result.evaluations}", flush=True)
    print(f"Generations: {result.generations}", flush=True)
    print(f"Evaluations table: {result.evaluations_csv}", flush=True)
    print(f"Result: {result.result_json}", flush=True)
    print(f"Calibrated configuration: {result.calibrated_config}", flush=True)
    print(f"Observed summary: {result.run_dir / 'observed.csv'}", flush=True)
    print(f"Stations table: {result.stations_csv}", flush=True)
    print(f"Best candidate series: {result.best_series}", flush=True)

    logger.info("RUBEM successfully finished!")


@config_app.command("schema")
def config_schema(
    schema_format: Annotated[
        SchemaFormat,
        typer.Option("--format", help="Configuration file format (1.0 by default)."),
    ] = SchemaFormat.v1,
) -> None:
    """Print the JSON Schema of the configuration file."""
    if schema_format is SchemaFormat.legacy:
        from .configuration.model_configuration_file import ModelConfigurationFile

        schema = ModelConfigurationFile.model_json_schema(by_alias=True)
    else:
        from .configuration.model_configuration_file_v1 import ModelConfigurationFileV1

        schema = ModelConfigurationFileV1.model_json_schema(by_alias=True)
    print(json.dumps(schema, indent=2))


@config_app.command("migrate")
def config_migrate(
    configfile: Annotated[
        Path,
        typer.Option("-c", "--configfile", callback=_configfile_callback, help="Legacy file."),
    ],
    output: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="Destination (default: <name>-v1.json alongside)."),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite the destination if it exists.")
    ] = False,
) -> None:
    """Convert a legacy configuration file to format 1.0."""
    from .configuration.migrate import migrate_legacy_file

    try:
        written = migrate_legacy_file(configfile, output, force=force)
    except FileExistsError as e:
        logger.critical("%s", e)
        raise typer.Exit(code=1) from e
    except (ValidationError, ValueError) as e:
        logger.critical("Invalid configuration: %s", e)
        raise typer.Exit(code=1) from e
    print(f"Wrote {written}")


def _configure_process() -> None:
    """Set up logging and the language from the application settings."""
    setup_logging()
    app_settings = AppSettings.default()
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


_LEGACY_OPTIONS = {"-c", "--configfile", "-s", "--skip-inputs-validation"}
_legacy_invocation = False


def _legacy_arguments(argv: Sequence[str]) -> list[str]:
    """Map the former ``rubem -c <file> [-s]`` spelling onto ``rubem run``.

    The old form is recognised when every argument is one of its options (or
    the value of ``-c``); a ``DeprecationWarning`` is emitted and the arguments
    are handed to ``run``.
    """
    global _legacy_invocation
    _legacy_invocation = False
    arguments = list(argv)
    if not arguments or arguments[0] in ("run", "config", "calibrate", "preprocess"):
        return arguments
    options = [a for a in arguments if a.startswith("-")]
    if not options or not {o.split("=", 1)[0] for o in options} <= _LEGACY_OPTIONS:
        return arguments
    if not any(o.split("=", 1)[0] in ("-c", "--configfile") for o in options):
        return arguments
    warnings.warn(
        "'rubem -c <config>' is deprecated; use 'rubem run -c <config>'.",
        DeprecationWarning,
        stacklevel=3,
    )
    # Logged by the root callback, once logging is configured.
    _legacy_invocation = True
    return ["run", *arguments]


def main(argv: Sequence[str] | None = None) -> None:
    """Run the RUBEM command line.

    This is the console script entry point; it returns normally when the
    command succeeds.

    :param argv: Command line arguments, without the program name. Defaults to
        ``None``, which reads ``sys.argv``.
    :type argv: Sequence[str], optional

    :raises SystemExit(0): After ``--version`` or ``--help``.
    :raises SystemExit(1): If the simulation fails or the configuration is invalid.
    :raises SystemExit(2): If the arguments are invalid or the program is
        interrupted by the user.
    """
    arguments = _legacy_arguments(sys.argv[1:] if argv is None else argv)
    try:
        # Outside standalone mode a ``typer.Exit`` (``--version``, ``--help``,
        # a failed run) comes back as its exit code; a command that returns
        # normally yields ``None``.
        code = app(args=arguments, prog_name="rubem", standalone_mode=False)
    except typer.Abort as e:
        logger.critical("RUBEM was interrupted by the user.")
        raise SystemExit(2) from e
    except Exception as e:
        # Usage errors (missing options, unknown commands) know how to print
        # themselves and carry their exit code; anything else is a real crash.
        if hasattr(e, "show") and hasattr(e, "exit_code"):
            e.show()
            raise SystemExit(e.exit_code) from e
        raise
    if code is not None:
        raise SystemExit(code)


def setup_logging(custom_logging_config: dict | None = None):
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
