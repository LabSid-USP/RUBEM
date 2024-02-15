from enum import Enum, auto


class OutputFileFormat(Enum):
    """
    Enum class representing the output file format options.
    """

    PCRASTER = auto()
    GEOTIFF = auto()
