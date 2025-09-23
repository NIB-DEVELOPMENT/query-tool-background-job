from functools import wraps
from src.nib_user.decorators.nib_user_role_decorator import roles_required
from src.nib_user.enums.customer_service_roles import CustomerServiceRoles
from src.nib_user.enums.family_island_roles import FamilyIslandRoles

def user_required():
    def wrapper(func):
        allowed_roles = [role.value for role in CustomerServiceRoles]
        allowed_roles.extend([FamilyIslandRoles.MANAGER.value, FamilyIslandRoles.SUB_OFFICE_MANAGER.value])
        @roles_required(allowed_roles)
        @wraps(func)
        def inner(*args, **kwargs):
            return func(*args, **kwargs)

        return inner

    return wrapper