# toolbox.py
from typing import List, Union, Dict

from lexios.core.external_command import LexiExternalCommand
from lexios.frontend.session_data import LexiSessionData
from lexios.core.security import RolesVerification
from lexios.core.logger import CustomLogger

class UserToolBox():
    # Creates a tailored toolbox for a thread
    # Checks every object for roles and security management

    def __call__(
            self,
            lexi, 
            user: LexiSessionData, 
            commands: dict = None, 
            background_thread: bool = False, 
            setup: dict = None,
    ):

        # Create a list of tools available for the assistant:
        tools = []

        # Add openAi built-in code interpreter function:
        if setup.get("code_interpreter", False):
            tools.append({"type": "code_interpreter"})

        # Add openAi built-in data retrieval function:
        if setup.get("retrieval", False):
            tools.append({"type": "retrieval"})

        # Load system required commands 
        commands.update(lexi.required_commands)

        # External Commands:
        for command in commands.values():
            
            try:
                
                # For background assistants, filter commands not allowed in background 
                if background_thread and not command.allowed_in_background:
                    continue

                # Verify if the command is required at lexios level
                required = command.name in lexi.required_commands

                if not required:

                    # Run verification
                    try:
                        verified = RolesVerification()(
                            user=user, 
                            roles_required=command.roles_required,
                            session_data_check=command.session_data_check,
                        )
                    except PermissionError:
                        verified = False

                if required or verified:
                    # If the verification is ok then add to the current toolbox
                    tools.append(dict(command.specs))
                    
            except Exception as e:
                with CustomLogger("security") as log:
                    log.error(f"Security: User {user.user_id} {e}")
        
        return tools