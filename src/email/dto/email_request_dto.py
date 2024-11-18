from dataclasses import dataclass
from typing import List
from src.email.dto.recipient_dto import RecipientDTO

@dataclass
class EmailRequestDTO:
    email_from: str
    email_to: List[RecipientDTO]
    subject: str
    template_id: int