import logging

from rubem.configuration.output_format import OutputFileFormat


class OutputVariables:
    """
    Represents the output variables configuration.

    :param itp: Enable or disable Total Interception (ITP).
    :param bfw: Enable or disable Baseflow (BFW).
    :param srn: Enable or disable Surface Runoff (SRN).
    :param eta: Enable or disable Actual Evapotranspiration (ETA).
    :param lfw: Enable or disable Lateral Flow (LFW).
    :param rec: Enable or disable Recharge (REC).
    :param smc: Enable or disable Soil Moisture Content (SMC).
    :param rnf: Enable or disable Total Runoff (RNF).
    :param tss: Enable or disable Create time output time series (TSS).
    :param output_format: The output file format.
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
        output_format: OutputFileFormat = OutputFileFormat.PCRaster,
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
            f"Total Runoff (RNF): {'Enabled' if self.rnf else 'Disabled'}\n"
            f"Create time output time series (TSS): {'Enabled' if self.tss else 'Disabled'}\n"
            f"Output format: {self.file_format}"
        )
