import os

import pcraster.framework as pcrfw


class TimeoutputTimeseriesAdapter(pcrfw.TimeoutputTimeseries):
    """``TimeoutputTimeseries`` that accepts absolute output filenames.

    The base class asserts that its filename is relative because it writes to
    the process working directory. The model writes every output to the
    configured output directory instead, so this adapter overrides the
    private ``_configureOutputFilename`` hook to allow absolute paths while
    preserving the base behavior: the ``.tss`` extension is appended when
    missing, and stochastic runs still write into the current sample-number
    directory (placed between the directory and the filename).

    A stochastic framework creates its sample directories under the working
    directory, which is where the base class writes; a redirected output
    directory has no such directory, so this adapter creates the one it
    targets.
    """

    def _configureOutputFilename(self, filename):
        if not os.path.splitext(filename)[1]:
            filename += ".tss"

        if hasattr(self._userModel, "nrSamples"):
            directory, basename = os.path.split(filename)
            sample_directory = os.path.join(directory, str(self._userModel.currentSampleNumber()))
            if directory:
                os.makedirs(sample_directory, exist_ok=True)
            filename = os.path.join(sample_directory, basename)

        return filename
