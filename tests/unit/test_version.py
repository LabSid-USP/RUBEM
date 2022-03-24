import unittest

import rubem.__version__ as rbv


class VersionTest(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_author_str(self):
        self.assertEqual("LabSid PHA EPUSP", rbv.__author__)

    def test_email_str(self):
        self.assertEqual("rubem.hydrological@labsid.eng.br", rbv.__email__)

    def test_copyright_str(self):
        self.assertEqual(
            "Copyright 2020-2022, LabSid PHA EPUSP", rbv.__copyright__
        )

    def test_license_str(self):
        self.assertEqual("GPL", rbv.__license__)

    def test_date_str(self):
        self.assertEqual("2022-03-23", rbv.__date__)

    def test_version_str(self):
        self.assertEqual("0.1.3", rbv.__version__)

    def test_release_str(self):
        self.assertEqual("0.1.3-alpha", rbv.__release__)
