from abc import ABC, abstractmethod
from typing import Any


class BaseParameterValidator(ABC):
    """Base class for all parameter validators"""

    @abstractmethod
    def validate(self, param_name: str, value: Any) -> None:
        """
        Validate a parameter value.

        Args:
            param_name: Name of the parameter
            value: Value to validate

        Raises:
            BadRequest: If validation fails
        """
        pass

    @abstractmethod
    def matches(self, param_name: str) -> bool:
        """
        Check if this validator should handle the parameter.

        Args:
            param_name: Name of the parameter

        Returns:
            bool: True if this validator handles this parameter type
        """
        pass
