import json
import os
from pathlib import Path
from typing import Any

from .._paths import PathInput, as_path


class AppSettings:
    """
    A class representing the application settings.

    This class is implemented as a singleton, meaning that only one instance of it can exist.
    It loads the application settings from a JSON file and provides methods to access specific settings.
    """

    __instance = None
    __default_appsettings_dir = Path(__file__).parent.parent
    __default_appsettings_file = str((__default_appsettings_dir / "appsettings.json").absolute())

    if "PYTHON_ENVIRONMENT" in os.environ and os.environ["PYTHON_ENVIRONMENT"]:
        custom_env_settings = f"appsettings.{os.environ['PYTHON_ENVIRONMENT']}.json"
        for candidate_dir in (__default_appsettings_dir, Path.cwd()):
            custom_env_settings_path = str((candidate_dir / custom_env_settings).absolute())
            if (
                Path(custom_env_settings_path).is_file()
                and Path(custom_env_settings_path).stat().st_size > 0
            ):
                __default_appsettings_file = custom_env_settings_path
                break

    def __new__(cls):
        """
        Create a new instance of the `AppSettings` class if it doesn't already exist.

        :return: The instance of the `AppSettings` class.
        :rtype: AppSettings
        """
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
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

    def load(self, app_settings_file_path: PathInput | None = None) -> None:
        """
        Load the specified application settings or from the default appsettings.json file.

        :param app_settings_file_path: The path to the appsettings.json file. Defaults to None.
        :type app_settings_file_path: Optional[Union[str, bytes, os.PathLike]], optional

        :raises FileNotFoundError: If the application settings file is not found.
        """

        if app_settings_file_path:
            app_settings_file_path_str = str(as_path(app_settings_file_path).absolute())
        else:
            app_settings_file_path_str = self.__default_appsettings_file

        settings_path = Path(app_settings_file_path_str)
        if not settings_path.exists() or not settings_path.is_file():
            raise FileNotFoundError(
                f"Application settings file not found: {app_settings_file_path_str}"
            )

        with settings_path.open(encoding="utf8") as file:
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
