from dataclasses import dataclass
from werkzeug.datastructures import FileStorage
from typing import Optional


@dataclass
class CreateQueryDTO:
    name: str
    query_upload: FileStorage
    file_path: Optional[str] = None
    department: Optional[str] = None
