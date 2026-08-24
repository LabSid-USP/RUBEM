import argparse
import logging
import os

import pytest

from rubem.validation.cli_validators import file_path_cli_arg_validator

LOGGER_NAME = "rubem.validation.cli_validators"


class TestFilePathCliArgValidator:
    @pytest.mark.unit
    def test_missing_path_raises(self, tmp_path, caplog):
        missing = tmp_path / "absent.json"

        with caplog.at_level("ERROR", logger=LOGGER_NAME):
            with pytest.raises(argparse.ArgumentTypeError, match="does not exist"):
                file_path_cli_arg_validator(str(missing))

        assert caplog.records
        assert caplog.records[0].levelno == logging.ERROR

    @pytest.mark.unit
    def test_directory_path_raises(self, tmp_path, caplog):
        with caplog.at_level("ERROR", logger=LOGGER_NAME):
            with pytest.raises(argparse.ArgumentTypeError, match="not a valid file"):
                file_path_cli_arg_validator(str(tmp_path))

        assert caplog.records
        assert caplog.records[0].levelno == logging.ERROR

    @pytest.mark.unit
    def test_unreadable_path_raises(self, tmp_path, monkeypatch, caplog):
        target = tmp_path / "config.json"
        target.write_text("{}", encoding="utf8")

        monkeypatch.setattr(os, "access", lambda path, mode: False)

        with caplog.at_level("ERROR", logger=LOGGER_NAME):
            with pytest.raises(argparse.ArgumentTypeError, match="not readable"):
                file_path_cli_arg_validator(str(target))

        assert caplog.records
        assert caplog.records[0].levelno == logging.ERROR

    @pytest.mark.unit
    def test_empty_file_raises(self, tmp_path, caplog):
        target = tmp_path / "config.json"
        target.write_text("", encoding="utf8")

        with caplog.at_level("ERROR", logger=LOGGER_NAME):
            with pytest.raises(argparse.ArgumentTypeError, match="is empty"):
                file_path_cli_arg_validator(str(target))

        assert caplog.records
        assert caplog.records[0].levelno == logging.ERROR

    @pytest.mark.unit
    def test_wrong_extension_raises(self, tmp_path, caplog):
        target = tmp_path / "config.txt"
        target.write_text("{}", encoding="utf8")

        with caplog.at_level("ERROR", logger=LOGGER_NAME):
            with pytest.raises(argparse.ArgumentTypeError, match="not a valid file format"):
                file_path_cli_arg_validator(str(target))

        assert caplog.records
        assert caplog.records[0].levelno == logging.ERROR

    @pytest.mark.unit
    def test_valid_json_file_returns_path_unchanged(self, tmp_path):
        target = tmp_path / "config.json"
        target.write_text("{}", encoding="utf8")

        result = file_path_cli_arg_validator(str(target))

        assert result == str(target)
