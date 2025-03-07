from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class DateRangeDTO:
    start: Optional[date] = None
    end: Optional[date] = None
