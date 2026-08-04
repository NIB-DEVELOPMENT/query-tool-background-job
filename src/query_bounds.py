"""Worker-side execution bounds (DS-07, pre-E.1 gate #4).

Tier limits arrive on each message (backend query_limits.py) — but a message
without them (tier limits off, legacy publisher, scheduled run) must still be
bounded. These are the worker's own backstop defaults, tunable via the mounted
config.py without a rebuild:

    class WorkerLimits:
        QUERY_TIMEOUT_SECONDS = 1800
        QUERY_ROW_CAP = 500_000

Standalone module: imports only config (optional) so it stays testable
without the mounted file.
"""

DEFAULT_TIMEOUT_SECONDS = 1800  # floor evidence: q288 took ~6 min on a 19-day
                                # window (2026-07-20) and scales with window
DEFAULT_ROW_CAP = 500_000


class QueryBoundsExceeded(Exception):
    """A query breached the worker's execution bounds — controlled failure,
    never a hang, OOM, or redelivery loop."""

    def __init__(self, kind: str, limit, query_id=None):
        self.kind = kind  # "timeout" | "row_cap"
        self.limit = limit
        self.query_id = query_id
        super().__init__(
            f"Query bounds exceeded: {kind} (limit={limit}, query_id={query_id})"
        )


def worker_limits():
    """Resolve (timeout_seconds, row_cap) from mounted config with defaults."""
    try:
        import config as _config
    except ImportError:
        return DEFAULT_TIMEOUT_SECONDS, DEFAULT_ROW_CAP
    limits = getattr(_config, "WorkerLimits", None)
    timeout = getattr(limits, "QUERY_TIMEOUT_SECONDS", None) or DEFAULT_TIMEOUT_SECONDS
    row_cap = getattr(limits, "QUERY_ROW_CAP", None) or DEFAULT_ROW_CAP
    return timeout, row_cap


def is_call_timeout_error(exc: BaseException) -> bool:
    """True when an exception (or its wrapped .orig) is the oracledb/Oracle
    call-timeout family: DPY-4024 (thin driver timeout), ORA-03156 (OCI call
    timeout), ORA-01013 (operation cancelled)."""
    seen = str(exc)
    orig = getattr(exc, "orig", None)
    if orig is not None:
        seen += " " + str(orig)
    return any(code in seen for code in ("DPY-4024", "ORA-03156", "ORA-01013"))
