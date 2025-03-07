from dataclasses import dataclass
from src.admin.query_log.dto.date_range_dto import (
    DateRangeDTO,
)
from typing import Optional


@dataclass
class QueryLogSearchCriteriaDTO:
    user_name: Optional[str] = None
    query_id: Optional[int] = None
    date: Optional[DateRangeDTO] = None
