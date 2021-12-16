# coding=utf-8
# RUBEM is a distributed hydrological model to calculate monthly
# flows with changes in land use over time.
# Copyright (C) 2020-2021 LabSid PHA EPUSP

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
# Contact: rubem.hydrological@labsid.eng.br

"""Common file conversion functionality used by RUBEM"""

from glob import glob
import logging
from os import remove
from os.path import join, splitext

from pandas import read_csv

logger = logging.getLogger(__name__)


def tss2csv(tssPath, colNames):
    """Convert all PCRaster Time Series (*.tss) files present in the specified directory to (*.csv).

    :param tssPath: Directory containing the files.
    :type tssPath: str

    :param colNames: List of strings of aliases for the column names.
    :type colNames: list[str]
    """
    # Create a list with all files in this folder with matching extension
    tssFileList = glob(join(tssPath, "*.tss"))

    # Iterate over file list to convert each tss file in a csv file
    for tssFile in tssFileList:

        # Read tss file properly
        df = read_csv(tssFile, header=None, index_col=0, delim_whitespace=True)

        # Remove tss extension and add csv extension preserving the filename
        csvFileName = splitext(tssFile)[0] + ".csv"

        # Export csv file
        df.to_csv(csvFileName, sep=";", header=colNames)

    # Remove tss files
    eraseFiles(tssFileList)


def eraseFiles(fileList):
    """Delete files from a specified list.

    :param fileList: List of paths to files.
    :type fileList: List
    """
    # Iterate over file list to remove each tss file
    for file in fileList:
        remove(file)
