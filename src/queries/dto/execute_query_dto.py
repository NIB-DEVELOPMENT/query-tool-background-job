from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecuteQueryDTO:
    query_id: int
    page: int
    per_page: int
    query_params: Optional[dict] = None
