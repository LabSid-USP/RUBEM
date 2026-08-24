import pytest

from rubem import (
    __author__,
    __copyright__,
    __date__,
    __email__,
    __license__,
    __release__,
    __version__,
)


class TestVersionInfo:
    @pytest.mark.unit
    def test_author_str(self):
        assert "LabSid PHA EPUSP" == __author__

    @pytest.mark.unit
    def test_email_str(self):
        assert "rubem.hydrological@labsid.eng.br" == __email__

    @pytest.mark.unit
    def test_copyright_str(self):
        assert "Copyright (C) 2020-2024 - LabSid/PHA/EPUSP" == __copyright__

    @pytest.mark.unit
    def test_license_str(self):
        assert "GPL" == __license__

    @pytest.mark.unit
    def test_date_str(self):
        assert "2026-08-23" == __date__

    @pytest.mark.unit
    def test_version_str(self):
        assert "0.10.0.dev0" == __version__

    @pytest.mark.unit
    def test_release_str(self):
        assert "0.10.0.dev0" == __release__
