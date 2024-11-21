from dataclasses import dataclass
from typing import List
from config import NIBEmailService
from src.email.email_service import EmailService
from src.email.dto.recipient_dto import RecipientDTO
from src.email.dto.email_request_dto import EmailRequestDTO


@dataclass
class query_report_delivered(EmailService):
    email_from = "alerts@nib-bahamas.com"
    email_to = []
    subject = "NIB Query Tool: Query Report Download"
    template_id = NIBEmailService.template_ids["query_report_delivered.html"]

    def __init__(self) -> None:
        super().__init__()

    def send(self, recipients: List[RecipientDTO]) -> None:
        self.email_to = recipients
        email_request = EmailRequestDTO(
            email_from=self.email_from,
            email_to=self.email_to,
            subject=self.subject,
            template_id=self.template_id,
        )
        self.send_request(email_request)