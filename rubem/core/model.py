import os
import time
import logging
from configparser import ConfigParser

from pcraster.framework import DynamicFramework

try:
    from core._dynamic_model import RUBEM
    from utilities._date_calc import totalSteps
    from utilities._file_convertions import tss2csv
    from validation._exception_validation import ValidationException
    from validation._validators import (
        filePathValidator,
        fileNamePrefixValidator,
        floatTypeValidator,
        booleanTypeValidator,
        dateValidator,
        directoryPathValidator,
        schemaValidator,
    )
except ImportError:
    from ..core._dynamic_model import RUBEM
    from ..utilities._date_calc import totalSteps
    from ..utilities._file_convertions import tss2csv
    from ..validation._exception_validation import ValidationException
    from ..validation._validators import (
        filePathValidator,
        fileNamePrefixValidator,
        floatTypeValidator,
        booleanTypeValidator,
        dateValidator,
        directoryPathValidator,
        schemaValidator,
    )

logger = logging.getLogger(__name__)


class Model:
    def __init__(self, modelConfig: ConfigParser):

        try:
            self.__validateModelConfig(modelConfig)
        except Exception as e:
            raise SystemExit(1) from e
        else:
            self.config = modelConfig

        startDate = self.config.get("SIM_TIME", "start")
        endDate = self.config.get("SIM_TIME", "end")
        self.start, self.end, self.steps = totalSteps(startDate, endDate)

        self.__setup()

    def __validateModelConfig(self, modelConfig):
        if not modelConfig:
            raise ValidationException("Model configuration file cannot be null")
        elif not isinstance(modelConfig, ConfigParser):
            raise ValidationException(
                "Model configuration file must be an instance of ConfigParser"
            )
        schemaValidator(modelConfig)
        dateValidator(modelConfig)
        directoryPathValidator(modelConfig)
        fileNamePrefixValidator(modelConfig)
        filePathValidator(modelConfig)
        floatTypeValidator(modelConfig)
        booleanTypeValidator(modelConfig)

    def __setup(self):
        # Store which variables have or have not been selected for export
        genFilesList = ["itp", "bfw", "srn", "eta", "lfw", "rec", "smc", "rnf"]
        genFilesDic = {}
        for file in genFilesList:
            genFilesDic[file] = self.config.getboolean("GENERATE_FILE", file)

        self.model = RUBEM(self.config)

        self.dynamicModel = DynamicFramework(
            self.model, lastTimeStep=self.end, firstTimestep=self.start
        )

    def run(self):

        t1 = time.time()
        logger.info("Started")

        if logger.isEnabledFor(logging.DEBUG):
            self.dynamicModel.setDebug(True)
            self.dynamicModel.setQuiet(False)
        else:
            self.dynamicModel.setDebug(False)
            self.dynamicModel.setQuiet(True)

        try:
            self.dynamicModel.run()
        except RuntimeError as e:
            logger.info("Failed")
            raise SystemExit(1) from e
        else:
            execTime = time.time() - t1
            logger.info(f"Elapsed time: {execTime:.2f}s")
            logger.info("Finished")

    @classmethod
    def load(cls, data):
        if isinstance(data, (str, bytes, os.PathLike)):
            return cls.__loadFromConfigFile(data)
        elif isinstance(data, dict):
            return cls.__loadFromDict(data)
        else:
            raise Exception("Unsupported model configuration format", type(data))

    @classmethod
    def __loadFromConfigFile(cls, filePath):
        if os.path.exists(filePath):
            modelConfig = ConfigParser()
            modelConfig.read(filePath)
            return cls(modelConfig)
        else:
            raise FileNotFoundError(filePath)

    @classmethod
    def __loadFromDict(cls, dataDict):
        if dataDict:
            modelConfig = ConfigParser()
            modelConfig.read_dict(dataDict)
            return cls(modelConfig)
        else:
            raise ValueError("Empty model configuration dictionay")

    def exportTablesAsCSV(self):
        # Check whether the generation of time series has been activated
        if self.config.getboolean("GENERATE_FILE", "tss"):
            logger.info("Exporting tables as CSV...")
            cols = [str(n) for n in self.model.sample_vals[1:]]
            # Convert generated time series to .csv format and removes .tss files
            tss2csv(self.config.get("DIRECTORIES", "output"), cols)
        else:
            raise RuntimeError("Generation of time series must be activated")
