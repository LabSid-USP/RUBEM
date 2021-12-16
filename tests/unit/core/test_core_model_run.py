import os
import unittest

from tests.utils import parentDirUpdate, removeFile, removeDirectory
from rubem.core import Model


class ModelRunTest(unittest.TestCase):
    """Test model run method"""

    def setUp(self):
        """Runs before each test."""

        self.currentDir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        )
        self.templateBaseProject = os.path.join(
            self.currentDir, "fixtures/base2.template"
        )
        self.baseProjectFile = os.path.join(self.currentDir, "fixtures/base2.ini")
        if not os.path.exists(self.baseProjectFile):
            parentDirUpdate(
                template=self.templateBaseProject,
                tag="{PARENT_DIR}",
                target=self.baseProjectFile,
                currentDir=self.currentDir,
            )

        self.baseProjectOutputDir = os.path.join(self.currentDir, "fixtures/base/out2")
        if not os.path.exists(self.baseProjectOutputDir):
            os.mkdir(self.baseProjectOutputDir)

    def tearDown(self):
        """Runs after each test."""
        removeFile(self.baseProjectFile)
        removeDirectory(self.baseProjectOutputDir)

    def test_run_config_ini_file(self):
        """Test we can run a model from a configuration file"""
        model = Model.load(self.baseProjectFile)
        model.run()
        self.assertCountEqual(
            os.listdir(self.baseProjectOutputDir),
            [
                "bfw00000.001",
                "bfw00000.002",
                "bfw0000001.tif",
                "bfw0000002.tif",
                "eta00000.001",
                "eta00000.002",
                "eta0000001.tif",
                "eta0000002.tif",
                "itp00000.001",
                "itp00000.002",
                "itp0000001.tif",
                "itp0000002.tif",
                "lfw00000.001",
                "lfw00000.002",
                "lfw0000001.tif",
                "lfw0000002.tif",
                "rec00000.001",
                "rec00000.002",
                "rec0000001.tif",
                "rec0000002.tif",
                "rnf00000.001",
                "rnf00000.002",
                "rnf0000001.tif",
                "rnf0000002.tif",
                "smc00000.001",
                "smc00000.002",
                "smc0000001.tif",
                "smc0000002.tif",
                "srn00000.001",
                "srn00000.002",
                "srn0000001.tif",
                "srn0000002.tif",
                "tss_bfw.csv",
                "tss_eta.csv",
                "tss_itp.csv",
                "tss_lfw.csv",
                "tss_rec.csv",
                "tss_rnf.csv",
                "tss_smc.csv",
                "tss_srn.csv",
            ],
        )


if __name__ == "__main__":
    suite = unittest.makeSuite(ModelRunTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
