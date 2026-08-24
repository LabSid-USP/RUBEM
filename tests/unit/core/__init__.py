from rubem.configuration.app_settings import AppSettings
from rubem.configuration.data_ranges_settings import DataRangesSettings

DataRangesSettings(AppSettings().get_setting("value_ranges"))
