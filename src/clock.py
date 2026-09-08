"""One local clock for the worker.

Containers run UTC while the Oracle server clock (SYSDATE) and every user are on
Nassau time. Using ``datetime.now()`` made a ``08:00`` schedule fire at 04:00 and
put every log line 4h off the DB (2026-09-07). All wall-clock decisions go
through here; the zone is config-driven with a safe default.

Returns NAIVE datetimes in local wall time because the DB columns are DATEs
compared against SYSDATE -- tz-aware values would not bind cleanly.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "America/Nassau"


def local_timezone() -> str:
    try:
        import config as _config  # mounted at runtime; absent in some tests
    except ImportError:
        return DEFAULT_TIMEZONE
    app_cfg = getattr(_config, "AppConfig", None)
    return getattr(app_cfg, "TIMEZONE", None) or DEFAULT_TIMEZONE


def now_local() -> datetime:
    return datetime.now(ZoneInfo(local_timezone())).replace(tzinfo=None)
