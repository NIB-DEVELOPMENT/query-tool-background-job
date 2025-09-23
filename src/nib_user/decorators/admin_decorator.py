from functools import wraps
from src.nib_user.decorators.nib_user_role_decorator import roles_required
from src.nib_user.enums.customer_service_roles import CustomerServiceRoles
from src.nib_user.enums.family_island_roles import FamilyIslandRoles


def admin_required():
    def wrapper(func):
        @roles_required(
            [
                CustomerServiceRoles.SUPERVISOR.value,
                CustomerServiceRoles.DEPARTMENT_HEAD.value,
                FamilyIslandRoles.MANAGER.value,
                FamilyIslandRoles.SUB_OFFICE_MANAGER.value,
            ]
        )
        @wraps(func)
        def inner(*args, **kwargs):
            return func(*args, **kwargs)

        return inner

    return wrapper
