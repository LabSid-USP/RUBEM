import os

import pytest

from rubem.configuration.model_configuration import ModelConfiguration
from rubem.core import DynamicFrameworkWrapper
from tests.helpers.config import base_model_config


class TestInProcessRun:
    """Guard the guarantees a subprocess run cannot check.

    A child process hides any ``os.chdir`` the model performs: the change dies
    with the child while the outputs still land in the configured directory.
    Only an in-process run can prove that an embedding program keeps its
    working directory.
    """

    @pytest.mark.slow
    @pytest.mark.integration
    def test_run_leaves_the_caller_working_directory_untouched(self, tmp_path):
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        config = ModelConfiguration(base_model_config(str(output_dir)))

        before = os.getcwd()
        DynamicFrameworkWrapper(config).run()

        assert os.getcwd() == before
        assert (output_dir / "tss_itp.csv").is_file()
        assert (output_dir / "itp00000.001").is_file()
