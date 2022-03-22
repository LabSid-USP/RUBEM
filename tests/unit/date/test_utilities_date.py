import unittest
from unittest.case import expectedFailure

from rubem.date._date_calc import totalSteps, daysOfMonth


class StepsDateUtilitiesTest(unittest.TestCase):
    """Tests the function that returns the number of months between\
        start and end dates"""

    def setUp(self):
        """Runs before each test."""
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_totalSteps_null_end_start_date(self):
        """Test we can't use a null end date or start date"""
        startDate = None
        endDate = "31/12/9999"
        self.assertRaises(TypeError, totalSteps, startDate, endDate)

    def test_totalSteps_broken_end_start_date(self):
        """Test we can't use a broken end date or start date"""
        startDate = "01/01/wxyz"
        endDate = "31/12/9999"
        self.assertRaises(ValueError, totalSteps, startDate, endDate)

    def test_totalSteps_end_far_from_start_date(self):
        """Test we can use an end date far from start date"""
        startDate = "01/01/1500"
        endDate = "31/12/9999"
        result = totalSteps(startDate, endDate)
        expected = (1, 102000, 102000)  # first step, last step, total steps
        self.assertEqual(result, expected)

    def test_totalSteps_end_gt_start_date(self):
        """Test we can use an end date greater than start date"""
        startDate = "03/03/2002"
        endDate = "04/04/2002"
        result = totalSteps(startDate, endDate)
        expected = (1, 2, 2)  # first step, last step, total steps
        self.assertEqual(result, expected)

    def test_totalSteps_end_eq_start_date(self):
        """Test we can't use an end date equal start date"""
        startDate = "02/02/2002"
        endDate = "02/02/2002"
        self.assertRaises(AssertionError, totalSteps, startDate, endDate)

    def test_totalSteps_end_lt_start_date(self):
        """Test we can't use an end date less than start date"""
        startDate = "03/03/2002"
        endDate = "02/02/2002"
        self.assertRaises(AssertionError, totalSteps, startDate, endDate)


class DaysOfMonthDateUtilitiesTest(unittest.TestCase):
    """[summary]"""

    def setUp(self):
        """Runs before each test."""
        pass

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_daysOfMonth_valid_date_zero_timestep(self):
        """"""
        startDate = "01/02/2000"
        timestep = 0  # jan
        result = daysOfMonth(startDate, timestep)
        expected = 31
        self.assertEqual(result, expected)

    def test_daysOfMonth_valid_date_valid_timestep(self):
        """"""
        startDate = "01/02/2000"
        timestep = 1
        result = daysOfMonth(startDate, timestep)
        expected = 29  # fev
        self.assertEqual(result, expected)

    def test_daysOfMonth_None_date_valid_timestep(self):
        """"""
        startDate = None
        timestep = 1
        self.assertRaises(TypeError, daysOfMonth, startDate, timestep)

    def test_daysOfMonth_invalid_date_valid_timestep(self):
        """"""
        startDate = "01/02/xpto"
        timestep = 1
        self.assertRaises(ValueError, daysOfMonth, startDate, timestep)

    def test_daysOfMonth_valid_date_None_timestep(self):
        """"""
        startDate = "01/12/2000"
        timestep = None
        self.assertRaises(TypeError, daysOfMonth, startDate, timestep)


def suite():
    """
    Gather all the tests from this module in a test suite.
    """
    testSuite = unittest.TestSuite()
    testSuite.addTest(unittest.makeSuite(StepsDateUtilitiesTest))
    testSuite.addTest(unittest.makeSuite(DaysOfMonthDateUtilitiesTest))
    return testSuite


if __name__ == "__main__":
    testSuite = suite()
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(testSuite)
