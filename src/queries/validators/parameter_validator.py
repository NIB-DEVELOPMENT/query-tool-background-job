import json
import logging
import os
from typing import Any, Dict, List, Optional

from werkzeug.exceptions import BadRequest

from src.queries.validators.base_validator import BaseParameterValidator
from src.queries.validators.date_validator import DateParameterValidator


# ─── Mode handling (TC-01) ────────────────────────────────────────────────────
#
# Mirrors backend's parameter_validator.py. The bg-job uses logger-only output
# in all modes (no DB write target) because by the time a message reaches the
# bg-job, the backend's validator has already run — bg-job validator firing in
# shadow mode is a rare event and gets surfaced via Sentry/logs.
#
# See nib-query-tool-backend/src/queries/validators/parameter_validator.py for
# the full mode semantics.

logger = logging.getLogger(__name__)

VALID_MODES = {"off", "shadow", "enforce"}
_MODE_ENV = "PARAMETER_VALIDATOR_MODE"


def _resolve_mode() -> str:
    raw = os.environ.get(_MODE_ENV, "off").strip().lower()
    if raw not in VALID_MODES:
        logger.warning(
            "%s=%r is not in %s; falling back to 'off'", _MODE_ENV, raw, sorted(VALID_MODES)
        )
        return "off"
    return raw


def _log_shadow_rejection(param_name: str, param_value: Any, error: BadRequest) -> None:
    logger.info(
        "validator_shadow_decision",
        extra={
            "source": "parameter_validator",
            "subsystem": "background-job",
            "action": "would_reject",
            "details": json.dumps({
                "param_name": param_name,
                "param_value": str(param_value)[:200],
                "rule_violated": str(error.description)[:300],
            }),
            "mode": "shadow",
        },
    )


class ParameterValidator:
    """
    Main validator that orchestrates parameter validation.
    Mode-gated per PARAMETER_VALIDATOR_MODE — mirrors backend behavior.
    """

    def __init__(self):
        self.validators: List[BaseParameterValidator] = [
            DateParameterValidator(),
            # Future validators added here; keep parity with backend.
        ]

    def validate_parameters(self, query_params: Optional[Dict[str, Any]]) -> None:
        """
        Validate all query parameters.

        Raises:
            BadRequest: when mode is "enforce" and a parameter fails validation.
        """
        if not query_params:
            return

        mode = _resolve_mode()
        if mode == "off":
            return

        for param_name, param_value in query_params.items():
            self._validate_parameter(param_name, param_value, mode)

    def _validate_parameter(self, param_name: str, param_value: Any, mode: str) -> None:
        for validator in self.validators:
            if validator.matches(param_name):
                try:
                    validator.validate(param_name, param_value)
                except BadRequest as err:
                    if mode == "shadow":
                        _log_shadow_rejection(param_name, param_value, err)
                        return
                    raise
                break
