from dataclasses import dataclass
from typing import List

@dataclass
class AuthenticatedUserDTO:
    user_id: int
    roles: List[str]
    user_name: str