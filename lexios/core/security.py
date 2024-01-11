# security.py
from typing import List

from lexios.database.roles import get_assigned_roles_by_user_id
from lexios.frontend.session_data import LexiSessionData
from lexios.core.logger import CustomLogger

class LexiAccessControl():

    def __init__(self, user: LexiSessionData, roles_required: List[str] = None, session_data_check = None ):

        self.verification = False

        # Example: Get user roles from the token
        user_roles = get_assigned_roles_by_user_id(user.user_id)

        if session_data_check:
            try:
                # Read the attribute, it has to be boolean type
                self.verification = getattr(user, session_data_check)

                if not isinstance(self.verification, bool):
                    raise ValueError
                
                if not self.verification:
                      raise PermissionError("Permission denied")
            
            except Exception as e:
                with CustomLogger("security") as log:
                    log.warning(f"Attribute {session_data_check} is not present in session data. Permission denied. Check command {e}")
                
                raise PermissionError(f"Permission denied with errors, {e}")
        
        if self.verification and roles_required:
            # Default role needed for not registered objects
            roles_required = ["user_access"] 

            # Check if user has required roles
            if not any(role.name in roles_required for role in user_roles):
                raise PermissionError("Permission denied")     
    
        # If nothing trigerred ań error till now, then set verification status to True
        self.verification = True

    def __call__(self):
        return self.verification
