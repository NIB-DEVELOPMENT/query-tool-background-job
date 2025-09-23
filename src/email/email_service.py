import json
import requests
from dataclasses import dataclass, asdict
from typing import Dict, List
from config import NIBEmailService
from src.email.dto.email_request_dto import EmailRequestDTO

@dataclass
class EmailService:
    
    def send_request(self, request: EmailRequestDTO) -> None:
        try:
            submit_request_endpoint = f"{NIBEmailService.root_url}/email"
            headers = {
                        "Content-Type": "application/json", 
                        "Accept": "text/plain", 
                        "Cache-Control": "no-cache",
                        "Api-key": NIBEmailService.api_key, 
                        "App-Name": NIBEmailService.app_name
                      }
            data = json.dumps(asdict(request))
            req = requests.post(url=submit_request_endpoint,data=data,headers=headers)
            if not req.ok:
                print(req.text)
        except Exception as e:
            print(str(e))
