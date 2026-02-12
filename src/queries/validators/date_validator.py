import re
from datetime import datetime
from typing import Any
from werkzeug.exceptions import BadRequest
from src.queries.enums.exception_message import QueryException
from src.queries.validators.base_validator import BaseParameterValidator


class DateParameterValidator(BaseParameterValidator):
    """Validates date parameters in YYYYMMDD format"""

    DATE_PATTERN = re.compile(r'^\d{8}$')
    DATE_FORMAT = '%Y%m%d'

    def matches(self, param_name: str) -> bool:
        """Match parameters ending with _date"""
        return param_name.lower().endswith('_date')

    def validate(self, param_name: str, value: Any) -> None:
        """
        Validate that value is a valid YYYYMMDD date.

        Raises BadRequest with clear message if invalid.

        Args:
            param_name: Name of the parameter (e.g., 'start_date')
            value: Value to validate

        Raises:
            BadRequest: If value is not a valid YYYYMMDD date

        Example:
            >>> validator = DateParameterValidator()
            >>> validator.validate('start_date', '20240101')  # Valid
            >>> validator.validate('end_date', '202010h')  # Raises BadRequest
        """
        if value is None:
            return  # Allow None (optional parameters)

        str_value = str(value).strip()

        # Check format (8 digits)
        if not self.DATE_PATTERN.match(str_value):
            raise BadRequest(
                QueryException.INVALID_DATE_PARAMETER.value.format(
                    param=param_name,
                    value=value
                )
            )

        # Validate actual date
        try:
            datetime.strptime(str_value, self.DATE_FORMAT)
        except ValueError:
            raise BadRequest(
                QueryException.INVALID_DATE_PARAMETER.value.format(
                    param=param_name,
                    value=value
                )
            )
