import logging
import os
import argparse
from datetime import datetime
from configparser import ConfigParser

try:
    from validation import _schemas
    from validation._exception_validation import ValidationException
except ImportError:
    from . import _schemas
    from ._exception_validation import ValidationException

logger = logging.getLogger(__name__)


def filePathArgValidator(path: str):
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(
            f'model config file "{path}" does not exists'
        )
    elif not os.path.isfile(path):
        raise argparse.ArgumentTypeError(
            f'model config file "{path}" is not a valid file'
        )
    else:
        return path


def dateValidator(config: ConfigParser):

    format = "%d/%m/%Y"

    for option in config.options("SIM_TIME"):
        try:
            date_string = config.get("SIM_TIME", option)
        except Exception as e:
            raise ValidationException from e
        else:
            try:
                datetime.strptime(date_string, format)
            except ValueError as e:
                raise ValidationException(
                    f"Incorrect SIM_TIME:{option} date string format. It"
                    " should be DD/MM/YYYY"
                ) from e
            except Exception as e:
                raise SystemExit(1, e)


def fileNamePrefixValidator(config: ConfigParser):
    for option in config.options("FILENAME_PREFIXES"):
        try:
            prefix = config.get("FILENAME_PREFIXES", option)
        except Exception as e:
            raise ValidationException from e

        try:
            assert 1 <= len(prefix) <= 8, (
                "The raster map series prefix must follow"
                "the standard 8.3 DOS style format"
            )
        except AssertionError as e:
            raise ValidationException(
                "Invalid filename prefix length"
                f" FILENAME_PREFIXES:{option}:{prefix}"
            ) from e
        except Exception as e:
            raise SystemExit(1, e)


def filePathValidator(config: ConfigParser):
    sections = ["RASTERS", "TABLES"]
    for section in sections:
        for option in config.options(section):
            try:
                path = config.get(section, option)
            except Exception as e:
                raise ValidationException from e
            else:
                if not os.path.exists(path):
                    raise ValidationException(
                        f"{section}:{option}:{path} does not exists"
                    )
                elif not os.path.isfile(path):
                    raise ValidationException(
                        f"{section}:{option}:{path} is not a valid file"
                    )


def directoryPathValidator(config: ConfigParser):
    for option in config.options("DIRECTORIES"):
        try:
            path = config.get("DIRECTORIES", option)
        except Exception as e:
            raise ValidationException from e
        else:
            if not os.path.exists(path):
                raise ValidationException(
                    f"DIRECTORIES:{option}:{path} does not exists"
                )
            elif not os.path.isdir(path):
                raise ValidationException(
                    f"DIRECTORIES:{option}:{path} is not a valid directory"
                )


def floatTypeValidator(config: ConfigParser):
    sections = ["GRID", "CALIBRATION", "INITIAL_SOIL_CONDITIONS", "CONSTANTS"]
    for section in sections:
        for option in config.options(section):
            try:
                config.getfloat(section, option)
            except Exception as e:
                raise ValidationException(
                    f"{section}:{option} does not contain a valid float value"
                ) from e


def booleanTypeValidator(config: ConfigParser):
    sections = ["GENERATE_FILE", "RASTER_FILE_FORMAT"]
    for section in sections:
        for option in config.options(section):
            try:
                config.getboolean(section, option)
            except Exception as e:
                raise ValidationException(
                    f"{section}:{option} does not contain a valid boolean"
                    " value"
                ) from e


def value_range_validator(config: ConfigParser):
    sections = ["CALIBRATION", "INITIAL_SOIL_CONDITIONS", "CONSTANTS"]
    for section in sections:
        for option in config.options(section):
            if option in _schemas.parameters_value_ranges.get(section).keys():
                value = config.getfloat(section, option)
                value_min, value_max = _schemas.parameters_value_ranges.get(
                    section
                ).get(option)
                var_name = _schemas.parameters_titles.get(section).get(option)
                if not value_min <= value <= value_max:
                    raise ValidationException(
                        f"The {var_name} ({option}) value must be in the value"
                        f" range [{value_min}, {value_max}]"
                    )


def output_generation_enforcer(config: ConfigParser):
    if all(
        value == "False"
        for option, value in config["GENERATE_FILE"].items()
        if option != "tss"
    ):
        raise ValidationException(
            "At least one output variable must be selected"
        )


def output_format_enforcer(config: ConfigParser):
    if all(
        value == "False" for value in config["RASTER_FILE_FORMAT"].values()
    ):
        raise ValidationException("An output file format must be selected")


def fpar_constraints_enforcer(config: ConfigParser):
    fpar_min = config.getfloat("CONSTANTS", "fpar_min")
    fpar_max = config.getfloat("CONSTANTS", "fpar_max")
    if not fpar_max > fpar_min:
        raise ValidationException("fpar_max must be greater than fpar_min")


def bfw_constraints_enforcer(config: ConfigParser):
    bfw_lim = config.getfloat("INITIAL_SOIL_CONDITIONS", "bfw_lim")
    bfw_ini = config.getfloat("INITIAL_SOIL_CONDITIONS", "bfw_ini")
    if not bfw_lim > bfw_ini:
        raise ValidationException(
            "Baseflow threshold (bfw_lim) must be greater than zero and"
            " Initial Baseflow (bfw_ini)"
        )


def weights_constraints_enforcer(config: ConfigParser):
    w1 = config.getfloat("CALIBRATION", "w_1")
    w2 = config.getfloat("CALIBRATION", "w_2")
    w3 = config.getfloat("CALIBRATION", "w_3")
    if not w1 + w2 + w3 == 1.0:
        raise ValidationException(
            "The sum of the weight factors Land Use (w1), Soil Moisture (w2)"
            " and Slope (w3) must equal 1.0"
        )


def domain_validator(config: ConfigParser):
    output_generation_enforcer(config)
    output_format_enforcer(config)
    fpar_constraints_enforcer(config)
    bfw_constraints_enforcer(config)
    weights_constraints_enforcer(config)


def schemaValidator(config: ConfigParser):
    for section, keys in _schemas.required_config_schema.items():
        if section not in config:
            raise ValidationException(
                f"Missing section '{section}' in the configuration file"
            )

        for key, values in keys.items():
            if key not in config[section] or config.get(section, key) == "":
                raise ValidationException(
                    f"Missing value for '{key}' under section {section} in the"
                    " config file"
                )
