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
            time.sleep(0.42)


def parentDirUpdate(template, tags, target, dirs):
    with open(template, "r") as inputFile:
        content = inputFile.read()
        for tag, dir in zip(tags, dirs):
            content = content.replace(tag, dir)
    with open(target, "w") as outputFile:
        outputFile.write(content)


def areIdendicalFiles(filePath1, filePath2):
    if os.path.getsize(filePath1) == os.path.getsize(filePath2):
        if open(filePath1, "r").read() == open(filePath2, "r").read():
            return True
    return False
