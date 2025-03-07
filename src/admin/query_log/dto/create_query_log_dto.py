from dataclasses import dataclass
from typing import Optional
from src.queries.dto.query_dto import QueryDTO
from src.nib_user.dto.nib_user_dto import NIBUserDTO


@dataclass
class CreateQueryLogDTO:
    user: NIBUserDTO
    query: QueryDTO
    status: Optional[str] = "Pending"
