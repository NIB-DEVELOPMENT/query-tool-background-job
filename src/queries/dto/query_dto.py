from dataclasses import dataclass
from typing import Optional


@dataclass
class QueryDTO:
    id: int
    name: str
    file_path: str
    department: str
    query_params: Optional[dict] = None
