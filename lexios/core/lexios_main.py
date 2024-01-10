# lexios_main.py
import os
import openai

import json
from datetime import timedelta

from lexios.settings.main import *
from lexios.api.session_manager import LexiSessionManager
from lexios.core.lexi_base_tools import *
from lexios.core.external_command import LexiExternalCommand
from lexios.core.task_scheduler import LexiTaskScheduler
from lexios.core.lexios_builtin import append_basic_IO
from lexios.core.logger import CustomLogger


class LexiOS_Backend(LexiBaseTools):
    # This class is capable of managing the whole communication with a chat model integrating external functions, access to real-time data
    # and NLP capabilities.

    def __init__(
            self, 
            model: str = LEXI_GPT_MODEL, 
            instructions=None, 
            active_users=None,
    ):
        
        super().__init__()

        self.model = model
        self.lexi_instance_id = self.get_last_instance_id()
        self.toolbox = {}
        self.generated_prompt = None

        # Adjust time settings:
        self.time_zone = TIME_ZONE
        self.time_delta = timedelta(minutes= TIME_DELTA )

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
        else:
            print("API key not found.")

        # Define output methods:
        self.define_output_methods(command_line=True, backend=BROKER_PATH)

        # Set up LexiScheduler:
        self.scheduler = LexiTaskScheduler(lexi=self)

        # Add Lexi built- in functions:
        append_basic_IO(self)

        # Set up SQL Engine:
        # List of databases Lexi is connecting to
        self.databases_list = None
        self.sql_engine = None 


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

    def append_command(self, command: LexiExternalCommand) -> bool:
        # Append command to catalog
        self.toolbox[command.name] = command
        
    def get_last_instance_id(self):
        sesid_file = "data/sesid.txt"

        # Get the absolute path to the 'data' folder
        data_folder = os.path.abspath("data")

        # Ensure that the 'data' folder exists; create it if it doesn't
        if not os.path.exists(data_folder):
            os.makedirs(data_folder)

        # Try to read the existing SESID from the file
        try:
            with open(sesid_file, "r") as file:
                sesid = int(file.read().strip())
        except FileNotFoundError:
            # If the file does not exist, start with SESID 1
            sesid = 1

        # Perform any necessary operations with sesid
        sesid += 1
        # Save the updated SESID back to the file
        with open(sesid_file, "w") as file:
            file.write(str(sesid))

        return sesid

        return json.dumps({"table": data}, indent=4)

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
                        await self.prepare_output(
                            "I'm still processing your last request. Just a moment please...", 
                            user_id= user_id,
                            conversation_id= conversation_id
                        )
                
                else:
                    # No thread found, create the first one
                    thread = self.session_manager.new_lexi_thread(
                        user_id = user_id,
                        conversation_id = conversation_id,
                        args = {
                            'conversation_id' : conversation_id,
                            'user_id': user_id,
                            'model': self.model,
                            'tools': self.toolbox,
                            'lexi': self,
                            'instructions': self.instructions
                        }
                    )
                    if thread.running_stat == "ready":
                        # Send the message to the initiated Thread
                        await thread.process_input(user_input, filename)

        except Exception as e:
            await self.prepare_output(
                f"Seems that there is a problem... {e}", 
                user_id=user_id,
                conversation_id=conversation_id
            )

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
    

