import os

import pytest

from rubem.configuration.output_data_directory import OutputDataDirectory


class TestOutputDataDirectory:
    @pytest.mark.unit
    def test_a_missing_directory_is_created(self, tmp_path, caplog):
        target = tmp_path / "results" / "run"

        with caplog.at_level("WARNING"):
            directory = OutputDataDirectory(target)

        assert target.is_dir()
        assert directory.path == str(target)
        assert "Output directory does not exist" in caplog.text

    @pytest.mark.unit
    def test_an_existing_empty_directory_is_accepted_silently(self, tmp_path, caplog):
        with caplog.at_level("WARNING"):
            OutputDataDirectory(tmp_path)

        assert caplog.text == ""

    @pytest.mark.unit
    def test_existing_data_is_reported(self, tmp_path, caplog):
        (tmp_path / "old.csv").write_text("x", encoding="utf8")

        with caplog.at_level("WARNING"):
            OutputDataDirectory(tmp_path)

        assert "There is data in the output directory" in caplog.text

    @pytest.mark.unit
    def test_a_file_is_not_a_directory(self, tmp_path):
        target = tmp_path / "output"
        target.write_text("x", encoding="utf8")

        with pytest.raises(NotADirectoryError, match="is not a directory"):
            OutputDataDirectory(target)

    @pytest.mark.unit
    def test_a_creation_failure_is_logged_and_raised(self, tmp_path, caplog, monkeypatch):
        target = tmp_path / "blocked" / "output"

        def refuse(self, *args, **kwargs):
            raise PermissionError("no way")

        monkeypatch.setattr("pathlib.Path.mkdir", refuse)

        with caplog.at_level("ERROR"):
            with pytest.raises(PermissionError):
                OutputDataDirectory(target)

        assert "Failed to create output directory" in caplog.text

    @pytest.mark.unit
    def test_string_representation_and_string_input(self, tmp_path):
        directory = OutputDataDirectory(str(tmp_path))

        assert str(directory) == str(tmp_path)
        assert directory.path == str(tmp_path)

    @pytest.mark.unit
    def test_bytes_input_is_deprecated_but_accepted(self, tmp_path):
        with pytest.warns(DeprecationWarning, match="bytes paths are deprecated"):
            directory = OutputDataDirectory(os.fsencode(str(tmp_path)))

        assert directory.path == str(tmp_path)
