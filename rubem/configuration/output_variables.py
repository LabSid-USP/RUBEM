import logging

from rubem.configuration.output_format import OutputFileFormat


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

    :param rnf: Enable or disable Accumulated Total Runoff (RNF). Defaults to `False`.
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
        tss: bool = False,
        output_format: OutputFileFormat = OutputFileFormat.PCRASTER,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.itp = itp
        self.bfw = bfw
        self.srn = srn
        self.eta = eta
        self.lfw = lfw
        self.rec = rec
        self.smc = smc
        self.rnf = rnf
        self.tss = tss
        self.file_format = output_format

        if (
            not self.itp
            and not self.bfw
            and not self.srn
            and not self.eta
            and not self.lfw
            and not self.rec
            and not self.smc
            and not self.rnf
        ):
            self.logger.warning("No output variables selected.")

    def __str__(self) -> str:
        return (
            f"Total Interception (ITP): {'Enabled' if self.itp else 'Disabled'}\n"
            f"Baseflow (BFW): {'Enabled' if self.bfw else 'Disabled'}\n"
            f"Surface Runoff (SRN): {'Enabled' if self.srn else 'Disabled'}\n"
            f"Actual Evapotranspiration (ETA): {'Enabled' if self.eta else 'Disabled'}\n"
            f"Lateral Flow (LFW): {'Enabled' if self.lfw else 'Disabled'}\n"
            f"Recharge (REC): {'Enabled' if self.rec else 'Disabled'}\n"
            f"Soil Moisture Content (SMC): {'Enabled' if self.smc else 'Disabled'}\n"
            f"Accumulated Total Runoff (RNF): {'Enabled' if self.rnf else 'Disabled'}\n"
            f"Create time output time series (TSS): {'Enabled' if self.tss else 'Disabled'}\n"
            f"Output format: {self.file_format}"
        )
