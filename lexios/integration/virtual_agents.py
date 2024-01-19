# virtual_agent.py
import asyncio
from typing import Any, List
from uuid import uuid4
from abc import abstractmethod

from lexios.core.common_tools import frontend_output
from lexios.settings.main import LEXI_ALIAS
from lexios.core.signatures import _LexiOS_Backend
from lexios.core.logger import CustomLogger, DEBUG
from lexios.core.exceptions import LexiException
from lexios.globals import GENERAL_VIRTUAL_AGENT

from lexios.integration.plugin import PluginTemplate
from lexios.integration.trustedActions import TrustedAction


class VirtualAgent(PluginTemplate):
    # Create a virtual agent that interacts within the system

    # Agents have conversation_id ranging above 400 for easier identification
    _internal_id = 401
    agents = {}

    def __init__(
            self, 
            name: str, 
            id: uuid4 = None,
            as_user_id: int = None, 
            instructions: str = None, 
            description: str = None,
            hidden: bool = False,
            request_full_access = False,
            can_be_cloned = False,
            can_be_replaced = True,
            roles : List[str] = None,
            retrieval: bool = False,
            interpreter: bool = False,
            ref_assistant_id: uuid4 = None, 
            pre_loaded_assistant_id = None,
            pre_loaded_thread_id = None,
             
        ) -> None:

        # Generate a new Token identification for security
        self.id = None

        # Name
        self.name = name

        # Define a unique channel for this agent
        self.channel = VirtualAgent._internal_id
        VirtualAgent._internal_id +=1

        # Define a graph of nodes agents can access
        self.neighbors = []

        # Add the agent to the dictionary
        VirtualAgent.agents[self.channel] = self

        # Lexi (or alias) always gets the channel 400
        if name.lower() == LEXI_ALIAS.lower():
            self.channel = 400

        self.ref_assistant_id = ref_assistant_id
        self.status = "initiated"

        # Define commands it can execute & resources it can access
        self.commands = None
        self.resources = None
        
        # Define instructions & description
        self.instructions = instructions
        self.description = description 

        # Hidden status 
        self.hidden = hidden
        
        # Service thread
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

        # Define a preloaded OpenAi assistant if you have trained one
        self.pre_loaded_assistant_id = pre_loaded_assistant_id
        self.pre_loaded_thread_id = pre_loaded_thread_id

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

        # A wildcard reference to the backend, the field is actually initiated at
        # method start_service()

        self.lexi : _LexiOS_Backend = None

        # Call construtor of the PluginTemplate class
        super().__init__(plugin_name= "VirtualAgent")

    
    def add_relationship(self, other_agent: 'VirtualAgent'):
        # Add a relationship between two agents
        self.neighbors.append(other_agent)

        # Return the other agent reference so it allows to create a chain of
        # interactions
        return other_agent

    def get_neighbors(self)-> List['VirtualAgent']:
        # Get neighbors of the agent
        return self.neighbors
    
    def remove_relationship(self, other_agent: 'VirtualAgent'):
        # Remove a relationship between two agents
        if other_agent in self.neighbors:
            self.neighbors.remove(other_agent)

    
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
            from_agent: 'VirtualAgent' = None,
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
        # Append other plugins or more advanced components, still on the cook
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

            # Save the reference to lexi
            self.lexi = lexi

            # Build the LexiThread 
            self.main_thread= self.build(lexi)

            # Change status
            self.status = "ready"
        
        except LexiException as e:
            self.status = "load_failed"
            raise LexiException(f"Virtual agent {self.name} problems starting service. {e}")
        
    # Create a copy of the asistant
    def _clone(self, lexi):
        # Check if cloning feature is allowed

        if not self.can_be_cloned:
            raise AttributeError("can_be_cloned is set to False, change to True for enabling cloning.")

        if self.hidden:
            raise AttributeError("hidden is set to True, change to False for enabling cloning.")
        
        # Increment the counter 
        self.nr_copies += 1     
        # Return a new copy
        return self.build(lexi)
    

    @abstractmethod
    async def before_closing_event(self, action: TrustedAction):
        """
        Defines en entrypoint to act before a command (action) is executed.  

        Abstract method to be implemented by child classes.

        Parameters:
          - action (TrustedAction): Context of the execution.
        """
        pass

    @abstractmethod
    async def after_closing_event(self, action: TrustedAction):
        """
        Defines en entrypoint to act after a command (action) is executed.  

        Abstract method to be implemented by child classes.

        Parameters:
        - action (TrustedAction): Context of the execution.
        """
        pass

