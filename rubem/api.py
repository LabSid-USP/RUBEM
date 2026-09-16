"""The public Python API of RUBEM.

Three names are public: :class:`Model`, the entry point that loads a
configuration and runs the model; :class:`RunResult`, the description of what a
finished run wrote; and :class:`ConfigurationError`, re-exported here, raised
when a configuration carries blocking problems.

Stability
    ``rubem.api`` is the supported programmatic surface. Every other module of
    the package is internal and may change without notice. While the version is
    below 1.0, a breaking change to ``rubem.api`` bumps the minor version and is
    listed in the changelog.

Process limitation
    PCRaster keeps the clone and the raster memory process-wide (``setclone``
    is global to the process and the memory of a run is not reclaimed), so
    repeated :meth:`Model.run` calls in one interpreter grow the resident
    memory and must share the same grid. :meth:`Model.run_isolated` runs the
    simulation in a fresh spawned subprocess instead, at the cost of an
    interpreter start-up per call; it is the form to use for repeated runs,
    for runs on different grids and for parallel runs.

Importing this module does not require PCRaster or GDAL; running the model
does, and raises :class:`ImportError` with the installation guidance when they
are missing.

Logging
    The package reports its progress through the ``rubem`` logger and writes
    nothing to standard output of its own; configure that logger to follow a
    run. The records of the simulation of an isolated run are emitted in its
    subprocess, which starts from the default logging configuration and does
    not inherit the handlers of the caller; the loading of the configuration
    happens in the calling process and is logged there.
"""

import logging
import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ._deps import missing_runtime_deps, runtime_deps_message
from ._paths import PathInput
from .configuration._problems import ConfigurationError
from .configuration.output_format import OutputFileFormat, TimeSeriesFileFormat
from .file._naming import get_raster_series_filepath, output_raster_filename

if TYPE_CHECKING:
    from .configuration.model_configuration import ModelConfiguration

__all__ = ["Model", "RunResult", "ConfigurationError"]

logger = logging.getLogger(__name__)

_METADATA_FILENAME = "metadata.json"


@dataclass(frozen=True)
class RunResult:
    """What a finished run wrote, enumerated from the configuration.

    The paths are derived from the configuration and the naming rules of the
    model, never from a listing of the output directory, so a result describes
    the run that produced it even when the directory holds the outputs of
    earlier runs as well. They are absolute, so a result of an isolated run
    names the same files whatever the caller does with its working directory
    afterwards.

    :param output_directory: Directory the run wrote to.
    :param rasters: Raster members per variable id, the PCRaster series in step
        order followed by the GeoTIFF series in step order, restricted to the
        enabled formats.
    :param time_series: Time series tables per variable id, the CSV table
        followed by the PCRaster TSS table, restricted to the enabled formats.
        Empty when the run writes no time series. The ``zones_mapping.csv`` a
        run aggregated over zones writes is not listed: it belongs to the
        aggregation, not to a variable.
    :param metadata: The ``metadata.json`` of a format 1.0 run, ``None`` for a
        legacy configuration, which has no metadata section.
    :param first_step: First simulated time step.
    :param last_step: Last simulated time step.
    :param elapsed_seconds: Wall-clock duration of the run itself. An isolated
        run measures the simulation inside its subprocess, not the interpreter
        start-up the call also pays.
    """

    output_directory: Path
    rasters: dict[str, tuple[Path, ...]]
    time_series: dict[str, tuple[Path, ...]]
    metadata: Path | None
    first_step: int
    last_step: int
    elapsed_seconds: float


