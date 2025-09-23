from dataclasses import dataclass
from typing import Optional


@dataclass
class QueryResultDTO:
    column_names: list
    rows: list
    total_count: Optional[int] = 0
