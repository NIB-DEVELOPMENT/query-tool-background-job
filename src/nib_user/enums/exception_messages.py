from enum import Enum


class NIBUserExceptions(Enum):
    PERMSISSION_DENIED = "Permission Denied"
    NIB_USER_NO_NIB_NUMBER_FOUND = "No NIB number found for NIB User"
    NO_ROLES_FOUND = "User Roles Not Found"
    WRONG_TOKEN_USED = "User token was received admin token is required for this route"
    ROLE_DOESNT_EXIST = "Role does not exist"
    USER_DOESNT_EXIST = "User does not exist"
