# virtual_agent.py
import asyncio
from typing import List
from uuid import uuid4

from lexios.settings.main import LEXI_GPT_MODEL, LEXI_ALIAS
from lexios.core.signatures import _LexiOS_Backend
from lexios.core.external_command import LexiExternalCommand
from lexios.core.logger import CustomLogger, DEBUG, ERROR, WARNING
from lexios.core.messages_backend import frontend_output
from lexios.core.exceptions import VirtualAgentRequested, MainAssistantRequested, LexiException
from lexios.globals import GENERAL_VIRTUAL_AGENT

from lexios.integrations.plugin import PluginTemplate
from lexios.integrations.context import RunContext


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
            request_full_access = False,
            can_be_cloned = False,
            can_be_replaced = True,
            roles : List[str] = None,
            retrieval: bool = False,
            interpreter: bool = False,
            ref_assistant_id: uuid4 = None, 
            
        ) -> None:

        self.id = id
        self.ref_assistant_id = ref_assistant_id
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
        self.request_full_access = request_full_access

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
        self.roles = roles or ['virtual_agent']

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
        # Virtual Agent attends a request, originated either by an user or by other interface or 
        # Component.

        try:
            # Thread is loaded
            if self.lexi_thread:
                # Prepare a message to the virtual agent to give context.
                if session_data:
                    message = f"message from {session_data.name_first}: {message}"

                # Run Thread
                await self.lexi_thread.process_input(message)

                # Retrieve output
                response = self.lexi_thread.response

                # Check status
                if response.get("status") == "completed":
                    
                    # Extract the Virtual Agent reply
                    plain_text = response.get('output')
                    # Parse response
                    parsed_response = plain_text.replace("\n", "<br>")

                    if not callback:
                        # Render the response on the frontend
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
                    raise LexiException("Could not process virtual agent request.", DEBUG)
                
        except Exception as e:
            raise LexiException("Could not process virtual agent request.", DEBUG, e)

    def define_instructions(self, instructions: str):
        # Define the Virtual Agent instructions 
        # Go creative!
        self.instructions = instructions

    def append_command(self, command):
        # Append command to Agent ToolBox

        if not self.commands:
            self.commands = {}
        
        # Append the command to the virtual agent
        self.commands[command.name] = command

    def append_resource(self, resource: any):
        # Append other plugins or more advanced component, still on the cook
        # The resource should inherit from PluginTemplate
        # For now there are two resources:
        # 1 Virtual Agents
        # 2 Databases

        if not self.resources:
            self.resources = []
        
        self.resources.append(resource)

    def hide(self):
        # Remove agent from the Router is subscribed
        # Hidden agents cannot be cloned
        self.hidden = True
    
    def unhide(self):
        # Add agent to the Router's agent list
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
            raise LexiException(f"Virtual agent {self.name} problems starting service. {e}")
        

    def build(self, lexi: _LexiOS_Backend):
        # Build a copy of the model <assistant, instructions, tools>
        global _internal_id

        # Determine the initial scope of resources needed by the agent
        # This is just a request, all components go under security clearance
        # Except for the commands required by LexiOS, such as 'time_and_location'
        # Or routing commands to the Root assistant.

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

        if self.hidden:
            raise AttributeError("hidden is set to True, change to False for enabling cloning.")
        
        # Clone the thread by passing its reference or returning a new copy
        if self.lexi_thread:
            last_agent_instance = self.lexi_thread
            # Clear the reference so on the next request a new model is built
            self.lexi_thread = None
            # Return the instance
            return last_agent_instance
        else:
            # Return a new copy
            return self.build(lexi)
        
class VirtualAgentsRouter():

    _virtual_agents = None
    _agent_names = None

    def __init__(self, virtual_agents: list = None, context: RunContext = None):
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

        # Find the agent         
        agent = self.by_name(virtual_agent_name)
        if agent:
                    

            # Check is not already root or if it can be replaced
            if self.context.virtual_agent_name and self.context.virtual_agent_name.lower() == LEXI_ALIAS.lower():
                return f"You are at root level. Your alias is '{LEXI_ALIAS}'."

            # Check the requested agent is not already loaded
            elif self.context.virtual_agent_name and self.context.virtual_agent_name.lower() == virtual_agent_name.lower():
                return f"You are '{virtual_agent_name}'. These are the valid agent names: {self.agent_names}" 

            # Or cannot be replaced (settings on virtual agents)
            elif not self.context.can_be_replaced:
                return "You are currently set as the permanent assistant in this conversation. Routing service is Disabled."
        
            else:

                # Send message to virtual agent
                agent_task = asyncio.create_task(
                    agent.attend_request(
                        message= message,
                        from_user_id= self.context.user_id,
                        from_conversation_id= self.context.conversation_id,
                        session_data= self.context.user,
                        # Convert the callback parameter, seems to work better this way.
                        callback= not no_callback,
                    )
                )

            # Request for the virtual agent to take over
            if no_callback and self.context.can_be_replaced and agent.can_be_cloned:

                # Raise an exception to handle the take over process
                raise VirtualAgentRequested(name=agent.name)
                        
            else:
                # Wait for the agent to process its output and return to the source LexiThread
                agent_response = await agent_task
                return agent_response
        else:
            # Return Information about the current routes available from this node.   
            return (f"Virtual agent {virtual_agent_name} not found. These are the valid agent names: {self.agent_names}"
                    f"\n Root assistant alias is '{LEXI_ALIAS}'.")
        

    
    def route_to_main_assistant(self, information: str = None):

        # SUMM: Use when assistant cannot complete user request and requires a higher level of supervision. 
        # information 'description': include any relevant data that can help the main assistant to find a better solution.

        if self.context.virtual_agent_name and self.context.virtual_agent_name.lower() == LEXI_ALIAS.lower():
            return f"You are already the main-root assistant. Your name is '{LEXI_ALIAS}'."
        else:
            # Raise Exception
            raise MainAssistantRequested(
                                agent=self.context.virtual_agent_name,
                                information= information,
                                user_message= self.context.user_message,
            )


    def by_name(self, agent_name: str, _default: any = None) -> VirtualAgent:
        # Return a VirtualAgent by its label name
        for agent in self._virtual_agents:
            if agent.name.lower() == agent_name.lower():

                return agent
        
        return _default

if __name__ == "__main__":

    command = LexiExternalCommand(VirtualAgentsRouter.route_to_virtual_agent)

    names = ['Clarisa']

    command.add_key_spec("virtual_agent_name", "enum", names)

    print(command)