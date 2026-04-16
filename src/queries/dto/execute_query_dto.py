from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecuteQueryDTO:
    first_name: str
    query_id: int
    name: str
    file_path: str
    user_id: int
    query_params: Optional[dict] = None
    email: Optional[str] = None
    department: Optional[str] = None
    timeout_seconds: Optional[int] = None  # Tier-based query timeout
    row_cap: Optional[int] = None          # Tier-based row limit
    tier: Optional[str] = None             # For logging: standard/supervisor/power/dev
