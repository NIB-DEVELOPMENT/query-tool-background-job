from functools import wraps
from typing import List
from flask_jwt_extended import get_jwt_identity,verify_jwt_in_request
from werkzeug.exceptions import Forbidden
from src.nib_user.enums.exception_messages import NIBUserExceptions

def roles_required(required_roles: List):
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            token = get_jwt_identity()
            if isinstance(token, str):
                raise Forbidden(NIBUserExceptions.WRONG_TOKEN_USED.value)
            if any(role in required_roles for role in token.get("roles")):
                return fn(*args, **kwargs)
            else:
                raise Forbidden(NIBUserExceptions.PERMSISSION_DENIED.value)
        return decorator

    return wrapper