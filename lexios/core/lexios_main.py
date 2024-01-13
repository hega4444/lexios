# lexios_main.py
import os
import openai

from datetime import timedelta
from lexios.globals import Globals
from lexios.settings.main import *
from lexios.core.session_manager import LexiSessionManager
from lexios.core.common_tools import *
from lexios.core.external_command import LexiExternalCommand
from lexios.core.task_scheduler import LexiTaskScheduler
from lexios.core.logger import CustomLogger
from lexios.core.messages_backend import frontend_output
from lexios.core.exceptions import VirtualAgentRequested, MainAssistantRequested
from lexios.core.thread import LexiAssistantThread


class LexiOS_Backend():
    # This class is capable of managing the whole communication with a chat model integrating external functions, access to real-time data
    # and NLP capabilities.

    def __init__(
            self, 
            model: str = LEXI_GPT_MODEL, 
            instructions=None, 
            active_users=None,
            virtual_agents= None,
            databases = None,
    ):
        
        super().__init__()

        Globals(lexi=self)

        self.model = model
        self.toolbox = {}
        self.generated_prompt = None

        # Adjust time settings:
        self.time_zone = TIME_ZONE
        self.time_delta = timedelta(minutes= TIME_DELTA)

        # Admin Assistant True / False 
        # Use it to define an assistant role that manages the user Threads
        self.set_up_admin = False
        self.admin_assistant = None

        # Users - Lexi can manage multi-user conversations
        self.users = active_users
        # Threads
        self.open_threads = {}

        # Message broker
        self.broker_url = BROKER_URL

        # Session Manager
        self.session_manager = LexiSessionManager(self)

        # Settings for output messages:
        self.filter_echo = True # Filter assistant replies that are an echo of user input      
        self.command_line = True
        self.backend = None

        # Dictionary for prompts management:
        self.lexi_dictionary = {
            "lexi_assistant_role": (
                "You are a resourceful ai assistant."
                "You have real-time internet connectivity and can access various external resources, "
            ),
        }

        # Change prompt-instructions when chatting:
        if instructions is None:
            self.instructions = self.lexi_dictionary['lexi_assistant_role']
        else:
            self.instructions = instructions

        # Command line prompt settings:
        try:
            self.name = LEXI_ALIAS
        except Exception:
            self.name = "Lexi -virtual assistant-"

        self.lexi_prompt = f"{self.name}_>:"
        # Adjust temperature for chat model response
        self.temperature = LEXI_GPT_TEMPERATURE

        # Set up openAI and assistant

        # Load system variable with API KEY
        api_key = os.environ.get("MY_API_KEY")
        if api_key:
            # print("API key found!")
            openai.api_key = api_key

        elif OPENAI_KEY != "YOUR_KEY_HERE": 
            # Constant stored in settings comes second in priority
            openai.api_key = OPENAI_KEY
        
        else:
            # Not found - Shutdown
            with CustomLogger("lexios") as log:
                log.critical("API key not found.")
            
            sys.exit()

        # Define output methods:
        self.define_output_methods(command_line=True, backend=BROKER_PATH)

        # Set up LexiScheduler:
        self.scheduler = LexiTaskScheduler(lexi=self)

        # Commands needed for the system, creates the minimun toolbox
        self.required_commands = {}

        # Add Lexi built- in functions:
        from lexios.core.setup import append_basic_IO
        append_basic_IO(self)

        # Setup Virtual Agents
        self.virtual_agents = virtual_agents
        from lexios.core.setup import set_up_virtual_agents_and_routing
        set_up_virtual_agents_and_routing(self)

        # Setup SQL Engine:

        # List of databases Lexi is connecting to
        self.databases = databases

        # SQL Engine
        self.sql_engine = None

        from lexios.core.setup import set_up_db_integration
        set_up_db_integration(self)

    def set_up_admin_assistant(self):
        # Create a list of available tools for the Assistant
        toolbox = self.build_toolbox()

        # Create the Admin assistant role
        self.admin_assistant = openai.beta.assistants.create(
            instructions=self.instructions,
            name=self.name,
            tools=toolbox,
            model=self.model,
        )

    def define_output_methods(self, command_line=None, backend=None):
        # Determine the way Lexi will output messages to the user (command line / Websockets):
        if isinstance(command_line, bool):
            self.command_line = command_line
        if backend is not None:
            self.backend = backend

    def append_command(self, command: LexiExternalCommand, required_by_lexi: bool = False) -> bool:
        # Add key for the command to catalog
        self.toolbox[command.name] = command

        if required_by_lexi:
            # Save in separate toolbox
            self.required_commands[command.name] = command
    
    def build_toolbox(self, code_interpreter=True, retrieval=True):
        # Create a list of tools available for the assistant:
        tools = []

        # Add openAi built-in code interpreter function:
        if code_interpreter:
            tools.append({"type": "code_interpreter"})

        # Add openAi built-in data retrieval function:
        if retrieval:
            tools.append({"type": "retrieval"})

        # External Commands:
        for tool in self.toolbox.values():
            tools.append(dict(tool.specs))

        return tools

    def show_toolbox(self):
        for tool in self.toolbox.values():
            print(tool)

    async def process_user_request(
        self, user_input: str = None, 
        user_id: int = None, 
        conversation_id: str = None,
        data = None, 
        filename = None, 
    ) -> str:
        
        if isinstance(data, dict):
  
                # Data package overrides default user
                user_id = data.get('user_id', None)
                # conversation_id
                conversation_id = data.get('conversation_id', None)
                # Text input
                user_input = data.get('user_input', None)
                # File attachments
                filename = data.get('filename', None)

        try:
            # Check if admin assistant needs initialization
            if self.admin_assistant is None and self.set_up_admin is True:
                self.set_up_admin_assistant()

            # Check if the user has an initiated Thread already:
            user_profile = self.users.get(user_id, None)
            if user_profile:

                # Try to recover thread:
                thread = self.session_manager.get_thread(user_id, conversation_id)
                if thread:

                    # Thread found and ready, process new request
                    if thread.running_stat == "ready":
                        # Send the message to the corresponding Thread
                        await thread.process_input(user_input, filename)

                    else:

                    # Thread found but busy, inform the user on the chat interface
                        await frontend_output(
                            "I'm still processing your last request. Just a moment please...", 
                            user_id= user_id,
                            conversation_id= conversation_id
                        )
                
                else:
                    # No thread found, create one
                    thread = self.build_thread(
                        user_id = user_id,
                        conversation_id = conversation_id,
                    )

                    # Send the message to the initiated Thread as background task
                    await thread.process_input(user_input, filename)
        
        except MainAssistantRequested as request:
                await thread.process_input(from_agent=request)

        except VirtualAgentRequested as agent:
            # Route a thread to a Virtual Agent
            self.route_virtual_agent(thread, agent)

        except Exception as e:
            with CustomLogger("lexios") as log:
                log.error(f"At process_user_request: {e}")

    def reset_user_thread_request(self, user_id: str ='default', conversation_id='default') ->str:
        # Resets the user thread 
        try:
             # Check if the user has an initiated Thread already:
            user_profile = self.users.get(user_id, None)
            if user_profile:
                # Try to recover thread:
                thread = user_profile.active_threads.get(conversation_id, None)
                if thread:
                    thread.reset_signal = True
            
        except Exception:
            pass
    
    def route_virtual_agent(self, thread: LexiAssistantThread, agent: MainAssistantRequested):
        # Load an instance of a virtual agent
        
        # Find the agent
            agent = self.agents_router.by_name(agent.name)
            if agent:
                # Get a blank slate of a virtual agent
                cloned_virtual_agent = agent.clone(lexi=self)

                # Request the session manager to handle the transition
                thread.load_virtual_agent(cloned_virtual_agent)
    
    def build_thread(
            self, 
            user_id:int, 
            conversation_id:str, 
            virtual_agent = None,
            restore_conversation = None,
    ):
        # Builds a new thread
        try:
            # Baseline 
            thread_context = {
                        'lexi': self,
                        'user_id': user_id,
                        'conversation_id' : conversation_id,
                        'restore_conversation': restore_conversation,
                        'model': self.model,
                        'toolbox': self.toolbox,
                        'instructions': self.instructions,
                    }
            
            # Virtual Agent Setup
            if virtual_agent:  
                # Update with the agent context
                thread_context['virtual_agent_name']= virtual_agent.name
                thread_context['instructions'] = virtual_agent.instructions
                thread_context['toolbox'] = virtual_agent.toolbox
                thread_context['retrieval'] = virtual_agent.retrieval
                thread_context['interpreter'] = virtual_agent.interpreter
                thread_context['run_in_background'] = True
            
            # Restore conversation Setup
            if restore_conversation:
                thread_context['title_generated'] = True,
            
            # Return thread
            return LexiAssistantThread(**thread_context)
            
        except Exception as e:
            with CustomLogger("lexios") as log:
                log.error(f"at build_thread: {e}.")