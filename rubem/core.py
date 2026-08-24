import logging
import os
import time

import humanize
from pcraster.framework import DynamicFramework

from ._dynamic_model import RainfallRunoffBalanceEnhancedModel
from .configuration.model_configuration import ModelConfiguration
from .file._file_convertions import tss2csv


class DynamicFrameworkWrapper:
    """Initialize the ``DynamicFrameworkWrapper`` class

    Wrapper for the ``DynamicFramework`` that runs the ``DynamicModelConcept`` of the Rainfall rUnoff Balance Enhanced Model.

    :param model_configuration: The configuration object for the model.
    :type model_configuration: ModelConfiguration

    :raises ValueError: If the model configuration is empty.
    """

    def __init__(self, model_configuration: ModelConfiguration) -> None:
        self.logger = logging.getLogger(__name__)
        if not model_configuration:
            self.logger.error("Empty model configuration")
            raise ValueError("Empty model configuration")

        self.config = model_configuration

        self.logger.info("Setting up model...")
        self.dynamic_model_concept = RainfallRunoffBalanceEnhancedModel(self.config)

        self.logger.info("Setting up dynamic model framework...")
        self.dynamic_model = DynamicFramework(
            userModel=self.dynamic_model_concept,
            firstTimestep=self.config.simulation_period.first_step,
            lastTimeStep=self.config.simulation_period.last_step,
        )

        if self.logger.isEnabledFor(logging.DEBUG):
            self.dynamic_model.setDebug(True)
            self.dynamic_model.setQuiet(False)
        else:
            self.dynamic_model.setDebug(False)
            self.dynamic_model.setQuiet(True)

    def run(self) -> None:
        """
        Wrapper of the ``DynamicFramework.run()`` that runs the ``DynamicModelConcept``.
        """
        t0 = time.time()
        self.logger.info(
            "Started model run for %s cycles...", self.config.simulation_period.total_steps
        )

        try:
            self.dynamic_model.run()
            self.logger.info("Simulation finished successfully!")
        except RuntimeError:
            self.logger.exception("Simulation failed.")
            raise
        finally:
            exec_time = time.time() - t0
            self.logger.info(
                "Elapsed time: %s",
                humanize.precisedelta(exec_time, minimum_unit="seconds"),
            )

        self.__export_tables_as_csv()

    @classmethod
    def load(cls, data):
        """
        Load the model configuration.

        :param data: The model configuration data.
        :type data: Any

        :return: The loaded Model object.
        :rtype: ..configuration.model_configuration.ModelConfiguration

        :raises ValueError: If the model configuration format is unsupported.
        """
        if isinstance(data, ModelConfiguration):
            return cls(data)
        else:
            raise ValueError("Unsupported model configuration format", type(data))

    def __export_tables_as_csv(self) -> None:
        """Converts PCRaster TSS files to Comma-Separated Values (CSV) files."""
        enabled_time_series = self.config.output_variables.get_enabled_time_series()
        if (
            self.config.raster_files.sample_locations
            and enabled_time_series
            and self.dynamic_model_concept.sample_vals is not None
        ):
            self.logger.info("Exporting tables as CSV...")
            cols = [str(n) for n in self.dynamic_model_concept.sample_vals[1:]]
            tss_files = [
                os.path.join(
                    self.config.output_directory.path,
                    f"{var.get('table_filename_prefix')}.tss",
                )
                for var in enabled_time_series
            ]
            missing = [f for f in tss_files if not os.path.isfile(f)]
            if missing:
                # The export also runs after a failed run, where a writer may
                # never have been reached: the ones that exist are still
                # converted, but the gap is named instead of being swallowed.
                self.logger.warning(
                    "%d enabled time series file(s) were not produced and cannot be converted: %s",
                    len(missing),
                    ", ".join(missing),
                )
            tss2csv([f for f in tss_files if f not in missing], cols)
        else:
            self.logger.warning(
                "Generation of time series was not configured to export time series files."
            )
