import unittest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from werkzeug.exceptions import BadRequest
from src.queries.validators.parameter_validator import ParameterValidator
from src.queries.validators.date_validator import DateParameterValidator


class TestDateParameterValidator(unittest.TestCase):
    """Test cases for DateParameterValidator"""

    def setUp(self):
        self.validator = DateParameterValidator()

    def test_matches_date_parameters(self):
        """Test that _date parameters are matched"""
        self.assertTrue(self.validator.matches('start_date'))
        self.assertTrue(self.validator.matches('end_date'))
        self.assertTrue(self.validator.matches('birth_date'))
        self.assertTrue(self.validator.matches('START_DATE'))  # Case insensitive
        self.assertFalse(self.validator.matches('user_id'))
        self.assertFalse(self.validator.matches('name'))

    def test_valid_dates(self):
        """Test valid YYYYMMDD dates pass"""
        # Should not raise exceptions
        self.validator.validate('start_date', '20240101')
        self.validator.validate('end_date', '20251231')
        self.validator.validate('birth_date', '19900515')

    def test_invalid_format_length(self):
        """Test dates with wrong length fail"""
        with self.assertRaises(BadRequest):
            self.validator.validate('start_date', '2024010')  # 7 digits

        with self.assertRaises(BadRequest):
            self.validator.validate('start_date', '202401011')  # 9 digits

    def test_invalid_format_non_numeric(self):
        """Test non-numeric characters fail"""
        with self.assertRaises(BadRequest):
            self.validator.validate('end_date', '202010h1')  # THE ACTUAL ERROR CASE

        with self.assertRaises(BadRequest):
            self.validator.validate('end_date', '2024-01-01')  # Contains dashes

        with self.assertRaises(BadRequest):
            self.validator.validate('start_date', 'abcd1234')  # Contains letters

    def test_invalid_date_values(self):
        """Test invalid calendar dates fail"""
        with self.assertRaises(BadRequest):
            self.validator.validate('start_date', '20241332')  # Day 32

        with self.assertRaises(BadRequest):
            self.validator.validate('start_date', '20241301')  # Month 13

        with self.assertRaises(BadRequest):
            self.validator.validate('end_date', '20230229')  # Non-leap year Feb 29

    def test_valid_leap_year(self):
        """Test that leap year dates are valid"""
        # 2024 is a leap year
        self.validator.validate('start_date', '20240229')  # Should not raise

    def test_none_allowed(self):
        """Test None values allowed (optional params)"""
        self.validator.validate('start_date', None)
        # Should not raise exception

    def test_whitespace_trimmed(self):
        """Test that whitespace is trimmed before validation"""
        self.validator.validate('start_date', '  20240101  ')
        # Should not raise exception

    def test_numeric_value_converted(self):
        """Test that numeric values are converted to string"""
        self.validator.validate('start_date', 20240101)
        # Should not raise exception


class TestParameterValidator(unittest.TestCase):
    """Test cases for ParameterValidator orchestrator"""

    def setUp(self):
        self.validator = ParameterValidator()

    def test_valid_parameters(self):
        """Test validation of valid parameter set"""
        params = {
            'start_date': '20240101',
            'end_date': '20241231',
            'user_id': '12345',
            'department': 'HR'
        }
        self.validator.validate_parameters(params)
        # Should not raise exception

    def test_invalid_date_parameter(self):
        """Test invalid date raises BadRequest"""
        params = {
            'start_date': '202010h',  # Invalid format - reproduces the actual error
            'user_id': '12345'
        }
        with self.assertRaises(BadRequest):
            self.validator.validate_parameters(params)

    def test_empty_parameters(self):
        """Test empty/None parameters don't error"""
        self.validator.validate_parameters(None)
        self.validator.validate_parameters({})
        # Should not raise exceptions

    def test_mixed_parameters(self):
        """Test mixed date and non-date parameters"""
        params = {
            'start_date': '20240101',
            'user_id': '12345',
            'query_name': 'Test Query',
            'end_date': '20241231',
            'department': 'HR'
        }
        self.validator.validate_parameters(params)
        # Should not raise exception

    def test_only_non_date_parameters(self):
        """Test that non-date parameters pass without validation"""
        params = {
            'user_id': '12345',
            'query_name': 'Test Query',
            'department': 'HR',
            'status': 'active'
        }
        self.validator.validate_parameters(params)
        # Should not raise exception

    def test_multiple_invalid_dates(self):
        """Test that first invalid date raises error"""
        params = {
            'start_date': '202010h',  # Invalid
            'end_date': 'invalid',     # Also invalid
        }
        with self.assertRaises(BadRequest):
            self.validator.validate_parameters(params)


if __name__ == '__main__':
    unittest.main()
