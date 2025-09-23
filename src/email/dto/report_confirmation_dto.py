from dataclasses import dataclass

@dataclass
class ReportConfirmationDTO:
    first_name: str
    query_name: str

    def __post_init__(self):
        self.first_name = self.first_name.capitalize()