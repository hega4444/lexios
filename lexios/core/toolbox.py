# toolbox.py
from typing import List

from lexios.core.common_tools import CustomLogger, LexiException, LEXI_ALIAS
from lexios.core.thread import LexiAssistantThread
from lexios.core.security import RolesVerification
from lexios.core.agents_router import AgentsRouter


class ToolBox():
    """
     - Creates a tailored toolbox for a thread.
     - Checks every LexiExternalCommand object for roles and security control.

     Parameters: 
     - tehad (LexiAssistantThread) : The thread to be checked.

     Returns:
     - A list of tools descriptions to be shared with the AI model.

    """

    def __call__(
            self,
            thread: LexiAssistantThread
    ) -> List[str]:
        # Definitions needed at setup

        # Create a list of tools available for the assistant:
        tools = []

        # Add openAi built-in code interpreter function:
        if thread.code_interpreter_active:
            tools.append({"type": "code_interpreter"})

        # Add openAi built-in data retrieval function:
        if thread.retrieval_active:
            tools.append({"type": "retrieval"})

        # Load system required commands 
        thread.root_toolbox.update(thread.lexi.required_commands)

        # External Commands:
        for command in thread.root_toolbox.values():
            
            try:
                # Specific for root assistant (agent Lexi) Remove route to main assistant
                if ((thread.virtual_agent_name is None or
                    thread.virtual_agent_name.lower() == LEXI_ALIAS.lower() ) 
                    and 
                    command.name == AgentsRouter.route_to_main_assistant.__name__ ):

                    continue # exclude command

                # Verify if the command is required at lexios level
                required = command.name in thread.lexi.required_commands

                if required:

                    # Filter routing commands for agents that cannot be replaced
                    if thread.can_be_replaced is False and (
                        command.name == AgentsRouter.route_to_main_assistant.__name__ or
                        command.name == AgentsRouter.route_to_virtual_agent.__name__
                    ):
                        continue # exclude command

                # For background assistants, filter commands not allowed in background 
                elif thread.run_in_background and not command.allowed_in_background:
                    
                    continue # exclude command
    
                else:
                    # Run verification
                    try:
                        verified = RolesVerification()(
                            user= thread.session_data, 
                            roles_required=command.roles_required,
                            session_data_check=command.session_data_check,
                        )
                    except PermissionError:
                        verified = False

                if required or verified:
                    # If the verification is ok then add to the current toolbox
                    tools.append(dict(command.specs))
                    
            except Exception as e:
                with CustomLogger("lexios") as log:
                    log.error(f"At Toolbox: User {thread.user_id} Details: {e}")
        
        return tools