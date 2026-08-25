from enum import Flag, auto


class OutputFileFormat(Flag):
    """
    Enum class representing the output file format options.
    """

    PCRASTER = auto()
    GEOTIFF = auto()


class TimeSeriesFileFormat(Flag):
    """
    Enum class representing the time series file format options.
    """

    CSV = auto()
    PCRASTER_TSS = auto()
