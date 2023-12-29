# toolbox.py
from typing import List

from lexios.core.external_command import LexiExternalCommand
from lexios.api.session_data import LexiSessionData
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

    def create_thread_toolbox(self):

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
                verification = LexiAccessControl(user=self.user, security_obj=command.security_obj)()

                if verification:
                    tools.append(dict(command.specs))
                    
            except PermissionError as e:
                with CustomLogger("security") as log:
                    log.warning(f"User: {self.user.user_id} command:{command.name}. Permission denied.")
        
        return tools