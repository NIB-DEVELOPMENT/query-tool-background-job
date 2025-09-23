from functools import wraps
from src.nib_user.decorators.nib_user_role_decorator import roles_required
from src.nib_user.enums.customer_service_roles import CustomerServiceRoles
from src.nib_user.enums.it_roles import ITRoles
from src.nib_user.enums.family_island_roles import FamilyIslandRoles

def read_only():
    def wrapper(func):
        customer_service = [role.value for role in CustomerServiceRoles]
        it = [role.value for role in ITRoles]
        family_island = [role.value for role in FamilyIslandRoles]

        @roles_required(customer_service + it + family_island)
        @wraps(func)
        def inner(*args, **kwargs):
            return func(*args, **kwargs)

        return inner

    return wrapper