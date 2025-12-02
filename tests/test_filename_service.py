import unittest
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.document_save.filename_service import FilenameService


class TestFilenameService(unittest.TestCase):
    """Test cases for FilenameService"""

    def test_basic_filename_generation(self):
        """Test basic filename generation without parameters"""
        filename = FilenameService.generate_filename(
            user_id=31688,
            query_name="Active Employee Email",
            query_params=None,
            timestamp=datetime(2025, 6, 12, 14, 30, 22)
        )

        self.assertEqual(
            filename,
            "20250612-143022-31688-Active-Employee-Email.csv"
        )

    def test_filename_with_parameters(self):
        """Test filename generation with query parameters"""
        filename = FilenameService.generate_filename(
            user_id=31688,
            query_name="Active Employee Email",
            query_params={"department": "HR", "year": 2024},
            timestamp=datetime(2025, 6, 12, 14, 30, 22)
        )

        self.assertEqual(
            filename,
            "20250612-143022-31688-Active-Employee-Email-dept_HR-year_2024.csv"
        )

    def test_query_name_sanitization(self):
        """Test that spaces and special characters are handled correctly"""
        sanitized = FilenameService._sanitize_query_name("Active  Employee   Email?")
        self.assertEqual(sanitized, "Active-Employee-Email")

    def test_query_name_with_invalid_chars(self):
        """Test removal of filesystem-invalid characters"""
        sanitized = FilenameService._sanitize_query_name('Active<Employee>Email/Report')
        self.assertEqual(sanitized, "ActiveEmployeeEmailReport")

    def test_empty_query_name(self):
        """Test handling of empty query name"""
        sanitized = FilenameService._sanitize_query_name("")
        self.assertEqual(sanitized, "unnamed-query")

    def test_parameter_abbreviation(self):
        """Test that common parameter names are abbreviated"""
        self.assertEqual(FilenameService._abbreviate_key("department"), "dept")
        self.assertEqual(FilenameService._abbreviate_key("employee"), "emp")
        self.assertEqual(FilenameService._abbreviate_key("start_date"), "sdate")

    def test_parameter_formatting(self):
        """Test parameter formatting"""
        params = FilenameService._format_parameters({
            "department": "HR",
            "year": 2024,
            "status": "Active"
        })

        # Should be sorted alphabetically by key
        self.assertEqual(params, "dept_HR-sts_Active-year_2024")

    def test_long_filename_truncation(self):
        """Test that very long filenames are truncated appropriately"""
        long_query_name = "Very Long Query Name That Exceeds Maximum Length Allowed For Filenames"
        long_params = {
            "department": "Human Resources Department",
            "subdepartment": "Employee Relations Subdepartment",
            "year": 2024,
            "month": "December",
            "status": "Active Full Time Employees Only",
            "location": "Nassau Head Office Building"
        }

        filename = FilenameService.generate_filename(
            user_id=31688,
            query_name=long_query_name,
            query_params=long_params,
            timestamp=datetime(2025, 6, 12, 14, 30, 22)
        )

        # Should be within max length
        self.assertLessEqual(len(filename), FilenameService.MAX_FILENAME_LENGTH)

        # Should still start with timestamp and user_id
        self.assertTrue(filename.startswith("20250612-143022-31688-"))

        # Should end with .csv
        self.assertTrue(filename.endswith(".csv"))

    def test_special_characters_in_params(self):
        """Test handling of special characters in parameter values"""
        params = FilenameService._format_parameters({
            "name": "O'Brien & Associates",
            "date": "12/31/2024"
        })

        # Filesystem-invalid chars should be removed (only / is invalid, & and ' are valid)
        self.assertNotIn("/", params)
        # Should contain the sanitized values
        self.assertIn("name_", params)
        self.assertIn("date_", params)

    def test_extract_components(self):
        """Test extraction of components from generated filename"""
        filename = "20250612-143022-31688-Active-Employee-Email-dept_HR-year_2024.csv"

        components = FilenameService.extract_components(filename)

        self.assertEqual(components['timestamp'], "20250612-143022")
        self.assertEqual(components['user_id'], "31688")
        self.assertEqual(components['query_name'], "Active-Employee-Email")
        self.assertEqual(components['params'], "dept_HR-year_2024")
        self.assertEqual(components['extension'], ".csv")

    def test_filename_chronological_sorting(self):
        """Test that filenames sort chronologically"""
        filenames = [
            FilenameService.generate_filename(
                user_id=1, query_name="Test",
                timestamp=datetime(2025, 6, 12, 14, 30, 22)
            ),
            FilenameService.generate_filename(
                user_id=1, query_name="Test",
                timestamp=datetime(2025, 6, 12, 15, 45, 30)
            ),
            FilenameService.generate_filename(
                user_id=1, query_name="Test",
                timestamp=datetime(2025, 6, 11, 10, 0, 0)
            ),
        ]

        sorted_filenames = sorted(filenames)

        # Should sort in chronological order
        self.assertTrue(sorted_filenames[0].startswith("20250611"))
        self.assertTrue(sorted_filenames[1].startswith("20250612-143022"))
        self.assertTrue(sorted_filenames[2].startswith("20250612-154530"))

    def test_multiple_params_smart_truncation(self):
        """Test that parameter truncation preserves complete pairs"""
        # Create a params string that needs truncation
        params_str = "dept_HR-subdept_Relations-year_2024-month_Dec-status_Active"

        # Truncate to 30 characters
        truncated = FilenameService._truncate_params_smart(params_str, 30)

        # Should be within limit
        self.assertLessEqual(len(truncated), 30)

        # Should end with a complete pair (not end with a dash)
        self.assertFalse(truncated.endswith('-'))

        # Each dash-separated component should be a complete key_value pair
        parts = truncated.split('-')
        for part in parts:
            self.assertIn('_', part)  # Each part should have key_value format

    def test_no_parameters(self):
        """Test filename generation with no parameters"""
        filename = FilenameService.generate_filename(
            user_id=12345,
            query_name="Simple Query",
            query_params={},
            timestamp=datetime(2025, 1, 15, 9, 30, 0)
        )

        self.assertEqual(filename, "20250115-093000-12345-Simple-Query.csv")

    def test_numeric_parameter_values(self):
        """Test that numeric parameter values are handled correctly"""
        filename = FilenameService.generate_filename(
            user_id=100,
            query_name="Test",
            query_params={"year": 2024, "month": 12, "day": 31},
            timestamp=datetime(2025, 1, 1, 0, 0, 0)
        )

        self.assertIn("year_2024", filename)
        self.assertIn("month_12", filename)
        self.assertIn("day_31", filename)


if __name__ == '__main__':
    unittest.main()
