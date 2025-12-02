from typing import Dict, List, Any, Optional
from src.queries.validators.base_validator import BaseParameterValidator
from src.queries.validators.date_validator import DateParameterValidator


class ParameterValidator:
    """
    Main validator that orchestrates parameter validation.
    Delegates to specific validators based on parameter names.
    """

    def __init__(self):
        # Register all validators
        self.validators: List[BaseParameterValidator] = [
            DateParameterValidator(),
            # Future validators can be added here:
            # IntegerParameterValidator(),
            # EmailParameterValidator(),
        ]

    def validate_parameters(self, query_params: Optional[Dict[str, Any]]) -> None:
        """
        Validate all query parameters.

        Args:
            query_params: Dictionary of parameter names to values

        Raises:
            BadRequest: If any parameter fails validation

        Example:
            >>> validator = ParameterValidator()
            >>> validator.validate_parameters({'start_date': '20240101'})  # Valid
            >>> validator.validate_parameters({'end_date': '202010h'})  # Raises BadRequest
        """
        if not query_params:
            return

        for param_name, param_value in query_params.items():
            self._validate_parameter(param_name, param_value)

    def _validate_parameter(self, param_name: str, param_value: Any) -> None:
        """
        Validate a single parameter by finding appropriate validator.

        Args:
            param_name: Name of the parameter
            param_value: Value to validate
        """
        for validator in self.validators:
            if validator.matches(param_name):
                validator.validate(param_name, param_value)
                # Only use first matching validator
                break
