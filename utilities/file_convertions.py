# coding=utf-8
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
    tssFileList = glob(join(tssPath,'*.tss'))
    
    # Iterate over file list to convert each tss file in a csv file
    for tssFile in tssFileList:
        
        # Read tss file properly
        df = read_csv(tssFile, header=None, index_col=0, delim_whitespace=True)
        
        # Remove tss extension and add csv extension preserving the filename
        csvFileName = splitext(tssFile)[0] + '.csv'

        # Export csv file
        df.to_csv(csvFileName, sep=',', header=None)

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