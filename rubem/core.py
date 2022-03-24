# coding=utf-8
# RUBEM is a distributed hydrological model to calculate monthly
# flows with changes in land use over time.
# Copyright (C) 2020-2022 LabSid PHA EPUSP

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Contact: hydrological@labsid.eng.br

"""Rainfall rUnoff Balance Enhanced Model (RUBEM) API"""

import os
import time
import logging
from configparser import ConfigParser

from pcraster.framework import DynamicFramework

try:
    from _dynamic_model import RUBEM
    from date._date_calc import totalSteps
    from file._file_convertions import tss2csv
    from validation import _validators
except ImportError:
    from ._dynamic_model import RUBEM
    from .date._date_calc import totalSteps
    from .file._file_convertions import tss2csv
    from .validation import _validators


logger = logging.getLogger(__name__)


class Model:
    """Distributed Hydrological Model for transforming
    precipitation into surface and subsurface runoff"""

    def __init__(self, modelConfig: ConfigParser) -> None:
        """Initialise a new Model instance

        :param modelConfig: Configuration parser object
        :type modelConfig: ConfigParser
        :raises TypeError: The class constructor did not take an\
            argument of the expected type
        :raises SystemExit: The class constructor was unable to\
            validate the given settings
        """

        if not isinstance(modelConfig, ConfigParser):
            raise TypeError(
                "The model constructor expected an argument type like"
                f" ConfigParser, but got {type(modelConfig)}"
            )

        self.__validateModelConfig(modelConfig)
        self.config = modelConfig

        startDate = self.config.get("SIM_TIME", "start")
        endDate = self.config.get("SIM_TIME", "end")
        self.start, self.end, self.steps = totalSteps(startDate, endDate)

        self.__setup()

    def __validateModelConfig(self, modelConfig) -> None:
        """Validation of the configuration parser object

        :param modelConfig: Configuration parser object
        :type modelConfig: ConfigParser
        """

        _validators.schemaValidator(modelConfig)
        _validators.dateValidator(modelConfig)
        _validators.directoryPathValidator(modelConfig)
        _validators.fileNamePrefixValidator(modelConfig)
        _validators.filePathValidator(modelConfig)
        _validators.floatTypeValidator(modelConfig)
        _validators.booleanTypeValidator(modelConfig)
        _validators.value_range_validator(modelConfig)
        _validators.domain_validator(modelConfig)

    def __setup(self) -> None:
        """Perform model initialization procedures"""
        # Store which variables have or have not been selected for export
        genFilesList = ["itp", "bfw", "srn", "eta", "lfw", "rec", "smc", "rnf"]
        genFilesDic = {}
        for file in genFilesList:
            genFilesDic[file] = self.config.getboolean("GENERATE_FILE", file)

        self.model = RUBEM(self.config)

        self.dynamicModel = DynamicFramework(
            self.model, lastTimeStep=self.end, firstTimestep=self.start
        )

    def run(self) -> None:
        """Run the model"""
        t1 = time.time()
        logger.info("Started model run...")

        if logger.isEnabledFor(logging.DEBUG):
            self.dynamicModel.setDebug(True)
            self.dynamicModel.setQuiet(False)
        else:
            self.dynamicModel.setDebug(False)
            self.dynamicModel.setQuiet(True)

        try:
            self.dynamicModel.run()
        except RuntimeError as e:
            logger.info("Model run failed!")
            raise SystemExit(1) from e
        else:
            execTime = time.time() - t1
            logger.info(f"Elapsed time: {execTime:.2f}s")
            logger.info("Model run finished")
            self.__exportTablesAsCSV()

    @classmethod
    def load(cls, data):
        """Load an existing model

        :param data: A file-like object to read INI data from, path\
            to a filename to read, or a parsed dict
        :type data: file-like, str, dict
        :raises Exception: Unsupported model configuration format
        """
        if isinstance(data, (str, bytes, os.PathLike)):
            return cls.__loadFromConfigFile(data)
        elif isinstance(data, dict):
            return cls.__loadFromDict(data)
        else:
            raise Exception(
                "Unsupported model configuration format", type(data)
            )

    @classmethod
    def __loadFromConfigFile(cls, filePath):
        """Load data from a INI file"""
        if os.path.exists(filePath):
            modelConfig = ConfigParser()
            modelConfig.read(filePath)
            return cls(modelConfig)
        else:
            raise FileNotFoundError(filePath)

    @classmethod
    def __loadFromDict(cls, dataDict):
        """Load data from a dictionary"""
        if dataDict:
            modelConfig = ConfigParser()
            modelConfig.read_dict(dataDict)
            return cls(modelConfig)
        else:
            raise ValueError("Empty model configuration dictionay")

    def __exportTablesAsCSV(self) -> None:
        """Converts PCRaster TSS files to Comma-Separated Values (CSV) files

        :raises RuntimeError: Export of time series files not enabled
        """
        # Check whether the generation of time series has been activated
        if self.config.getboolean("GENERATE_FILE", "tss"):
            logger.info("Exporting tables as CSV...")
            cols = [str(n) for n in self.model.sample_vals[1:]]
            # Convert generated time series to .csv format and
            # removes .tss files
            tss2csv(self.config.get("DIRECTORIES", "output"), cols)
        else:
            raise RuntimeError("Generation of time series must be activated")
