import os
import time
import shutil


def removeFile(filePath):
    if os.path.exists(filePath):
        os.remove(filePath)


def removeDirectory(dirPath):
    if os.path.exists(dirPath):
        try:
            shutil.rmtree(dirPath)
        except OSError:
            time.sleep(0.5)


def parentDirUpdate(template, tag, target, currentDir):
    with open(template, "r") as inputFile:
        content = inputFile.read().replace(tag, currentDir)
    with open(target, "w") as outputFile:
        outputFile.write(content)