class Model:
    """A configured model, ready to run.

    Build one with :meth:`from_file` or :meth:`from_config` rather than by
    calling the constructor, unless a :class:`ModelConfiguration` has already
    been loaded elsewhere.

    :param configuration: The loaded configuration.
    :param validate_input: Whether an isolated run revalidates the input files
        and their content when it rebuilds the configuration. It has no effect
        on ``configuration``, which is already loaded; pass the value the
        configuration was loaded with.
    """

    def __init__(self, configuration: "ModelConfiguration", *, validate_input: bool = True) -> None:
        self._configuration = configuration
        self._validate_input = bool(validate_input)

    @classmethod
    def from_file(
        cls,
        path: PathInput,
        *,
        validate_input: bool = True,
        base_dir: PathInput | None = None,
    ) -> "Model":
        """Load a configuration file and return the model it configures.

        :param path: The JSON configuration file, legacy or format 1.0.
        :param validate_input: Whether to validate the input files and their content.
        :param base_dir: Directory the relative paths of the configuration are
            anchored on. Defaults to the directory of the file.
        :raises ImportError: If PCRaster or GDAL are not installed.
        :raises FileNotFoundError: If ``path``, or a raster or table it names,
            is not there.
        :raises json.JSONDecodeError: If the file is not JSON.
        :raises pydantic.ValidationError: If the document does not match the schema.
        :raises ConfigurationError: If the inputs carry blocking problems.
        """
        _require_runtime_deps()
        from .configuration.model_configuration import ModelConfiguration

        configuration = ModelConfiguration(path, validate_input, base_dir)
        return cls(configuration, validate_input=validate_input)

    @classmethod
    def from_config(
        cls,
        config: "dict | ModelConfiguration",
        *,
        validate_input: bool = True,
        base_dir: PathInput | None = None,
    ) -> "Model":
        """Return the model a configuration document, or a loaded configuration, configures.

        :param config: The configuration document (legacy or format 1.0) as a
            dictionary, or an already loaded :class:`ModelConfiguration`, which
            is used as it is.
        :param validate_input: Whether to validate the input files and their
            content. An already loaded configuration is not validated again;
            the flag then only says whether an isolated run revalidates when it
            rebuilds the configuration.
        :param base_dir: Directory the relative paths of the document are
            anchored on. A dictionary has no anchor unless this is passed.
            Ignored when ``config`` is already loaded.
        :raises ImportError: If PCRaster or GDAL are not installed.
        :raises FileNotFoundError: If a raster or table the document names is
            not there.
        :raises pydantic.ValidationError: If the document does not match the schema.
        :raises ConfigurationError: If the inputs carry blocking problems.
        """
        _require_runtime_deps()
        from .configuration.model_configuration import ModelConfiguration

        if isinstance(config, ModelConfiguration):
            return cls(config, validate_input=validate_input)
        return cls(
            ModelConfiguration(config, validate_input, base_dir), validate_input=validate_input
        )

    @property
    def configuration(self) -> "ModelConfiguration":
        """The loaded configuration this model runs."""
        return self._configuration

    def run(self) -> RunResult:
        """Run the simulation in the current process.

        A fresh model framework is built for every call. PCRaster state is
        process-wide, so successive calls in one interpreter share the clone
        and grow the resident memory; see :meth:`run_isolated`.

        :return: What the run wrote.
        :raises ImportError: If PCRaster or GDAL are not installed.
        :raises Exception: Whatever the simulation itself raises, unchanged.
        """
        _require_runtime_deps()
        from .core import DynamicFrameworkWrapper

        logger.info("Starting an in-process run.")
        started = time.perf_counter()
        DynamicFrameworkWrapper(self._configuration).run()
        elapsed = time.perf_counter() - started
        return _describe_run(self._configuration, elapsed)

    def run_isolated(self) -> RunResult:
        """Run the simulation in a fresh spawned subprocess.

        The configuration crosses as its document plus its base directory and
        the validation flag, and is rebuilt on the other side; the result
        crosses as plain data. The subprocess is started for this call only and
        the executor is shut down before returning, so the PCRaster state of the
        run leaves nothing behind. Every call therefore pays a full interpreter
        start-up.

        The spawn start method imports the main module of the caller in the
        subprocess, so a script that calls this method must guard its entry
        point with ``if __name__ == "__main__":`` to avoid re-running itself.

        A configuration problem found while the subprocess rebuilds the
        configuration reaches the caller as the same
        :class:`ConfigurationError`, with its problems; any other exception of
        the run propagates as itself.

        The log records of the simulation are emitted in the subprocess, which
        starts from the default logging configuration: the handlers of the
        caller do not see them.

        :return: What the run wrote.
        :raises ImportError: If PCRaster or GDAL are not installed.
        :raises RuntimeError: If the subprocess dies before the run finishes.
        """
        _require_runtime_deps()
        logger.info("Starting an isolated run in a spawned subprocess.")
        executor = ProcessPoolExecutor(
            max_workers=1,
            mp_context=multiprocessing.get_context("spawn"),
            max_tasks_per_child=1,
        )
        try:
            future = executor.submit(
                _run_document,
                self._configuration.config,
                self._configuration.base_dir,
                self._validate_input,
            )
            document = future.result()
        except BrokenProcessPool as error:
            raise RuntimeError(
                "The subprocess of Model.run_isolated() died before the run finished; "
                "it was killed from outside or the native libraries crashed it."
            ) from error
        finally:
            executor.shutdown(wait=True)
        return _result_from_json(document)


def _run_document(document: dict, base_dir: str | None, validate_input: bool) -> dict[str, Any]:
    """Rebuild a configuration, run it, and return the result as plain data.

    The entry point of the subprocess of :meth:`Model.run_isolated`. It lives at
    module level because the spawn start method imports it by name in the child;
    it is not part of the public surface.

    :param document: The configuration document, legacy or format 1.0.
    :param base_dir: Directory the relative paths of the document are anchored on.
    :param validate_input: Whether to validate the input files and their content.
    :return: The :class:`RunResult` of the run, as a JSON-able dictionary.
    """
    from .configuration.model_configuration import ModelConfiguration
    from .core import DynamicFrameworkWrapper

    configuration = ModelConfiguration(document, validate_input, base_dir)
    started = time.perf_counter()
    DynamicFrameworkWrapper(configuration).run()
    elapsed = time.perf_counter() - started
    return _result_to_json(_describe_run(configuration, elapsed))


