import subprocess
import sys

import pytest

from rubem.cli import main
from tests.helpers.config import REPO_ROOT
from tests.helpers.synthetic import write_synthetic_dataset


class TestPreprocessCommand:
    @pytest.mark.unit
    def test_help_lists_the_tools(self, capsys, restore_logging):
        with pytest.raises(SystemExit) as error:
            main(["preprocess", "--help"])

        assert error.value.code == 0
        assert "info" in capsys.readouterr().out

    @pytest.mark.unit
    def test_help_works_without_the_native_dependencies(self, tmp_path):
        """The sub-application must not import GDAL or PCRaster at module level."""
        code = (
            "import sys; sys.modules['osgeo'] = None; sys.modules['pcraster'] = None; "
            "from rubem.cli import main; main(['preprocess', '--help'])"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=tmp_path,
            env={"PYTHONPATH": REPO_ROOT, "PATH": ""},
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, result.stderr
        assert "Prepare model inputs" in result.stdout

    @pytest.mark.unit
    def test_info_describes_a_raster(self, tmp_path, capsys, restore_logging):
        config = write_synthetic_dataset(str(tmp_path))

        main(["preprocess", "info", config["RASTERS"]["dem"]])

        output = capsys.readouterr().out
        assert "Size: 3 columns x 3 rows" in output
        assert "Cell: 500.0 (west 0.0, north 1500.0)" in output
        assert "Valid cells: 9 of 9" in output
        assert "Range: 100.0 to 140.0" in output

    @pytest.mark.unit
    def test_info_needs_an_existing_file(self, tmp_path, capsys, restore_logging):
        with pytest.raises(SystemExit) as error:
            main(["preprocess", "info", str(tmp_path / "absent.tif")])

        assert error.value.code == 2

    @pytest.mark.unit
    def test_info_reports_an_unreadable_raster_without_a_traceback(
        self, tmp_path, capsys, restore_logging
    ):
        """An existing file GDAL cannot open goes through ``_run``, like every other tool."""
        broken = tmp_path / "broken.tif"
        broken.write_text("not a raster", encoding="utf8")

        with pytest.raises(SystemExit) as error:
            main(["preprocess", "info", str(broken)])

        captured = capsys.readouterr()
        assert error.value.code == 1
        assert "cannot be opened as a raster" in captured.err
        assert "Traceback" not in captured.err
