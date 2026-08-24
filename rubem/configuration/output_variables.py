import warnings
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from ..configuration.output_format import OutputFileFormat

NO_DATA_VALUE_DEFAULT = -9999

VARIABLE_IDS = ("itp", "bfw", "srn", "eta", "lfw", "rec", "smc", "rnf", "arn")

_LABELS = {
    "itp": "Total Interception (ITP)",
    "bfw": "Baseflow (BFW)",
    "srn": "Surface Runoff (SRN)",
    "eta": "Actual Evapotranspiration (ETA)",
    "lfw": "Lateral Flow (LFW)",
    "rec": "Recharge (REC)",
    "smc": "Soil Moisture Content (SMC)",
    "rnf": "Total Runoff (RNF)",
    "arn": "Accumulated Total Runoff (ARN)",
}


class OutputVariable(BaseModel):
    """One output variable of the model and what the run writes for it.

    :param id: Short identifier (``itp``, ``bfw``, ...).
    :param is_raster_series_enabled: Whether the raster series is written.
    :param is_time_series_enabled: Whether the time series at the sample locations is written.
    :param raster_filename_prefix: Prefix of the raster series files.
    :param table_filename_prefix: Prefix of the time series file.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    is_raster_series_enabled: bool
    is_time_series_enabled: bool
    raster_filename_prefix: str
    table_filename_prefix: str

    def get(self, key: str, default: Any = None) -> Any:
        """Deprecated dictionary-style access kept for one minor release."""
        warnings.warn(
            "OutputVariable.get() is deprecated; read the attribute instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(self, key, default)


class OutputVariables(BaseModel):
    """
    Represents the output variables configuration.

    Each variable flag enables its raster series; the time series of a variable
    is written when the variable and ``tss`` are both enabled.

    :param itp: Enable or disable Total Interception (ITP). Defaults to `False`.
    :type itp: bool, optional

    :param bfw: Enable or disable Baseflow (BFW). Defaults to `False`.
    :type bfw: bool, optional

    :param srn: Enable or disable Surface Runoff (SRN). Defaults to `False`.
    :type srn: bool, optional

    :param eta: Enable or disable Actual Evapotranspiration (ETA). Defaults to `False`.
    :type eta: bool, optional

    :param lfw: Enable or disable Lateral Flow (LFW). Defaults to `False`.
    :type lfw: bool, optional

    :param rec: Enable or disable Recharge (REC). Defaults to `False`.
    :type rec: bool, optional

    :param smc: Enable or disable Soil Moisture Content (SMC). Defaults to `False`.
    :type smc: bool, optional

    :param rnf: Enable or disable Total Runoff (RNF). Defaults to `False`.
    :type rnf: bool, optional

    :param arn: Enable or disable Accumulated Total Runoff (ARN). Defaults to `False`.
    :type arn: bool, optional

    :param tss: Enable or disable Create time output time series (TSS). Defaults to `False`.
    :type tss: bool, optional

    :param output_formats: The output file formats. Defaults to ``OutputFileFormat.PCRASTER``.
    :type output_formats: OutputFileFormat, optional

    :param no_data_value: No-data value written to the GeoTIFF raster series. Defaults to ``-9999``.
    :type no_data_value: float, optional
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    itp: OutputVariable
    bfw: OutputVariable
    srn: OutputVariable
    eta: OutputVariable
    lfw: OutputVariable
    rec: OutputVariable
    smc: OutputVariable
    rnf: OutputVariable
    arn: OutputVariable
    tss: bool = False
    output_formats: OutputFileFormat = OutputFileFormat.PCRASTER
    no_data_value: float = NO_DATA_VALUE_DEFAULT

    @model_validator(mode="before")
    @classmethod
    def _expand_flags(cls, data: Any) -> Any:
        """Turn the boolean flags of the constructor into variable objects."""
        if not isinstance(data, dict):
            return data
        expanded = dict(data)
        tss = bool(expanded.get("tss", False))
        for variable_id in VARIABLE_IDS:
            value = expanded.get(variable_id, False)
            if isinstance(value, (OutputVariable, dict)):
                continue
            enabled = bool(value)
            expanded[variable_id] = OutputVariable(
                id=variable_id,
                is_raster_series_enabled=enabled,
                is_time_series_enabled=tss and enabled,
                raster_filename_prefix=variable_id,
                table_filename_prefix=f"tss_{variable_id}",
            )
        return expanded

    @property
    def file_formats(self) -> OutputFileFormat:
        """The output file formats (alias of ``output_formats``)."""
        return self.output_formats

    @property
    def variables(self) -> tuple[OutputVariable, ...]:
        """The nine output variables, in the documented order."""
        return tuple(getattr(self, variable_id) for variable_id in VARIABLE_IDS)

    def get_enabled_raster_series(self) -> list[OutputVariable]:
        """
        Returns a list of enabled raster series.

        :return: A list of enabled raster series.
        :rtype: list
        """
        return [v for v in self.variables if v.is_raster_series_enabled]

    def get_enabled_time_series(self) -> list[OutputVariable]:
        """
        Returns a list of enabled time series.

        :return: A list of enabled time series.
        :rtype: list
        """
        return [v for v in self.variables if v.is_time_series_enabled]

    def any_enabled(self) -> bool:
        """
        Returns ``True`` if any output variable is enabled, otherwise ``False``.

        :return: ``True`` if any output variable is enabled, otherwise ``False``.
        :rtype: bool
        """
        return any(v.is_raster_series_enabled for v in self.variables)

    def all_enabled(self) -> bool:
        """
        Returns ``True`` if all output variables are enabled, otherwise ``False``.

        :return: ``True`` if all output variables are enabled, otherwise ``False``.
        :rtype: bool
        """
        return all(v.is_raster_series_enabled for v in self.variables)

    def __str__(self) -> str:
        lines = [
            f"{_LABELS[v.id]}: {'Enabled' if v.is_raster_series_enabled else 'Disabled'}"
            for v in self.variables
        ]
        lines.append(
            f"Create time output time series (TSS): {'Enabled' if self.tss else 'Disabled'}"
        )
        lines.append(f"Output format: {self.output_formats}")
        return "\n".join(lines)
