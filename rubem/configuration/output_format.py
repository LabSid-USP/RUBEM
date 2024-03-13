from enum import Flag, auto


class OutputFileFormat(Flag):
    """
    Enum class representing the output file format options.
    """

    PCRASTER = auto()
    GEOTIFF = auto()
