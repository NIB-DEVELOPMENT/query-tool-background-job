from dataclasses import dataclass
from typing import List
from src.nib_user.nib_user_repo import NIBUserRepo
from src.nib_user.enums.exception_messages import NIBUserExceptions
from werkzeug.exceptions import BadRequest, Forbidden
from src.nib_user.enums.customer_service_roles import CustomerServiceRoles
from src.nib_user.enums.family_island_roles import FamilyIslandRoles


@dataclass
class NIBUserService:
    nib_user_repo = NIBUserRepo()

    def find_user_nib_number(self, user_id: int) -> int:
        nib_number = self.nib_user_repo.get_user_nib_number(user_id=user_id)
        if not nib_number:
            raise BadRequest(NIBUserExceptions.NIB_USER_NO_NIB_NUMBER_FOUND.value)
        return nib_number

    def find_user_roles(self, user_id: int) -> List[str]:
        nib_user_roles = self.nib_user_repo.get_user_roles(user_id=user_id)
        if not nib_user_roles:
            raise BadRequest(NIBUserExceptions.NO_ROLES_FOUND.value)
        return nib_user_roles

    def find_roles_allowed_to_route_applications_to_themselves(self) -> List[str]:
        return [role.value for role in CustomerServiceRoles] + [
            FamilyIslandRoles.MANAGER.value,
            FamilyIslandRoles.SUB_OFFICE_MANAGER.value,
        ]

    def validate_user_role_allowed(
        self, user_roles: List[str], allowable_roles: List[str]
    ) -> bool:
        return any(role in allowable_roles for role in user_roles)
    
    def validate_role_exist(self, role: str) -> bool:
        if not self.nib_user_repo.get_role(role=role):
            raise BadRequest(NIBUserExceptions.ROLE_DOESNT_EXIST.value)
        return True
    
    def validate_user_exist(self, user_id: int) -> bool:
      if not self.nib_user_repo._find_by_user_id(user_id=user_id):
          raise BadRequest(NIBUserExceptions.USER_DOESNT_EXIST.value)
      return True