# security.py

import json
from cryptography.fernet import Fernet
from typing import List

from lexios.settings.main import GOOGLE_ID_SECURE_KEY
from lexios.database.users import validate_password_in_db
from lexios.database.roles import get_assigned_roles_by_user_id
from lexios.frontend.session_data import LexiSessionData
from lexios.core.session_manager import LexiSessionManager
from lexios.core.exceptions import LexiException, LexiWarning
from lexios.globals import ROOT_ID


# Role verification

class RolesVerification():
    """ Verifies the roles a user or virtual agent have defined to control access to commands & resources.
    """

    def __call__(self, user: LexiSessionData, 
                 roles_required: List[str] = None, 
                 session_data_check : str = None ):
        try:
            # Example: Get user roles from the token
            user_roles = get_assigned_roles_by_user_id(user.user_id)

            if session_data_check:
                try:
                    # Read the attribute, it has to be boolean type
                    verification = getattr(user, session_data_check, False)

                    if not isinstance(verification, bool):
                        raise LexiException(f"Attribute {session_data_check} is not "
                                             "bool type. Check security settings.")
                    
                    if verification is False:
                        raise PermissionError("Permission denied.")
                
                except Exception as e:
                    LexiWarning(f"Attribute {session_data_check} is not present in "
                                    f"session data. Permission denied. Check command {e}")
                    
                    raise PermissionError(f"Attribute {session_data_check} is not present "
                                          f"in session data. Permission denied. Check command {e}")
            
            if not roles_required:
                
                # Default role needed for unregistered objects
                roles_required = ["user"]
            
                # Check if is root
                if user.user_id == ROOT_ID:
                    return True

            # Check if user has required roles
            if not any(role.name in roles_required for role in user_roles):
                raise PermissionError("Permission denied.")     

            # if all checks are passed return True
            return True
        
        except PermissionError:
            raise

        except Exception as e:
            raise LexiException(f"Unexpected exception at Toolbox: User {user.user_id} Details: {e}")

# Password validation

class UserAuthentication():
    """ Validates user profile, and triggers the creation of a new Lexi account user correctly was succesfully
    identified with a Google Id.
    """

    def __call__(self, email, password, gmail_data = None):
        try:
            # Validates a user in the database and recovers their data

            user = validate_password_in_db(email=email, password=password)

            if user == 'NEW_GOOGLE_ACCOUNT':
                
                # Create a new account
                user = LexiSessionManager().new_lexi_account(email, password, gmail_data= gmail_data) 

            if user:
                
                # Get the content of the user before decryption
                user_dict = user.__dict__  

                if user.encrypted_google_details:
                    
                    cipher_suite = Fernet(GOOGLE_ID_SECURE_KEY)
                    decrypted_google_details = cipher_suite.decrypt(user.encrypted_google_details)

                    # Load decrypted gmail data
                    user_dict['google_details'] = json.loads(decrypted_google_details)

                # Create session_data
                session_data = LexiSessionData.model_validate(user.__dict__)
                return session_data
            
            else:
                raise PermissionError("Wrong credentials.")
        
        except Exception as e:
            LexiException(f"security.py, at UserAuthentication() {e} ")