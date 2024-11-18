from dataclasses import dataclass
from src.nib_user.nib_user_model import NIBUser, db
from src.nib_user.dto.nib_user_dto import NIBUserDTO
from src.database.SQLReader import SQLReader
import os
from typing import List
from sqlalchemy.sql import text

# from sqlalchemy import CursorResult


@dataclass
class NIBUserRepo(SQLReader):
    db = db
    scriptPath = os.path.dirname(__file__) + os.sep + "scripts"

    def find_by_user_id(self, user_id: int) -> NIBUserDTO:
        return self.to_nib_user_dto(self._find_by_user_id(user_id=user_id))

    def find_by_id(self, nib_user_id: int) -> NIBUserDTO:
        return self.to_nib_user_dto(self._find_by_id(nib_user_id=nib_user_id))

    def get_user_local_office(self, user_id: int) -> int:
        local_office = None
        sqlFilePath = self.scriptPath + os.sep + "get_local_office.sql"
        script = self.getSQL(sqlFilePath)
        results = self.db.session.execute(text(script), {"user_id": user_id})
        for result in results.mappings():
            local_office = result["local_office"]
        return local_office

    def get_user_nib_number(self, user_id: int) -> int:
        nib_number = None
        sqlFilePath = self.scriptPath + os.sep + "get_nib_number.sql"
        script = self.getSQL(sqlFilePath)
        results = self.db.session.execute(text(script), {"user_id": user_id}).mappings()
        for result in results:
            nib_number = result["alt_identifier"]
        return nib_number

    def get_role(self, role: str) -> str:
        role_result = None
        sqlFilePath = self.scriptPath + os.sep + "get_role.sql"
        script = self.getSQL(sqlFilePath)
        results = self.db.session.execute(text(script), {"role": role})
        for result in results.mappings():
            role_result = result["display_name"]
        return role_result

    def get_user_roles(self, user_id: int) -> List[str]:
        sqlFilePath = self.scriptPath + os.sep + "get_user_roles.sql"
        script = self.getSQL(sqlFilePath)
        results = self.db.session.execute(text(script), {"user_id": user_id})
        return [result["display_name"] for result in results.mappings()]

    def _find_by_user_id(self, user_id: int) -> NIBUser:
        return NIBUser.query.filter(NIBUser.user_id == user_id).first()

    def _find_by_id(self, nib_user_id) -> NIBUser:
        return NIBUser.query.filter(NIBUser.id == nib_user_id).first()

    def to_nib_user_dto(self, user: NIBUser) -> NIBUserDTO:
        user_dto: NIBUserDTO = None
        if user:
            user_dto = NIBUserDTO(
                id=user.id,
                user_id=user.user_id,
                user_name=user.user_name,
                first_name=user.first_name,
                last_name=user.last_name,
                middle_name=user.middle_name,
                email=user.email,
            )
        return user_dto
