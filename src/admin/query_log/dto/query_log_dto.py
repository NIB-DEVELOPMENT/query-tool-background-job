from dataclasses import dataclass


@dataclass
class QueryLogDTO:
    id: int
    user_id: int
    query_id: int
    user_name: str
    status: str
