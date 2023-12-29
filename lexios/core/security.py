# security.py

from lexios.database.roles import get_assigned_roles_by_user_id
from lexios.api.session_data import LexiSessionData
from lexios.core.external_command import LexiExternalCommand


class LexiAccessControl():

    def __init__(self, user: LexiSessionData, security_obj:str ):

        # Example: Get user roles from the token
        user_roles = get_assigned_roles_by_user_id(user.user_id)

        if security_obj:
            pass
        else:
            # Default role needed for not registered objects
            required_roles = ["user_access"] 

        # Check if user has required roles
        if not any(role.name in required_roles for role in user_roles):
            raise PermissionError("Permission denied")

    def __call__(self):
        return True
