import py
import pytest
from rubem.configuration.output_format import OutputFileFormat

from rubem.configuration.output_variables import OutputVariables


class TestOutputVariables:

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "itp, bfw, srn, eta, lfw, rec, smc, rnf, tss, output_format",
        [
            (True, True, True, True, True, True, True, True, True, OutputFileFormat.PCRASTER),
            (True, True, True, True, True, True, True, True, True, OutputFileFormat.GEOTIFF),
            (
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                OutputFileFormat.PCRASTER,
            ),
            (
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                OutputFileFormat.GEOTIFF,
            ),
        ],
    )
    def test_output_variables_constructor(
        self, itp, bfw, srn, eta, lfw, rec, smc, rnf, tss, output_format
    ):
        _ = OutputVariables(
            itp=itp,
            bfw=bfw,
            srn=srn,
            eta=eta,
            lfw=lfw,
            rec=rec,
            smc=smc,
            rnf=rnf,
            tss=tss,
            output_formats=output_format,
        )
