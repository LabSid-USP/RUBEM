# coding=utf-8
# RUBEM RUBEM is a distributed hydrological model to calculate monthly
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

__author__ = "LabSid PHA EPUSP"
__email__ = "rubem.hydrological@labsid.eng.br"
__copyright__ = "Copyright 2020-2021, LabSid PHA EPUSP"
__license__ = "GPL"
__date__ = "2021-05-19"
__version__ = "0.1.0"

from os import remove
from os.path import splitext, join
from glob import glob
from pandas import read_csv


def tif2map(path):
    """[summary]

    :param path: [description]
    :type path: [type]
    """
    pass


def tss2csv(tssPath):
    """[summary]

    :param path: [description]
    :type path: [type]
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
        df.to_csv(csvFileName, sep=",", header=None)

    # Remove tss files
    eraseFiles(tssFileList)


def eraseFiles(fileList):
    """[summary]

    :param fileList: [description]
    :type fileList: [type]
    """
    # Iterate over file list to remove each tss file
    for file in fileList:
        remove(file)
