# toolbox.py

from lexios.core.security import RolesVerification
from lexios.core.logger import CustomLogger
from lexios.core.thread import LexiAssistantThread

class MakeToolBox():
    # Creates a tailored toolbox for a thread
    # Checks every object for roles and security management

    def __call__(
            self,
            thread: LexiAssistantThread
    ):
        # Definitions needed at setup
        from lexios.integrations.virtual_agents import VirtualAgentsRouter as Router

        # Create a list of tools available for the assistant:
        tools = []

        # Add openAi built-in code interpreter function:
        if thread.code_interpreter_active:
            tools.append({"type": "code_interpreter"})

        # Add openAi built-in data retrieval function:
        if thread.retrieval_active:
            tools.append({"type": "retrieval"})

        # Load system required commands 
        thread.toolbox.update(thread.lexi.required_commands)

        # External Commands:
        for command in thread.toolbox.values():
            
            try:

                # Exceptions or more specific rules

                # Filter routing commands for agents that cannot be replaced
                if thread.can_be_replaced is False and (
                    command.name == Router.route_to_main_assistant.__name__ or
                    command.name == Router.route_to_virtual_agent.__name__
                ):
                    continue # skip command

                # For background assistants, filter commands not allowed in background 
                if thread.run_in_background and not command.allowed_in_background:
                    
                    continue # skip command

                # Verify if the command is required at lexios level
                required = command.name in thread.lexi.required_commands
        
                if not required:

                    # Run verification
                    try:
                        verified = RolesVerification()(
                            user= thread.user_id, 
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
                    log.error(f"Security: User {thread.user_id} {e}")
        
        return tools