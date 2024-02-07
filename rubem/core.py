import time
import logging

from pcraster.framework import DynamicFramework

from rubem._dynamic_model import RUBEM
from rubem.configuration.model_configuration import ModelConfiguration
from rubem.file._file_convertions import tss2csv


class Model:
    """Initialize the ``DynamicFrameworkWrapper`` class

    Wrapper for the ``DynamicFramework`` that runs the ``DynamicModelConcept`` of the Rainfall rUnoff Balance Enhanced Model.

    :param model_configuration: The configuration object for the model.
    :type model_configuration: ModelConfiguration

    :raises ValueError: If the model configuration is empty.
    """

    def __init__(self, model_configuration: ModelConfiguration) -> None:
        self.logger = logging.getLogger(__name__)
        print("Setting up dynamic framework...")
        if not model_configuration:
            self.logger.error("Empty model configuration")
            raise ValueError("Empty model configuration")

        self.config = model_configuration

        self.logger.info("Setting up model...")
        self.dynamic_model_concept = RUBEM(self.config)

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
        print("Running simulation...")
        t0 = time.time()
        self.logger.info(
            "Started model run for %s cycles...", self.config.simulation_period.total_steps
        )

        try:
            self.dynamic_model.run()
            self.logger.info("Simulation finished!")
        except RuntimeError as e:
            self.logger.error("Simulation failed with error: %s", e)
            raise
        finally:
            exec_time = time.time() - t0
            self.logger.info("Elapsed time: %.2fs", exec_time)
            self.__exportTablesAsCSV()

    @classmethod
    def load(cls, data):
        """
        Load the model configuration.

        :param data: The model configuration data.
        :type data: Any

        :return: The loaded Model object.
        :rtype: rubem.configuration.model_configuration.ModelConfiguration

        :raises ValueError: If the model configuration format is unsupported.
        """
        if isinstance(data, ModelConfiguration):
            return cls(data)
        else:
            raise ValueError("Unsupported model configuration format", type(data))

    def __exportTablesAsCSV(self) -> None:
        """
        Converts PCRaster TSS files to Comma-Separated Values (CSV) files.

        :raises RuntimeError: If the export of time series files is not enabled.
        """
        if self.config.output_variables.tss:
            self.logger.info("Exporting tables as CSV...")
            cols = [str(n) for n in self.dynamic_model_concept.sample_vals[1:]]
            tss2csv(self.config.output_directory.path, cols)
        else:
            self.logger.error("Export of time series files not enabled")
            raise RuntimeError("Generation of time series must be activated")
