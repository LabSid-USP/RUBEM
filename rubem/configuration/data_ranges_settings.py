import sys


class DataRangesSettings:
    """
    Class representing valid data ranges settings for input rasters and variables.

    This class is a singleton, meaning that only one instance of it can exist.
    It stores and manages the data ranges for rasters and variables.
    """

    __instance = None

    def __new__(cls, *args, **kwargs):
        """
        Create a new instance of the `DataRangesSettings` class if it doesn't already exist.

        :return: The instance of the `DataRangesSettings` class.
        :rtype: DataRangesSettings
        """
        if cls.__instance is None:
            cls.__instance = super(DataRangesSettings, cls).__new__(cls)
            cls.__instance.__initialized = False
        return cls.__instance

    def __init__(self, data=None):
        """
        Initialize the `DataRangesSettings` instance.


        :param data: The data containing the ranges for rasters and variables. Defaults to None.
        :type data: dict, optional

        :raises ValueError: If the data is missing.
        """
        if self.__initialized:  # pylint: disable=access-member-before-definition
            return
        self.__initialized = True

        if not data:
            raise ValueError("Missing data for data ranges settings.")

        self.__convert_infinities(data)
        self.rasters = self.__extract_subsection(data, "rasters")
        self.variables = self.__extract_subsection(data, "variables")

    def __extract_subsection(self, data, section_name):
        """
        Extract a subsection from the data.


        :param data: The data containing the subsection.
        :type data: dict
        :param section_name: The name of the subsection.
        :type section_name: str

        :return: The extracted subsection.
        :rtype: dict

        :raises ValueError: If the subsection is missing or if the min/max values are invalid.
        """
        if section_name not in data:
            raise ValueError(f"Missing '{section_name}' section")

        section_data = data[section_name]
        for key, value in section_data.items():
            if "min" not in value:
                raise ValueError(f"Missing 'min' value in '{section_name}.{key}'")
            if "max" not in value:
                raise ValueError(f"Missing 'max' value in '{section_name}.{key}'")
            if value["min"] >= value["max"]:
                raise ValueError(
                    f"'max' value must be greater than 'min' value in '{section_name}.{key}'"
                )

        return section_data

    def __convert_infinities(self, d: dict) -> None:
        """
        Convert `Infinity` and `-Infinity` values to `sys.float_info.max` and `-sys.float_info.max`, respectively.

        :param d: The dictionary to convert.
        :type d: dict

        .. note::
            An attempt was made to convert `Infinity` and `-Infinity` to `sys.float_info.max`
            and `-sys.float_info.max`, respectively, using `json.load` and `parse_constant`,
            but was unsuccessful. This was the alternative found.
        """
        for key, value in d.items():
            if isinstance(value, dict):
                self.__convert_infinities(value)
            elif value == "Infinity":
                d[key] = sys.float_info.max
            elif value == "-Infinity":
                d[key] = -sys.float_info.max
