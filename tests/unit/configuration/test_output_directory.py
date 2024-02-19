import pytest

from rubem.configuration.output_data_directory import OutputDataDirectory


class TestOutputDataDirectory:

    @pytest.mark.unit
    def test_create_directory_when_not_exists(self, mocker):
        with mocker.patch("os.path.isdir", return_value=False) as mock_isdir, mocker.patch(
            "os.makedirs"
        ) as mock_makedirs, pytest.raises(Exception):
            _ = OutputDataDirectory("test_path")
            mock_isdir.assert_called_once_with("test_path")
            mock_makedirs.assert_called_once_with("test_path")

    @pytest.mark.unit
    def test_directory_exists_and_empty(self, mocker):
        with mocker.patch("os.path.isdir", return_value=True), mocker.patch(
            "os.listdir", return_value=[]
        ):
            _ = OutputDataDirectory("test_path")

    @pytest.mark.unit
    def test_directory_exists_and_not_empty(self, mocker):
        with mocker.patch("os.path.isdir", return_value=True), mocker.patch(
            "os.listdir", return_value=["file1.txt", "file2.txt", "file3.txt"]
        ):
            _ = OutputDataDirectory("test_path")

    @pytest.mark.unit
    def test_error_creating_directory(self, mocker):
        with mocker.patch("os.path.isdir", return_value=False), mocker.patch(
            "os.makedirs", side_effect=Exception("error")
        ) as mock_makedirs, mocker.patch("logging.Logger.error") as mock_error, pytest.raises(
            Exception
        ):
            _ = OutputDataDirectory("test_path")
            mock_makedirs.assert_called_once_with("test_path")
            mock_error.assert_called()

    @pytest.mark.unit
    def test_string_representation(self):
        directory = OutputDataDirectory("test_path")
        assert str(directory) == "test_path"
