# virtual_agent.py
import asyncio
from typing import Any, List
from uuid import uuid4

from lexios.settings.main import LEXI_ALIAS
from lexios.core.signatures import _LexiOS_Backend
from lexios.core.external_command import LexiExternalCommand
from lexios.core.logger import CustomLogger, DEBUG
from lexios.core.messages_backend import frontend_output
from lexios.core.exceptions import VirtualAgentRequested, MainAssistantRequested, LexiException
from lexios.globals import GENERAL_VIRTUAL_AGENT

from lexios.integration.plugin import PluginTemplate
from lexios.integration.context import RunContext

class Counter:

    _internal_id = 400

    def __init__(self):
        self.channel = Counter._internal_id

        Counter._internal_id += 1
    
    def __call__(self) -> Any:
        return self.channel


class VirtualAgent(PluginTemplate):
    # Create a virtual agent that interacts within the system

    # Define a channel (for now using the field conversation_id with a special range above 400)
    channel = Counter()()

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
        self.main_thread = None

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
        
        # Keep a counter of the number of copies this virtual agent has released
        self.nr_copies = 0
        
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
    
    def __call__(self, message: str, sync: bool = True):
        # Call a virtual agent from direclty by code

        # sync mode by default, wait for the response to continue processing your code
        if sync:
            # Create an event loop
            loop = asyncio.new_event_loop()

            # Run the asynchronous method in the event loop
            result = loop.run_until_complete(self.attend_request(
                message=message,
                callback= True,
            ))

            # Close the event loop
            loop.close()

            return result
        else:
            # In async mode the agent will execute commands in background withouth supervision until
            # it finishes executing the Run.
            self.attend_request(
                    message= message,
                    callback= True,
                )

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

        # Log the start of the service on console
        CustomLogger("lexios").info(f"Virtual agent {self.name} @ channel . {self.channel}. Processing new request.")
        try:
            # Thread is loaded
            if self.main_thread:
                # Prepare a message to the virtual agent to give context.
                if session_data:
                    message = f"message from {session_data.name_first}: {message}"

                # Run Thread
                response = await self.main_thread.process_input(message)

                # Check status
                if response.status == "completed":
                    
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

    # Build the thread
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
                conversation_id= self.channel,
                virtual_agent=self,
            )
            
            return thread
        
        except Exception as e:
            raise LexiException(f"Building virtual agent: {e}.")
    
    # Start the service
    def start_service(self, lexi: _LexiOS_Backend):
        # Start virtual agent
        try:
            # Build the LexiThread 
            self.main_thread= self.build(lexi)

            # Change status
            self.status = "ready"
        
        except LexiException as e:
            self.status = "load_failed"
            raise LexiException(f"Virtual agent {self.name} problems starting service. {e}")
        
    # Create a copy of the asistant
    def clone(self, lexi):
        # Check if cloning feature is allowed

        if not self.can_be_cloned:
            raise AttributeError("can_be_cloned is set to False, change to True for enabling cloning.")

        if self.hidden:
            raise AttributeError("hidden is set to True, change to False for enabling cloning.")
        
        # Increment the counter 
        self.nr_copies += 1     
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
    
    # Return a VirtualAgent by its label name
    def by_name(self, agent_name: str, _default: any = None) -> VirtualAgent:

        for agent in self._virtual_agents:
            if agent.name.lower() == agent_name.lower():

                return agent
        
        return _default
    
    # Route to main assistant
    def route_to_main_assistant(self, information: str = None):

        # SUMM: Use when assistant cannot complete user request and requires a higher level of supervision. 
        # information 'description': include any relevant data that can help the main assistant to find a better solution.

        if self.context.virtual_agent_name and self.context.virtual_agent_name.lower() == LEXI_ALIAS.lower():
            return f"You are already the main-root assistant. Your name is '{LEXI_ALIAS}'."
        else:
            # Raise Exception
            raise MainAssistantRequested(
                                user_message= self.context.user_message,
                                from_agent=self.context.virtual_agent_name,
                                information= information,                 
            )

    # Route to a virtual agent
    async def route_to_virtual_agent(self, virtual_agent_name: str, information: str= None, no_callback: bool = True):

        # SUMM: Forward the user input to another virtual assistant listed on the available options.
        # viertual_agent_name  'description' : Virtual assistant name that will receive the message.
        # information 'description' : A brief comment for the next agent to gain context on how to help the user.
        # no_callback 'description' : <default>True: Next assistant takes over conversation with user. False: await results from virtual agent.

        # Find the agent by its alias       
        agent = self.by_name(virtual_agent_name)
        if not agent:
            
            # Return Information about the current routes available from this node.   
            return (f"Virtual agent {virtual_agent_name} not found. These are the valid agent names: {self._agent_names}"
                    f"\n Root assistant alias is '{LEXI_ALIAS}'.")
                    
        # Check is not already root or if it can be replaced
        if self.context.virtual_agent_name and self.context.virtual_agent_name.lower() == LEXI_ALIAS.lower():
            return f"You are at root level. Your alias is '{LEXI_ALIAS}'."

        # Check the requested agent is not already loaded
        elif self.context.virtual_agent_name and self.context.virtual_agent_name.lower() == virtual_agent_name.lower():
            return f"You already are '{virtual_agent_name}'. List of valid agent names: {self._agent_names}." 

        # Or cannot be replaced (settings on virtual agents)
        elif not self.context.can_be_replaced:
            return "You are currently set as the permanent assistant in this conversation. Routing service is Disabled."
        
        # If requested for the root assistant, relay the message.
        elif virtual_agent_name.lower() == LEXI_ALIAS.lower():
            self.route_to_main_assistant()

        # Check if there is no need for callback, the current thread allows replacement and the agent allows cloning
        elif no_callback and self.context.can_be_replaced and agent.can_be_cloned:

            # Raise an exception to handle the take over process
            raise VirtualAgentRequested(  
                        from_agent= self.context.virtual_agent_name,
                        to_agent= agent.name,
                        user_message= self.context.user_message,
                        information = information,
            )

        else:
            # Create a request for the agent and await the response as if calling any other function
            agent_response = await asyncio.create_task(
                agent.attend_request(
                    message= information,
                    from_user_id= self.context.user_id,
                    from_conversation_id= self.context.conversation_id,
                    session_data= self.context.user,
                    # Negate the callback parameter, seems to work better this way.
                    callback= not no_callback,
                )
            )
            # Return the response inside the current thread
            return agent_response
        


if __name__ == "__main__":

    command = LexiExternalCommand(VirtualAgentsRouter.route_to_virtual_agent)

    names = ['Clarisa']

    command.add_key_spec("virtual_agent_name", "enum", names)

    print(command)