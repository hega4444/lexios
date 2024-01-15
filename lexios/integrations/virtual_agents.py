# virtual_agent.py
import asyncio
from typing import List
from uuid import uuid4

from lexios.settings.main import LEXI_GPT_MODEL
from lexios.core.signatures import _LexiOS_Backend
from lexios.core.external_command import LexiExternalCommand
from lexios.core.logger import CustomLogger, DEBUG, ERROR, WARNING
from lexios.core.messages_backend import frontend_output
from lexios.core.exceptions import VirtualAgentRequested, MainAssistantRequested, LexiException
from lexios.globals import GENERAL_VIRTUAL_AGENT

from lexios.integrations.plugin import PluginTemplate
from lexios.integrations.context import Context


_internal_id = 400

class VirtualAgent(PluginTemplate):
    # Create a virtual agent that interacts within the system

    def __init__(
            self, 
            name: str, 
            id: uuid4 = uuid4(),
            as_user_id: int = None, 
            instructions: str = None, 
            hidden: bool = False,
            full_access = False,
            can_be_cloned = False,
            can_be_replaced = True,
            roles : List[str] = None,
            retrieval: bool = False,
            interpreter: bool = False,
            ref_assistant_id: uuid4 = None, 
            
        ) -> None:

        self.id = id
        self.status = "initiated"

        self.commands = None
        self.resources = None
        self.instructions = instructions
        self.name = name
        self.hidden = hidden
        self.lexi_thread = None

        # Assistant_id
        self.ref_assistant_id = None

        # Open AI Assistant Builtin Tools
        self.retrieval = retrieval
        self.interpreter = interpreter

        # Custom toolbox for agent
        self.toolbox = {}

        # Asks for the complete toolbox available in lexios
        self.full_access = full_access

        # Can be cloned:
        self.can_be_cloned = can_be_cloned
        # Defines whether the agent can have multiple instances, meaning an assistant will be created
        # with the agent specifications and loaded into the user thread.
        # False = The agent takes requests sequentially and acts as a single identity.
        # True = The agent loads in each thread that requests it ans creates new specific context to append in the conversation.
        
        # Can be replaced:
        self.can_be_replaced = can_be_replaced
        # Defines whether the agent can be overwritten by other agents 
        # False = The agent is loaded in the thread permanently
        # True = The agent can be overwritten by a subsequent routing command

        # Roles it will act on behalf
        self.roles = roles or ['virtual_agent_access']

        # Determine the identity of the virtual agent system wise
        if as_user_id:
            # Use specific credentials (have to be previuosly set up at admin)
            self.as_user_id = as_user_id
        else:
            # General virtuaL agent
            self.as_user_id = GENERAL_VIRTUAL_AGENT

        # Call construtor of the PluginTemplate class
        super().__init__(plugin_name= "VirtualAgent")

    async def attend_request(
            self, 
            message: str, 
            from_user_id: int = None,
            from_conversation_id: str = None,
            session_data= None,
            callback: bool = False
        
        ):
        # Send a message to the virtual agent

        try:
            if self.lexi_thread:

                if session_data:
                    message = f"message from {session_data.name_first}: {message}"

                await self.lexi_thread.process_input(message)

                # Retrieve output
                response = self.lexi_thread.response

                if response.get("status") == "completed":

                    plain_text = response.get('output')
                    # Parse response
                    parsed_response = plain_text.replace("\n", "<br>")

                    if not callback:

                        await frontend_output(
                            content = parsed_response,
                            user_id=from_user_id,
                            conversation_id=from_conversation_id,
                            alias= self.name,
                        )
                    
                    # Callback requests
                    else:
                        # Return the generated response to the source agent
                        return parsed_response

                else:
                    raise ValueError("Could not process virtual agent request.")
                
        except Exception as e:
            pass

    def define_instructions(self, instructions: str):
        self.instructions = instructions

    def append_command(self, command):

        if not self.commands:
            self.commands = {}
        
        # Append the command to the virtual agent
        self.commands[command.name] = command

    def append_resource(self, resource: any):

        if not self.resources:
            self.resources = []
        
        self.resources.append(resource)

    def hide(self):
        self.hidden = True
    
    def unhide(self):
        self.hidden = False

    def start_agent_thread(self, lexi: _LexiOS_Backend):
        # Start virtual agent
        try:
            # Build the LexiThread 
            self.lexi_thread= self.build(lexi)

            # Change status
            self.status = "ready"
        
        except LexiException as e:
            self.status = "load_failed"


    def build(self, lexi: _LexiOS_Backend):

        global _internal_id

        if self.full_access:
            tools = lexi.toolbox
        else:
            tools = self.toolbox

        # Request Lexi to build the LexiThread needed
        try:
            thread = lexi.build_thread(
                user_id= self.as_user_id,
                conversation_id= str(_internal_id).zfill(3),
                virtual_agent=self,
            )
            
            # Update internal range
            _internal_id += 1
            
            return thread
        
        except Exception as e:
            raise LexiException(f"Building virtual agent: {e}.")

  
    def clone(self, lexi):
        # Check if cloning feature is allowed

        if not self.can_be_cloned:
            raise AttributeError("can_be_cloned is set to False, change to True for enabling cloning.")
        
        # Clone the thread by passing its reference or returning a new copy
        if self.lexi_thread:
            last_agent_instance = self.lexi_thread
            # Clear the reference so on the next request a new model is built
            self.lexi_thread = None,
            # Return the instance
            return last_agent_instance
        else:
            # Return a new copy
            return self.build(lexi)
        
