import json
import logging
import os
import tempfile
import textwrap
from pathlib import Path

from .._paths import PathInput, as_path
from ..configuration._json import read_json
from ..configuration._problems import ConfigurationError, Problem
from ..configuration.calibration_parameters import CalibrationParameters
from ..configuration.initial_soil_conditions import InitialSoilConditions
from ..configuration.input_raster_files import InputRasterFiles
from ..configuration.input_raster_series import InputRasterSeries
from ..configuration.input_table_files import InputTableFiles
from ..configuration.model_configuration_file import ModelConfigurationFile
from ..configuration.model_configuration_file_v1 import (
    SERIES_NAMES,
    VARIABLE_IDS,
    DirectoryRasterSeries,
    ModelConfigurationFileV1,
    RasterFormat,
    TimeSeriesFormat,
)
from ..configuration.model_constants import ModelConstants
from ..configuration.output_data_directory import OutputDataDirectory
from ..configuration.output_format import OutputFileFormat, TimeSeriesFileFormat
from ..configuration.output_raster_base import OutputRasterBase
from ..configuration.output_variables import OutputVariable, OutputVariables
from ..configuration.raster_grid_area import RasterGrid
from ..configuration.raster_series_resolver import (
    resolvers_from_legacy,
    resolvers_from_v1,
    validate_resolved_series,
)
from ..configuration.simulation_period import SimulationPeriod
from ..validation.lookup_tables import check_lookup_tables, check_runoff_coefficient_domain


