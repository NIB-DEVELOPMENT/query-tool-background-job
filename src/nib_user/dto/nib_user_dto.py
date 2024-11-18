from dataclasses import dataclass
from typing import Optional

@dataclass
class NIBUserDTO:
    id: int
    user_id: int
    user_name: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    email: Optional[str] = None