import logging

from ..configuration.output_format import OutputFileFormat


class OutputVariables:
    """
    Represents the output variables configuration.

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

    :param rnf: Enable or disable Accumulated Total Runoff (ARN). Defaults to `False`.
    :type rnf: bool, optional

    :param tss: Enable or disable Create time output time series (TSS). Defaults to `False`.
    :type tss: bool, optional

    :param output_format: The output file format. Defaults to ``OutputFileFormat.PCRASTER``.
    :type output_format: OutputFileFormat, optional
    """

    def __init__(
        self,
        itp: bool = False,
        bfw: bool = False,
        srn: bool = False,
        eta: bool = False,
        lfw: bool = False,
        rec: bool = False,
        smc: bool = False,
        rnf: bool = False,
        arn: bool = False,
        tss: bool = False,
        output_format: OutputFileFormat = OutputFileFormat.PCRASTER,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.itp = {
            "id": "itp",
            "is_raster_series_enabled": itp,
            "is_time_series_enabled": tss,
            "raster_filename_prefix": "itp",
            "table_filename_prefix": "tss_itp",
        }
        self.bfw = {
            "id": "bfw",
            "is_raster_series_enabled": bfw,
            "is_time_series_enabled": tss,
            "raster_filename_prefix": "bfw",
            "table_filename_prefix": "tss_bfw",
        }
        self.srn = {
            "id": "srn",
            "is_raster_series_enabled": srn,
            "is_time_series_enabled": tss,
            "raster_filename_prefix": "srn",
            "table_filename_prefix": "tss_srn",
        }
        self.eta = {
            "id": "eta",
            "is_raster_series_enabled": eta,
            "is_time_series_enabled": tss,
            "raster_filename_prefix": "eta",
            "table_filename_prefix": "tss_eta",
        }
        self.lfw = {
            "id": "lfw",
            "is_raster_series_enabled": lfw,
            "is_time_series_enabled": tss,
            "raster_filename_prefix": "lfw",
            "table_filename_prefix": "tss_lfw",
        }
        self.rec = {
            "id": "rec",
            "is_raster_series_enabled": rec,
            "is_time_series_enabled": tss,
            "raster_filename_prefix": "rec",
            "table_filename_prefix": "tss_rec",
        }
        self.smc = {
            "id": "smc",
            "is_raster_series_enabled": smc,
            "is_time_series_enabled": tss,
            "raster_filename_prefix": "smc",
            "table_filename_prefix": "tss_smc",
        }
        self.rnf = {
            "id": "rnf",
            "is_raster_series_enabled": rnf,
            "is_time_series_enabled": tss,
            "raster_filename_prefix": "rnf",
            "table_filename_prefix": "tss_rnf",
        }
        self.arn = {
            "id": "arn",
            "is_raster_series_enabled": arn,
            "is_time_series_enabled": tss,
            "raster_filename_prefix": "arn",
            "table_filename_prefix": "tss_arn",
        }
        self.tss = tss
        self.file_format = output_format

    def get_enabled_raster_series(self) -> list:
        """
        Returns a list of enabled raster series.

        :return: A list of enabled raster series.
        :rtype: list
        """
        return [
            v
            for k, v in self.__dict__.items()
            if isinstance(v, dict) and v.get("is_raster_series_enabled")
        ]

    def get_enabled_time_series(self) -> list:
        """
        Returns a list of enabled time series.

        :return: A list of enabled time series.
        :rtype: list
        """
        return [
            v
            for k, v in self.__dict__.items()
            if isinstance(v, dict) and v.get("is_time_series_enabled")
        ]

    def any_enabled(self) -> bool:
        """
        Returns ``True`` if any output variable is enabled, otherwise ``False``.

        :return: ``True`` if any output variable is enabled, otherwise ``False``.
        :rtype: bool
        """
        return any(
            [
                self.itp.get("is_raster_series_enabled"),
                self.bfw.get("is_raster_series_enabled"),
                self.srn.get("is_raster_series_enabled"),
                self.eta.get("is_raster_series_enabled"),
                self.lfw.get("is_raster_series_enabled"),
                self.rec.get("is_raster_series_enabled"),
                self.smc.get("is_raster_series_enabled"),
                self.rnf.get("is_raster_series_enabled"),
                self.arn.get("is_raster_series_enabled"),
            ]
        )

    def all_enabled(self) -> bool:
        """
        Returns ``True`` if all output variables are enabled, otherwise ``False``.

        :return: ``True`` if all output variables are enabled, otherwise ``False``.
        :rtype: bool
        """
        return all(
            [
                self.itp.get("is_raster_series_enabled"),
                self.bfw.get("is_raster_series_enabled"),
                self.srn.get("is_raster_series_enabled"),
                self.eta.get("is_raster_series_enabled"),
                self.lfw.get("is_raster_series_enabled"),
                self.rec.get("is_raster_series_enabled"),
                self.smc.get("is_raster_series_enabled"),
                self.rnf.get("is_raster_series_enabled"),
                self.arn.get("is_raster_series_enabled"),
            ]
        )

    def __str__(self) -> str:
        return (
            f"Total Interception (ITP): {'Enabled' if self.itp else 'Disabled'}\n"
            f"Baseflow (BFW): {'Enabled' if self.bfw else 'Disabled'}\n"
            f"Surface Runoff (SRN): {'Enabled' if self.srn else 'Disabled'}\n"
            f"Actual Evapotranspiration (ETA): {'Enabled' if self.eta else 'Disabled'}\n"
            f"Lateral Flow (LFW): {'Enabled' if self.lfw else 'Disabled'}\n"
            f"Recharge (REC): {'Enabled' if self.rec else 'Disabled'}\n"
            f"Soil Moisture Content (SMC): {'Enabled' if self.smc else 'Disabled'}\n"
            f"Total Runoff (RNF): {'Enabled' if self.rnf else 'Disabled'}\n"
            f"Accumulated Total Runoff (ARN): {'Enabled' if self.rnf else 'Disabled'}\n"
            f"Create time output time series (TSS): {'Enabled' if self.tss else 'Disabled'}\n"
            f"Output format: {self.file_format}"
        )
