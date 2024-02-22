import pytest

from rubem.configuration.output_data_directory import OutputDataDirectory


class TestOutputDataDirectory:

    @pytest.mark.unit
    def test_create_directory_when_not_exists_then_create_it(self, mocker):
        mocker.patch("os.listdir", return_value=[])
        mock_exists = mocker.patch("os.path.exists", return_value=False)
        mock_isdir = mocker.patch("os.path.isfile", return_value=False)
        mock_makedirs = mocker.patch("os.makedirs")
        _ = OutputDataDirectory("test_path")
        mock_exists.assert_called_once_with("test_path")
        mock_isdir.assert_called_once_with("test_path")
        mock_makedirs.assert_called_once_with("test_path")

    @pytest.mark.unit
    def test_directory_exists_and_empty(self, mocker):
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.path.isfile", return_value=False)
        mocker.patch("os.listdir", return_value=[])
        _ = OutputDataDirectory("test_path")

    @pytest.mark.unit
    def test_directory_exists_and_not_empty(self, mocker):
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.path.isfile", return_value=False)
        mocker.patch("os.listdir", return_value=["file1.txt", "file2.txt", "file3.txt"])
        _ = OutputDataDirectory("test_path")

    @pytest.mark.unit
    def test_error_creating_directory(self, mocker):
        mocker.patch("os.listdir", return_value=[])
        mocker.patch("os.path.isfile", return_value=False)
        mock_makedirs = mocker.patch("os.makedirs", side_effect=Exception("error"))
        mock_error = mocker.patch("logging.Logger.error")
        with pytest.raises(Exception):
            _ = OutputDataDirectory("test_path")
            mock_makedirs.assert_called_once_with("test_path")
            mock_error.assert_called()

    @pytest.mark.unit
    def test_string_representation(self, mocker):
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.path.isfile", return_value=False)
        mocker.patch("os.listdir", return_value=[])
        directory = OutputDataDirectory("test_path")
        assert str(directory) == "test_path"