class ModelConfiguration:
    """Represents the configuration settings for the model.

    The `ModelConfiguration` class is responsible for loading and storing the configuration settings
    required for running the model. It supports loading configuration from either a dictionary or a JSON file.

    :param config_input: The configuration input: a dictionary with the legacy sections, or the
        path of a legacy JSON file.
    :param validate_input: Whether to validate the input files and their content. Defaults to `True`.
    :type validate_input: bool, optional
    :param base_dir: Directory the relative paths of the configuration are anchored on. Defaults to
        the directory of the JSON file, or to ``None`` (paths kept as given) for a dictionary.

    :raises FileNotFoundError: If the specified config file is not found.
    :raises ValueError: If the config file type is not supported, or a setting is missing or invalid
        (``pydantic.ValidationError`` is a ``ValueError``).
    :raises json.JSONDecodeError: If the JSON file is not valid.
    :raises ConfigurationError: If the inputs carry blocking problems.
    """

    def __init__(
        self,
        config_input: dict | PathInput,
        validate_input: bool = True,
        base_dir: PathInput | None = None,
    ):
        self.logger = logging.getLogger(__name__)
        self.problems = []

        self.logger.info(
            "Loading configuration%s...", " and validating inputs" if validate_input else ""
        )
        try:
            self.file = None
            self.file_v1 = None
            if isinstance(config_input, dict):
                self.logger.debug("Reading configuration from dictionary")
                self.config = config_input
                self.__parse(config_input, duplicates=[])
            elif isinstance(config_input, (str, bytes, os.PathLike)):
                config_input_path = as_path(config_input)
                config_input_str = str(config_input_path)
                if not config_input_path.exists() or not config_input_path.is_file():
                    self.logger.error("Config file not found: %s", config_input_str)
                    raise FileNotFoundError(f"Config file not found: {config_input_str}")

                if config_input_str.endswith(".json"):
                    duplicates = []
                    self.config = self.__read_json(config_input_str, duplicates)
                else:
                    self.logger.error("Unsupported file type: %s", config_input_str)
                    raise ValueError("Unsupported file type")
                self.__parse(self.config, duplicates)
                if base_dir is None:
                    base_dir = config_input_path.absolute().parent
            else:
                raise TypeError(f"Unsupported configuration input: {type(config_input).__name__}")
            self.base_dir = str(as_path(base_dir)) if base_dir is not None else None
            if self.file_v1 is not None:
                self.file_v1 = self.file_v1.resolve_paths(base_dir)
                self.__build_from_v1(validate_input)
            else:
                self.file = self.file.resolve_paths(base_dir)
                self.__build_from_legacy(validate_input)
        except Exception as e:
            self.logger.error("Failed to load configuration: %s", e)
            raise

        self.problems.extend(self._series_problems)
        self.problems.extend(self.raster_files.problems)
        if validate_input:
            self.problems.extend(check_lookup_tables(self.lookuptable_files))
            self.problems.extend(
                check_runoff_coefficient_domain(
                    self.lookuptable_files,
                    self.calibration_parameters.w_1,
                    self.calibration_parameters.w_2,
                    self.calibration_parameters.w_3,
                )
            )
        self.__check_inconsistencies()

    def __parse(self, data: dict, duplicates: list[str]) -> None:
        """Validate the document as format 1.0 (``version`` present) or legacy."""
        if isinstance(data, dict) and "version" in data:
            if duplicates:
                raise ValueError(
                    f"Duplicated key(s) {sorted(set(duplicates))} are not allowed in "
                    "configuration format 1.0."
                )
            self.file_v1 = ModelConfigurationFileV1.model_validate(data)
        else:
            if duplicates:
                self.logger.warning(
                    "Duplicated key(s) %s; the last value of each wins.",
                    sorted(set(duplicates)),
                )
            self.file = ModelConfigurationFile.model_validate(data)

    def __build_from_legacy(self, validate_input: bool) -> None:
        self.logger.debug("Loading configuration...")
        file = self.file
        self.simulation_period = SimulationPeriod(
            start=file.sim_time.start,
            end=file.sim_time.end,
            alignment=file.sim_time.alignment,
        )
        self.grid = RasterGrid(file.grid.grid)
        self.calibration_parameters = CalibrationParameters(
            alpha=file.calibration.alpha,
            beta=file.calibration.b,
            w_1=file.calibration.w_1,
            w_2=file.calibration.w_2,
            w_3=file.calibration.w_3,
            rcd=file.calibration.rcd,
            f=file.calibration.f,
            alpha_gw=file.calibration.alpha_gw,
            x=file.calibration.x,
        )
        self.initial_soil_conditions = InitialSoilConditions(
            initial_soil_moisture_content=file.initial_soil_conditions.t_ini,
            initial_baseflow=file.initial_soil_conditions.bfw_ini,
            baseflow_limit=file.initial_soil_conditions.bfw_lim,
            initial_saturated_zone_storage=file.initial_soil_conditions.s_sat_ini,
        )
        self.constants = ModelConstants(
            fraction_photo_active_radiation_max=file.constants.fpar_max,
            fraction_photo_active_radiation_min=file.constants.fpar_min,
            leaf_area_interception_max=file.constants.lai_max,
            impervious_area_interception=file.constants.i_imp,
        )
        self.output_directory = OutputDataDirectory(file.directories.output).ensure_exists()

        output_formats = OutputFileFormat(0)
        if file.raster_file_format.map_raster_series:
            output_formats |= OutputFileFormat.PCRASTER
        if file.raster_file_format.tiff_raster_series:
            output_formats |= OutputFileFormat.GEOTIFF

        self.output_variables = OutputVariables(
            itp=file.generate_file.itp,
            bfw=file.generate_file.bfw,
            srn=file.generate_file.srn,
            eta=file.generate_file.eta,
            lfw=file.generate_file.lfw,
            rec=file.generate_file.rec,
            smc=file.generate_file.smc,
            rnf=file.generate_file.rnf,
            arn=file.generate_file.arn,
            tss=file.generate_file.tss,
            output_formats=output_formats,
            no_data_value=file.raster_file_format.no_data_value,
        )
        from .output_raster_base import reference_crs

        reference_projection = reference_crs(
            file.rasters.clone, file.rasters.georeference, file.rasters.dem
        )
        self.reference_crs = reference_projection
        self.raster_series = InputRasterSeries(
            etp=file.directories.etp,
            etp_filename_prefix=file.filename_prefixes.etp_prefix,
            precipitation=file.directories.prec,
            precipitation_filename_prefix=file.filename_prefixes.prec_prefix,
            ndvi=file.directories.ndvi,
            ndvi_filename_prefix=file.filename_prefixes.ndvi_prefix,
            kp=file.directories.kp,
            kp_filename_prefix=file.filename_prefixes.kp_prefix,
            landuse=file.directories.landuse,
            landuse_filename_prefix=file.filename_prefixes.landuse_prefix,
            validate_input=validate_input,
            required_steps=(
                self.simulation_period.first_step,
                self.simulation_period.last_step,
            ),
            reference_projection=reference_projection,
        )
        self.raster_files = InputRasterFiles(
            dem=file.rasters.dem,
            clone=file.rasters.clone,
            ndvi_max=file.rasters.ndvi_max,
            ndvi_min=file.rasters.ndvi_min,
            soil=file.rasters.soil,
            ldd=file.rasters.ldd,
            sample_locations=file.rasters.samples,
            validate_input=validate_input,
            georeference=file.rasters.georeference,
        )
        self.lookuptable_files = InputTableFiles(
            rainy_days=file.tables.rainydays,
            a_i=file.tables.a_i,
            a_o=file.tables.a_o,
            a_s=file.tables.a_s,
            a_v=file.tables.a_v,
            manning=file.tables.manning,
            bulk_density=file.tables.bulk_density,
            k_sat=file.tables.k_sat,
            t_fcap=file.tables.t_fcap,
            t_sat=file.tables.t_sat,
            t_wp=file.tables.t_wp,
            rootzone_depth=file.tables.rootzone_depth,
            kc_min=file.tables.k_c_min,
            kc_max=file.tables.k_c_max,
            validate_input=validate_input,
        )
        self._series_problems = list(self.raster_series.problems)
        self.series_resolvers = resolvers_from_legacy(self.raster_series)
        self.output_raster_base = OutputRasterBase.from_file(
            base_raster_path=self.raster_files.dem,
            georeference_path=self.raster_files.georeference,
            must_match=[("clone", self.raster_files.clone)],
            allow_rotation=OutputFileFormat.PCRASTER not in output_formats,
        )

    def __build_from_v1(self, validate_input: bool) -> None:
        self.logger.debug("Loading configuration (format 1.0)...")
        file = self.file_v1
        period = file.simulation_period
        self.simulation_period = SimulationPeriod(
            start=period.start, end=period.finish, alignment=period.alignment
        )
        self.grid = RasterGrid(file.raster_info.grid_size)
        calibration = file.model_calibration_parameters
        self.calibration_parameters = CalibrationParameters(
            alpha=calibration.alpha,
            beta=calibration.b,
            w_1=calibration.w_1,
            w_2=calibration.w_2,
            w_3=calibration.w_3,
            rcd=calibration.rcd,
            f=calibration.f,
            alpha_gw=calibration.alpha_gw,
            x=calibration.x,
        )
        initial = file.model_initial_soil_conditions
        self.initial_soil_conditions = InitialSoilConditions(
            initial_soil_moisture_content=initial.t_ini,
            initial_baseflow=initial.bfw_ini,
            baseflow_limit=initial.bfw_lim,
            initial_saturated_zone_storage=initial.s_sat_ini,
        )
        constants = file.model_constants
        self.constants = ModelConstants(
            fraction_photo_active_radiation_max=constants.fpar_max,
            fraction_photo_active_radiation_min=constants.fpar_min,
            leaf_area_interception_max=constants.lai_max,
            impervious_area_interception=constants.i_imp,
        )
        output = file.model_simulation_output
        self.output_directory = OutputDataDirectory(output.dir_path).ensure_exists()

        output_formats = OutputFileFormat(0)
        if RasterFormat.PCRASTER_MAP in output.raster_series.formats:
            output_formats |= OutputFileFormat.PCRASTER
        if RasterFormat.GEOTIFF in output.raster_series.formats:
            output_formats |= OutputFileFormat.GEOTIFF
        time_series_formats = TimeSeriesFileFormat(0)
        if TimeSeriesFormat.CSV in output.time_series_samples.formats:
            time_series_formats |= TimeSeriesFileFormat.CSV
        if TimeSeriesFormat.PCRASTER_TSS in output.time_series_samples.formats:
            time_series_formats |= TimeSeriesFileFormat.PCRASTER_TSS
        aggregation = output.time_series_samples.aggregation.value
        table_suffix = "" if aggregation == "point" else f"_{aggregation}"
        variables = {
            name: OutputVariable(
                id=name,
                is_raster_series_enabled=getattr(output.raster_series, name),
                is_time_series_enabled=getattr(output.time_series_samples, name),
                raster_filename_prefix=name,
                table_filename_prefix=f"tss_{name}{table_suffix}",
            )
            for name in VARIABLE_IDS
        }
        self.output_variables = OutputVariables(
            **variables,
            output_formats=output_formats,
            no_data_value=output.raster_series.no_data_value,
            time_series_formats=time_series_formats,
            aggregation=aggregation,
        )
        rasters = file.rasters
        self.raster_files = InputRasterFiles(
            dem=rasters.dem,
            clone=rasters.clone,
            ndvi_max=rasters.ndvi_max,
            ndvi_min=rasters.ndvi_min,
            soil=rasters.soil,
            ldd=rasters.ldd,
            sample_locations=rasters.samples,
            validate_input=validate_input,
            georeference=rasters.georeference,
            zones=rasters.zones,
        )
        tables = file.lookup_tables
        self.lookuptable_files = InputTableFiles(
            rainy_days=tables.rainy_days,
            a_i=tables.a_i,
            a_o=tables.a_o,
            a_s=tables.a_s,
            a_v=tables.a_v,
            manning=tables.manning,
            bulk_density=tables.bulk_density,
            k_sat=tables.k_sat,
            t_fcap=tables.t_fcap,
            t_sat=tables.t_sat,
            t_wp=tables.t_wp,
            rootzone_depth=tables.rootzone_depth,
            kc_min=tables.kc_min,
            kc_max=tables.kc_max,
            validate_input=validate_input,
        )
        self.series_resolvers = resolvers_from_v1(file)
        window = (self.simulation_period.first_step, self.simulation_period.last_step)
        from .output_raster_base import reference_crs

        reference_projection = reference_crs(rasters.clone, rasters.georeference, rasters.dem)
        self.reference_crs = reference_projection
        series = file.raster_series
        if all(isinstance(getattr(series, name), DirectoryRasterSeries) for name in SERIES_NAMES):
            self.raster_series = InputRasterSeries(
                etp=series.etp.dir_path,
                etp_filename_prefix=series.etp.files_prefix,
                precipitation=series.precipitation.dir_path,
                precipitation_filename_prefix=series.precipitation.files_prefix,
                ndvi=series.ndvi.dir_path,
                ndvi_filename_prefix=series.ndvi.files_prefix,
                kp=series.kp.dir_path,
                kp_filename_prefix=series.kp.files_prefix,
                landuse=series.landuse.dir_path,
                landuse_filename_prefix=series.landuse.files_prefix,
                validate_input=validate_input,
                required_steps=window,
                reference_projection=reference_projection,
            )
            self._series_problems = list(self.raster_series.problems)
        else:
            self.raster_series = None
            if validate_input:
                self._series_problems = validate_resolved_series(
                    self.series_resolvers, *window, reference_projection=reference_projection
                )
            else:
                self.logger.warning("Input data directories validation is disabled.")
                self._series_problems = []
        self.output_raster_base = OutputRasterBase.from_file(
            base_raster_path=self.raster_files.dem,
            georeference_path=self.raster_files.georeference,
            must_match=[("clone", self.raster_files.clone)],
            allow_rotation=OutputFileFormat.PCRASTER not in output_formats,
        )

    def write_metadata(self) -> None:
        """Write ``metadata.json`` next to the outputs of a format 1.0 run.

        A no-op for a legacy configuration, which has no ``metadata`` section.
        Intended to be called once the run has finished successfully (after
        every other output has been written): it is not called while loading
        or validating the configuration, so a configuration that fails
        validation never touches an existing ``metadata.json``. The write
        itself is atomic (a temporary file, replaced onto the target), so a
        failure while writing leaves an existing ``metadata.json`` untouched.
        """
        if self.file_v1 is None:
            return
        document = {
            "version": self.file_v1.version,
            **self.file_v1.metadata.model_dump(mode="json", exclude_none=True),
        }
        target = Path(self.output_directory.path) / "metadata.json"
        handle, temporary = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                file.write(json.dumps(document, indent=2) + "\n")
            Path(temporary).replace(target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    @classmethod
    def load(
        cls,
        config_input: dict | PathInput,
        validate_input: bool = True,
        base_dir: PathInput | None = None,
    ) -> "ModelConfiguration":
        """Load a legacy configuration from a dictionary or a JSON file.

        Relative paths are anchored on the directory of the JSON file, or on
        ``base_dir`` when given (a dictionary has no anchor unless ``base_dir``
        is passed).
        """
        return cls(config_input, validate_input=validate_input, base_dir=base_dir)

    def __check_inconsistencies(self):
        if self.output_variables.any_enabled() and not self.output_variables.file_formats:
            raise ValueError(
                "No raster file format is enabled: set RASTER_FILE_FORMAT.map_raster_series "
                "or RASTER_FILE_FORMAT.tiff_raster_series to true, or disable every output "
                "variable."
            )

        # A run that only writes time series (no raster series enabled, as
        # format 1.0 allows) is not "no output": any_output_enabled() covers
        # both selections so this is reported once, never alongside the
        # sample-locations-specific problem below for the same root cause.
        if not self.output_variables.any_output_enabled():
            reason = "No Output Variables were selected."
            if self.raster_files.sample_locations and self.output_variables.tss:
                reason = (
                    "Sample Locations raster and Time Series generation were enabled but no "
                    "Output Variables were selected."
                )
            self.problems.append(
                Problem(description="Simulation will not produce any output.", reason=reason)
            )

        if self.raster_files.sample_locations and not self.output_variables.tss:
            self.problems.append(
                Problem(
                    description="Simulation will not produce any Time Series tables.",
                    reason="Sample Locations raster was provided but Time Series generation was not enabled.",
                )
            )

        if (
            self.output_variables.tss
            and self.output_variables.aggregation != "zones"
            and not self.raster_files.sample_locations
        ):
            self.problems.append(
                Problem(
                    description="Simulation will not produce any Time Series tables.",
                    reason="Time Series generation was enabled but no Sample Locations raster was provided.",
                )
            )

        if self.problems:
            self.logger.warning("Configuration problems found: %d", len(self.problems))
            for problem in self.problems:
                self.logger.warning("Configuration problem: %s", problem)
        if any(problem.blocking for problem in self.problems):
            raise ConfigurationError(self.problems)

    def __read_json(self, file_path: PathInput, duplicates: list[str]):
        self.logger.debug("Reading JSON file: %s", file_path)
        try:
            return read_json(file_path, on_duplicate=duplicates.extend)
        except json.JSONDecodeError as e:
            self.logger.error("Error parsing JSON file: %s", e)
            raise

    def __series_summary(self) -> str:
        if self.raster_series is not None:
            return str(self.raster_series)
        return "\n".join(
            f"{name}: {resolver!r}" for name, resolver in self.series_resolvers.items()
        )

    def __str__(self):
        # Workaround for "Escape sequence (backslash) not allowed in expression portion of f-string prior to Python 3.12"
        tab = "\t"
        return (
            f"Simulation period: {self.simulation_period}\n"
            f"Grid area: {self.grid}\n"
            f"Raster Series:\n{textwrap.indent(self.__series_summary(), tab)}\n"
            f"Raster files:\n{textwrap.indent(str(self.raster_files), tab)}\n"
            f"Lookuptable files:\n{textwrap.indent(str(self.lookuptable_files), tab)}\n"
            f"Calibration parameters:\n{textwrap.indent(str(self.calibration_parameters), tab)}\n"
            f"Initial soil conditions:\n{textwrap.indent(str(self.initial_soil_conditions), tab)}\n"
            f"Constants:\n{textwrap.indent(str(self.constants), tab)}\n"
            f"Output directory: {self.output_directory}\n"
            f"Output Raster Series:\n{textwrap.indent(str(self.output_variables), tab)}"
        )
