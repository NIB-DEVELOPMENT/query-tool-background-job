from dataclasses import dataclass
from werkzeug.datastructures import FileStorage


@dataclass
class ValidatedQueryDTO:
    validated: bool
    query_name: str
    query_upload: FileStorage
    department: str
    id
