import pytest

from rubem import (
    __version__,
    __author__,
    __copyright__,
    __email__,
    __license__,
    __date__,
    __release__,
)


class VersionTest:

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
        assert "2023-01-24" == __date__

    @pytest.mark.unit
    def test_version_str(self):
        assert "0.2.3" == __version__

    @pytest.mark.unit
    def test_release_str(self):
        assert "0.2.3-beta.2" == __release__
