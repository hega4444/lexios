# toolbox.py
from typing import List

from lexios.core.external_command import LexiExternalCommand
from lexios.frontend.session_data import LexiSessionData
from lexios.core.security import LexiAccessControl
from lexios.core.logger import CustomLogger


class UserToolBox():

    def __init__(
            self, 
            user: LexiSessionData, 
            commands: List[LexiExternalCommand], 
            setup: dict
    ) -> None:
        
        self.setup = setup
        self.user = user
        self.ext_commands = commands
        self.tool_specs_output = None

    def __call__(self):

        # Create a list of tools available for the assistant:
        tools = []

        # Add openAi built-in code interpreter function:
        if self.setup.get("code_interpreter", False):
            tools.append({"type": "code_interpreter"})

        # Add openAi built-in data retrieval function:
        if self.setup.get("retrieval", False):
            tools.append({"type": "retrieval"})

        # External Commands:
        for command in self.ext_commands.values():
            
            try:

                # For background assistants, filter commands not allowed
                if self.setup.get("run_in_background", False) and not command.allowed_in_background:
                    continue
                
                verification = LexiAccessControl(
                    user=self.user, 
                    roles_required=command.roles_required,
                    session_data_check=command.session_data_check,
                )()

                if verification:
                    # If the verification is ok then add to the current toolbox
                    tools.append(dict(command.specs))
                    
            except PermissionError as e:
                with CustomLogger("security") as log:
                    log.warning(f"User: {self.user.user_id} command:{command.name}. Permission denied.")
        
        return tools