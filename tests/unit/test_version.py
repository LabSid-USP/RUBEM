import unittest

from rubem import __version__, __author__, __copyright__, \
    __email__, __license__, __date__, __release__


class VersionTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_author_str(self):
        self.assertEqual("LabSid PHA EPUSP", __author__)

    def test_email_str(self):
        self.assertEqual("rubem.hydrological@labsid.eng.br", __email__)

    def test_copyright_str(self):
        self.assertEqual(
            "Copyright (C) 2020-2023 - LabSid/PHA/EPUSP", __copyright__
        )

    def test_license_str(self):
        self.assertEqual("GPL", __license__)

    def test_date_str(self):
        self.assertEqual("2023-05-17", __date__)

    def test_version_str(self):
        self.assertEqual("0.2.2", __version__)

    def test_release_str(self):
        self.assertEqual("0.2.2-beta.1", __release__)
