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
