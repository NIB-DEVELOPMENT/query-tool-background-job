from dataclasses import dataclass

@dataclass
class ReportDeliveryDTO:
    first_name: str
    query_name:str
    link:str
    
    def __post_init__(self):
        self.first_name = self.first_name.capitalize()