def _require_runtime_deps() -> None:
    """Raise with the installation guidance when PCRaster or GDAL are missing.

    :raises ImportError: If any conda-only runtime dependency is missing.
    """
    missing = missing_runtime_deps()
    if missing:
        raise ImportError(runtime_deps_message(missing))


def _describe_run(configuration: "ModelConfiguration", elapsed_seconds: float) -> RunResult:
    """Enumerate the outputs of a finished run from its configuration.

    The output directory is made absolute first: a configuration may name it
    relatively, and a result whose members were half absolute (the PCRaster
    naming helper returns absolute paths) and half relative would be read
    against two different directories.
    """
    directory = Path(configuration.output_directory.path).absolute()
    period = configuration.simulation_period
    metadata = directory / _METADATA_FILENAME if configuration.file_v1 is not None else None
    return RunResult(
        output_directory=directory,
        rasters=_raster_members(configuration, directory),
        time_series=_time_series_tables(configuration, directory),
        metadata=metadata,
        first_step=period.first_step,
        last_step=period.last_step,
        elapsed_seconds=elapsed_seconds,
    )


def _raster_members(
    configuration: "ModelConfiguration", directory: Path
) -> dict[str, tuple[Path, ...]]:
    """The raster members of every enabled variable, per enabled format."""
    formats = configuration.output_variables.file_formats
    period = configuration.simulation_period
    steps = range(period.first_step, period.last_step + 1)
    members = {}
    for variable in configuration.output_variables.get_enabled_raster_series():
        paths = []
        if OutputFileFormat.PCRASTER in formats:
            paths.extend(
                Path(get_raster_series_filepath(directory, variable.raster_filename_prefix, step))
                for step in steps
            )
        if OutputFileFormat.GEOTIFF in formats:
            paths.extend(
                directory / output_raster_filename(variable.raster_filename_prefix, step, "tif")
                for step in steps
            )
        members[variable.id] = tuple(paths)
    return members


def _time_series_tables(
    configuration: "ModelConfiguration", directory: Path
) -> dict[str, tuple[Path, ...]]:
    """The time series tables of every enabled variable, per enabled format."""
    if not _writes_time_series(configuration):
        return {}
    formats = configuration.output_variables.time_series_formats
    tables = {}
    for variable in configuration.output_variables.get_enabled_time_series():
        paths = []
        if TimeSeriesFileFormat.CSV in formats:
            paths.append(directory / f"{variable.table_filename_prefix}.csv")
        # The run writes a TSS file for every enabled time series and converts
        # it to CSV afterwards, removing the source unless the TSS format is
        # enabled as well; with the CSV format disabled nothing is converted.
        if TimeSeriesFileFormat.CSV not in formats or TimeSeriesFileFormat.PCRASTER_TSS in formats:
            paths.append(directory / f"{variable.table_filename_prefix}.tss")
        tables[variable.id] = tuple(paths)
    return tables


def _writes_time_series(configuration: "ModelConfiguration") -> bool:
    """Whether the run writes time series at all.

    The same condition the model itself applies: the time series must be
    enabled and the raster their aggregation reads must be configured.
    """
    variables = configuration.output_variables
    if not variables.tss:
        return False
    if variables.aggregation == "zones":
        return bool(configuration.raster_files.zones)
    return bool(configuration.raster_files.sample_locations)


def _result_to_json(result: RunResult) -> dict[str, Any]:
    """Return ``result`` as a JSON-able dictionary, with the paths as strings."""
    return {
        "output_directory": str(result.output_directory),
        "rasters": {
            variable: [str(path) for path in paths] for variable, paths in result.rasters.items()
        },
        "time_series": {
            variable: [str(path) for path in paths]
            for variable, paths in result.time_series.items()
        },
        "metadata": None if result.metadata is None else str(result.metadata),
        "first_step": result.first_step,
        "last_step": result.last_step,
        "elapsed_seconds": result.elapsed_seconds,
    }


def _result_from_json(document: dict[str, Any]) -> RunResult:
    """Rebuild a :class:`RunResult` from the dictionary of :func:`_result_to_json`."""
    metadata = document["metadata"]
    return RunResult(
        output_directory=Path(document["output_directory"]),
        rasters={
            variable: tuple(Path(path) for path in paths)
            for variable, paths in document["rasters"].items()
        },
        time_series={
            variable: tuple(Path(path) for path in paths)
            for variable, paths in document["time_series"].items()
        },
        metadata=None if metadata is None else Path(metadata),
        first_step=int(document["first_step"]),
        last_step=int(document["last_step"]),
        elapsed_seconds=float(document["elapsed_seconds"]),
    )
