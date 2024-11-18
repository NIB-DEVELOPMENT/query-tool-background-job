from dataclasses import dataclass
from typing import Dict

@dataclass
class RecipientDTO:
    email_address: str
    data: Dict