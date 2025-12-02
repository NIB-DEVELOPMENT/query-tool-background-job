"""
Manual test script for filename generation.
Run this to visually verify filename outputs.

Usage:
    python tests/manual_test_filename.py
"""

import sys
import os
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.document_save.filename_service import FilenameService


def test_various_scenarios():
    """Test various filename generation scenarios"""

    print("=" * 80)
    print("FILENAME GENERATION TEST SCENARIOS")
    print("=" * 80)
    print()

    # Scenario 1: Basic case
    print("1. Basic case (no parameters):")
    filename = FilenameService.generate_filename(
        user_id=31688,
        query_name="Active Employee Email",
        timestamp=datetime(2025, 6, 12, 14, 30, 22)
    )
    print(f"   {filename}")
    print(f"   Length: {len(filename)}")
    print()

    # Scenario 2: With parameters
    print("2. With parameters:")
    filename = FilenameService.generate_filename(
        user_id=31688,
        query_name="Active Employee Email",
        query_params={"department": "HR", "year": 2024},
        timestamp=datetime(2025, 6, 12, 14, 30, 22)
    )
    print(f"   {filename}")
    print(f"   Length: {len(filename)}")
    print()

    # Scenario 3: Many parameters
    print("3. Many parameters:")
    filename = FilenameService.generate_filename(
        user_id=31688,
        query_name="Employee Report",
        query_params={
            "department": "HR",
            "subdepartment": "Payroll",
            "year": 2024,
            "month": "June",
            "status": "Active"
        },
        timestamp=datetime(2025, 6, 12, 14, 30, 22)
    )
    print(f"   {filename}")
    print(f"   Length: {len(filename)}")
    print()

    # Scenario 4: Long query name
    print("4. Long query name:")
    filename = FilenameService.generate_filename(
        user_id=31688,
        query_name="Very Long Query Name That Describes Employee Benefits Report",
        query_params={"dept": "HR"},
        timestamp=datetime(2025, 6, 12, 14, 30, 22)
    )
    print(f"   {filename}")
    print(f"   Length: {len(filename)}")
    print()

    # Scenario 5: Special characters
    print("5. Special characters in query name:")
    filename = FilenameService.generate_filename(
        user_id=31688,
        query_name="Employee's <Active> Report/2024",
        query_params={"dept": "HR"},
        timestamp=datetime(2025, 6, 12, 14, 30, 22)
    )
    print(f"   {filename}")
    print(f"   Length: {len(filename)}")
    print()

    # Scenario 6: Maximum truncation case
    print("6. Maximum truncation case:")
    filename = FilenameService.generate_filename(
        user_id=31688,
        query_name="Extremely Long Query Name That Definitely Exceeds The Maximum Character Limit",
        query_params={
            "department": "Human Resources",
            "subdepartment": "Employee Relations",
            "location": "Nassau Head Office",
            "year": 2024,
            "month": "December",
            "status": "Active Full Time"
        },
        timestamp=datetime(2025, 6, 12, 14, 30, 22)
    )
    print(f"   {filename}")
    print(f"   Length: {len(filename)}")
    print(f"   Within limit: {len(filename) <= FilenameService.MAX_FILENAME_LENGTH}")
    print()

    # Scenario 7: Component extraction
    print("7. Component extraction test:")
    test_filename = "20250612-143022-31688-Active-Employee-Email-dept_HR-year_2024.csv"
    components = FilenameService.extract_components(test_filename)
    print(f"   Input: {test_filename}")
    print(f"   Extracted components:")
    for key, value in components.items():
        print(f"     {key}: {value}")
    print()

    # Scenario 8: Current timestamp
    print("8. Using current timestamp:")
    filename = FilenameService.generate_filename(
        user_id=31688,
        query_name="Real Time Test",
        query_params={"type": "live"}
    )
    print(f"   {filename}")
    print(f"   Length: {len(filename)}")
    print()

    # Scenario 9: Query name with underscores (converted to dashes)
    print("9. Query name with underscores (converted to dashes):")
    filename = FilenameService.generate_filename(
        user_id=31688,
        query_name="Employee_Status_Report",  # Will become Employee-Status-Report
        query_params={"type": "monthly"}
    )
    print(f"   {filename}")
    print(f"   Extracted components:")
    components = FilenameService.extract_components(filename)
    for key, value in components.items():
        print(f"     {key}: {value}")
    print()

    print("=" * 80)
    print("All tests completed!")
    print("=" * 80)


if __name__ == '__main__':
    test_various_scenarios()