class VirtualAgentsRouter():

    _virtual_agents = None
    _agent_names = None

    def __init__(self, virtual_agents: list = None, context: Context = None):
        # Initialization logic
        
        if virtual_agents:
            VirtualAgentsRouter._virtual_agents = virtual_agents
            VirtualAgentsRouter._agent_names = [agent.name for agent in VirtualAgentsRouter._virtual_agents] if virtual_agents else []
  
        if context:
            # Save the context 
            self.context = context

    async def route_to_virtual_agent(self, virtual_agent_name: str, message: str, no_callback: bool = True):
        # SUMM: Forward the user input to another virtual assistant listed on the available options.
        # virtual_agent_name 'description': Virtual assistant name that will receive the message.
        # callback 'description' : <default>True: Next assistant takes over conversation with user. False: await results from virtual agent.

        agent = self.by_name(virtual_agent_name)
        if agent:
                
            # Send message to virtual agent
            agent_task = asyncio.create_task(
                agent.attend_request(
                    message= message,
                    from_user_id= self.context.user_id,
                    from_conversation_id= self.context.conversation_id,
                    session_data= self.context.user,
                    # Convert the callback parameter, seems to work better this way
                    callback= not no_callback,
                )
            )

            # Request for the virtual agent to take over
            if no_callback and self.context.can_be_replaced and agent.can_be_cloned:

                with CustomLogger("lexios") as log:
                    log.debug(f"Routing user_id {self.context.user_id} to virtual agent {agent.name}.")

                # Raise an exception to handle the take over process
                raise VirtualAgentRequested(name=agent.name)
                        
            else:
                # Wait for the agent to process its output and return to the source LexiThread
                agent_response = await agent_task
                return agent_response
                
        return f"Virtual agent {virtual_agent_name} not found. These are the valid agent names: {self.agent_names}"
    
    def route_to_main_assistant(self, information: str = None):
        # SUMM: Use when assistant cannot complete user request and requires a higher level of supervision. 
        # information 'description': include any relevant data that can help the main assistant to find a better solution.

        with CustomLogger("lexios") as log:
            log.debug(f"Routing user_id {self.context.user_id} to root assistant.")

        # Raise Exception
        raise MainAssistantRequested(
                            agent=self.context.virtual_agent_name,
                            information= information,
                            user_message= self.context.user_message,
        )


    def by_name(self, agent_name: str, _default: any = None) -> VirtualAgent:

        for agent in self._virtual_agents:
            if agent.name.lower() == agent_name.lower():

                return agent
        
        return _default

if __name__ == "__main__":

    command = LexiExternalCommand(VirtualAgentsRouter.route_to_virtual_agent)

    names = ['Clarisa']

    command.add_key_spec("virtual_agent_name", "enum", names)

    print(command)