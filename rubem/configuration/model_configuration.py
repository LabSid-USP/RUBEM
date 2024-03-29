from datetime import datetime
import json
import logging
import os
import textwrap
from typing import Union

from ..configuration.calibration_parameters import CalibrationParameters
from ..configuration.initial_soil_conditions import InitialSoilConditions
from ..configuration.input_raster_files import InputRasterFiles
from ..configuration.input_raster_series import InputRasterSeries
from ..configuration.input_table_files import InputTableFiles
from ..configuration.model_constants import ModelConstants
from ..configuration.output_data_directory import OutputDataDirectory
from ..configuration.output_format import OutputFileFormat
from ..configuration.output_raster_base import OutputRasterBase
from ..configuration.output_variables import OutputVariables
from ..configuration.raster_grid_area import RasterGrid
from ..configuration.simulation_period import SimulationPeriod


class ModelConfiguration:
    """Represents the configuration settings for the model.

    The `ModelConfiguration` class is responsible for loading and storing the configuration settings
    required for running the model. It supports loading configuration from either a dictionary or a JSON file.

    :param config_input: The configuration input. It can be a dictionary containing the configuration
        settings, a file path to a JSON file, or a file-like object.

    :param validate_input: Whether to validate the input. Defaults to `True`.
    :type validate_input: bool, optional

    :raises FileNotFoundError: If the specified config file is not found.
    :raises ValueError: If the config file type is not supported.
    :raises json.JSONDecodeError: If the JSON file is not valid.
    :raises KeyError: If a required setting is missing.
    :raises ValueError: If a setting value is invalid.
    """

    def __init__(
        self, config_input: Union[dict, str, bytes, os.PathLike], validate_input: bool = True
    ):
        self.logger = logging.getLogger(__name__)
        self.problems = []

        print(f"Loading configuration{' and validating inputs' if validate_input else ''}...")
        try:
            if isinstance(config_input, dict):
                self.logger.debug("Reading configuration from dictionary")
                self.config = config_input
            elif isinstance(config_input, (str, bytes, os.PathLike)):
                config_input_str = str(config_input)
                if not os.path.exists(config_input_str) or not os.path.isfile(config_input_str):
                    self.logger.error("Config file not found: %s", config_input_str)
                    raise FileNotFoundError(f"Config file not found: {config_input_str}")

                if config_input_str.endswith(".json"):
                    self.config = self.__read_json(config_input_str)
                else:
                    self.logger.error("Unsupported file type: %s", config_input_str)
                    raise ValueError("Unsupported file type")

            self.logger.debug("Loading configuration...")
            self.simulation_period = SimulationPeriod(
                start=datetime.strptime(self.__get_setting("SIM_TIME", "start"), "%d/%m/%Y"),
                end=datetime.strptime(self.__get_setting("SIM_TIME", "end"), "%d/%m/%Y"),
                alignment=(
                    datetime.strptime(
                        self.__get_setting("SIM_TIME", "alignment", optional=True), "%d/%m/%Y"
                    )
                    if self.__get_setting("SIM_TIME", "alignment", optional=True)
                    else None
                ),
            )
            self.grid = RasterGrid(float(self.__get_setting("GRID", "grid")))
            self.calibration_parameters = CalibrationParameters(
                alpha=float(self.__get_setting("CALIBRATION", "alpha")),
                beta=float(self.__get_setting("CALIBRATION", "b")),
                w_1=float(self.__get_setting("CALIBRATION", "w_1")),
                w_2=float(self.__get_setting("CALIBRATION", "w_2")),
                w_3=float(self.__get_setting("CALIBRATION", "w_3")),
                rcd=float(self.__get_setting("CALIBRATION", "rcd")),
                f=float(self.__get_setting("CALIBRATION", "f")),
                alpha_gw=float(self.__get_setting("CALIBRATION", "alpha_gw")),
                x=float(self.__get_setting("CALIBRATION", "x")),
            )
            self.initial_soil_conditions = InitialSoilConditions(
                initial_soil_moisture_content=float(
                    self.__get_setting("INITIAL_SOIL_CONDITIONS", "t_ini")
                ),
                initial_baseflow=float(self.__get_setting("INITIAL_SOIL_CONDITIONS", "bfw_ini")),
                baseflow_limit=float(self.__get_setting("INITIAL_SOIL_CONDITIONS", "bfw_lim")),
                initial_saturated_zone_storage=float(
                    self.__get_setting("INITIAL_SOIL_CONDITIONS", "s_sat_ini")
                ),
            )
            self.constants = ModelConstants(
                fraction_photo_active_radiation_max=float(
                    self.__get_setting("CONSTANTS", "fpar_max")
                ),
                fraction_photo_active_radiation_min=float(
                    self.__get_setting("CONSTANTS", "fpar_min")
                ),
                leaf_area_interception_max=float(self.__get_setting("CONSTANTS", "lai_max")),
                impervious_area_interception=float(self.__get_setting("CONSTANTS", "i_imp")),
            )
            self.output_directory = OutputDataDirectory(self.__get_setting("DIRECTORIES", "output"))

            output_formats = OutputFileFormat.PCRASTER

            if str_to_bool(
                self.__get_setting("RASTER_FILE_FORMAT", "tiff_raster_series", optional=True)
            ):
                output_formats = output_formats | OutputFileFormat.GEOTIFF

            self.output_variables = OutputVariables(
                itp=str_to_bool(self.__get_setting("GENERATE_FILE", "itp")),
                bfw=str_to_bool(self.__get_setting("GENERATE_FILE", "bfw")),
                srn=str_to_bool(self.__get_setting("GENERATE_FILE", "srn")),
                eta=str_to_bool(self.__get_setting("GENERATE_FILE", "eta")),
                lfw=str_to_bool(self.__get_setting("GENERATE_FILE", "lfw")),
                rec=str_to_bool(self.__get_setting("GENERATE_FILE", "rec")),
                smc=str_to_bool(self.__get_setting("GENERATE_FILE", "smc")),
                rnf=str_to_bool(self.__get_setting("GENERATE_FILE", "rnf")),
                arn=str_to_bool(self.__get_setting("GENERATE_FILE", "arn")),
                tss=str_to_bool(self.__get_setting("GENERATE_FILE", "tss")),
                output_formats=output_formats,
            )

            self.raster_series = InputRasterSeries(
                etp=self.__get_setting("DIRECTORIES", "etp"),
                etp_filename_prefix=self.__get_setting("FILENAME_PREFIXES", "etp_prefix"),
                precipitation=self.__get_setting("DIRECTORIES", "prec"),
                precipitation_filename_prefix=self.__get_setting(
                    "FILENAME_PREFIXES", "prec_prefix"
                ),
                ndvi=self.__get_setting("DIRECTORIES", "ndvi"),
                ndvi_filename_prefix=self.__get_setting("FILENAME_PREFIXES", "ndvi_prefix"),
                kp=self.__get_setting("DIRECTORIES", "kp"),
                kp_filename_prefix=self.__get_setting("FILENAME_PREFIXES", "kp_prefix"),
                landuse=self.__get_setting("DIRECTORIES", "landuse"),
                landuse_filename_prefix=self.__get_setting("FILENAME_PREFIXES", "landuse_prefix"),
                validate_input=validate_input,
            )
            self.raster_files = InputRasterFiles(
                dem=self.__get_setting("RASTERS", "dem"),
                clone=self.__get_setting("RASTERS", "clone"),
                ndvi_max=self.__get_setting("RASTERS", "ndvi_max"),
                ndvi_min=self.__get_setting("RASTERS", "ndvi_min"),
                soil=self.__get_setting("RASTERS", "soil"),
                ldd=self.__get_setting("RASTERS", "ldd", optional=True),
                sample_locations=self.__get_setting("RASTERS", "samples", optional=True),
                validate_input=validate_input,
            )
            self.lookuptable_files = InputTableFiles(
                rainy_days=self.__get_setting("TABLES", "rainydays"),
                a_i=self.__get_setting("TABLES", "a_i"),
                a_o=self.__get_setting("TABLES", "a_o"),
                a_s=self.__get_setting("TABLES", "a_s"),
                a_v=self.__get_setting("TABLES", "a_v"),
                manning=self.__get_setting("TABLES", "manning"),
                bulk_density=self.__get_setting("TABLES", "bulk_density"),
                k_sat=self.__get_setting("TABLES", "k_sat"),
                t_fcap=self.__get_setting("TABLES", "t_fcap"),
                t_sat=self.__get_setting("TABLES", "t_sat"),
                t_wp=self.__get_setting("TABLES", "t_wp"),
                rootzone_depth=self.__get_setting("TABLES", "rootzone_depth"),
                kc_min=self.__get_setting("TABLES", "k_c_min"),
                kc_max=self.__get_setting("TABLES", "k_c_max"),
                validate_input=validate_input,
            )
            self.output_raster_base = OutputRasterBase(base_raster_path=self.raster_files.dem)
        except Exception as e:
            self.logger.error("Failed to load configuration: %s", e)
            raise

        self.problems.extend(self.raster_series.problems)
        self.problems.extend(self.raster_files.problems)
        self.__check_inconsistencies()

    def __check_inconsistencies(self):
        if not self.output_variables.any_enabled():
            self.problems.append(
                {
                    "description": "Simulation will not produce any output.",
                    "reason": "No Output Variables were selected.",
                    "blocking": False,
                }
            )

        if self.raster_files.sample_locations and not self.output_variables.tss:
            self.problems.append(
                {
                    "description": "Simulation will not produce any Time Series tables.",
                    "reason": "Sample Locations raster was provided but Time Series generation was not enabled.",
                    "blocking": False,
                }
            )

        if self.output_variables.tss and not self.raster_files.sample_locations:
            self.problems.append(
                {
                    "description": "Simulation will not produce any Time Series tables.",
                    "reason": "Time Series generation was enabled but no Sample Locations raster was provided.",
                    "blocking": False,
                }
            )

        if (
            self.raster_files.sample_locations
            and self.output_variables.tss
            and not self.output_variables.any_enabled()
        ):
            self.problems.append(
                {
                    "description": "Simulation will not produce any output.",
                    "reason": "Sample Locations raster and Time Series generation were enabled but no Output Variables were selected.",
                    "blocking": False,
                }
            )

        if self.problems:
            print("Configuration problems found:")
            i = 1
            for problem in self.problems:
                message = f"{problem.get('description')}: {problem.get('reason')} {problem.get('implication', '')} {problem.get('file', '')}"
                self.logger.warning("Configuration problem: %s", message)
                print(f"{i}) {message}")
                i += 1
            print()

    def __read_json(self, file_path: Union[str, bytes, os.PathLike]):
        self.logger.debug("Reading JSON file: %s", file_path)
        try:
            with open(file=file_path, mode="r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.logger.error("Error parsing JSON file: %s", e)
            raise

    def __get_setting(self, section, setting, optional=False):
        try:
            return self.config[section][setting]
        except KeyError as e:
            if not optional:
                self.logger.error("Missing setting: %s in section: %s", setting, section)
                raise ValueError(f"Missing setting: {setting} in section: {section}") from e

            self.logger.warning("Optional setting not found: %s in section: %s", setting, section)
            return ""

    def __str__(self):
        # Workaround for "Escape sequence (backslash) not allowed in expression portion of f-string prior to Python 3.12"
        tab = "\t"
        return (
            f"Simulation period: {self.simulation_period}\n"
            f"Grid area: {self.grid}\n"
            f"Raster Series:\n{textwrap.indent(str(self.raster_series), tab)}\n"
            f"Raster files:\n{textwrap.indent(str(self.raster_files), tab)}\n"
            f"Lookuptable files:\n{textwrap.indent(str(self.lookuptable_files), tab)}\n"
            f"Calibration parameters:\n{textwrap.indent(str(self.calibration_parameters), tab)}\n"
            f"Initial soil conditions:\n{textwrap.indent(str(self.initial_soil_conditions), tab)}\n"
            f"Constants:\n{textwrap.indent(str(self.constants), tab)}\n"
            f"Output directory: {self.output_directory}\n"
            f"Output Raster Series:\n{textwrap.indent(str(self.output_variables), tab)}"
        )


def str_to_bool(value: str) -> bool:
    """
    Converts a string value to a boolean.

    :param value: The string value to be converted.
    :type value: str

    :return: The boolean representation of the string value.
    :rtype: bool
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.lower() in ("yes", "true", "t", "1")

    raise ValueError(f"Invalid value for boolean conversion: {type(value)}")
