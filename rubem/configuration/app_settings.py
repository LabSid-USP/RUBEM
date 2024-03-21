import json
import os
from typing import Any, Optional, Union


class AppSettings:
    """
    A class representing the application settings.

    This class is implemented as a singleton, meaning that only one instance of it can exist.
    It loads the application settings from a JSON file and provides methods to access specific settings.
    """

    __instance = None
    __default_appsettings_dir = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
    __default_appsettings_file = os.path.abspath(
        os.path.join(__default_appsettings_dir, "appsettings.json")
    )

    if "PYTHON_ENVIRONMENT" in os.environ and os.environ["PYTHON_ENVIRONMENT"]:
        custom_env_settings = f"appsettings.{os.environ['PYTHON_ENVIRONMENT']}.json"
        custom_env_settings_path = os.path.abspath(
            os.path.join(__default_appsettings_dir, custom_env_settings)
        )
        if (
            os.path.isfile(custom_env_settings_path)
            and os.path.getsize(custom_env_settings_path) > 0
        ):
            __default_appsettings_file = custom_env_settings_path

    def __new__(cls):
        """
        Create a new instance of the `AppSettings` class if it doesn't already exist.

        :return: The instance of the `AppSettings` class.
        :rtype: AppSettings
        """
        if cls.__instance is None:
            cls.__instance = super(AppSettings, cls).__new__(cls)
            cls.__instance.__initialized = False
        return cls.__instance

    def __init__(self):
        """
        Initialize the `AppSettings` instance.

        This method is called when the instance is created. It loads the application settings.
        """
        if self.__initialized:  # pylint: disable=access-member-before-definition
            return
        self.__initialized = True
        self.load()

    def load(self, app_settings_file_path: Optional[Union[str, bytes, os.PathLike]] = None) -> None:
        """
        Load the specified application settings or from the default appsettings.json file.

        :param app_settings_file_path: The path to the appsettings.json file. Defaults to None.
        :type app_settings_file_path: Optional[Union[str, bytes, os.PathLike]], optional

        :raises FileNotFoundError: If the application settings file is not found.
        """

        if app_settings_file_path:
            app_settings_file_path_str = os.path.abspath(app_settings_file_path)
        else:
            app_settings_file_path_str = self.__default_appsettings_file

        if not os.path.exists(app_settings_file_path_str) or not os.path.isfile(
            app_settings_file_path_str
        ):
            raise FileNotFoundError(
                f"Application settings file not found: {app_settings_file_path_str}"
            )

        with open(app_settings_file_path_str, "r", encoding="utf8") as file:
            self.settings = json.load(file)

    def get_setting(self, key: str) -> Any:
        """
        Get the value of a specific setting.

        :param key: The key of the setting to retrieve.
        :type key: str

        :return: The value of the setting, or None if the setting doesn't exist.
        :rtype: Any
        """
        return self.settings.get(key)
