import os
import openai
import aioredis
import json
from io import BytesIO
from datetime import timedelta

from lexios.settings.main import *
from lexios.api.session_manager import LexiSessionManager
from lexios.core.lexi_base_tools import *
from lexios.core.external_command import LexiExternalCommand
from lexios.core.task_scheduler import LexiTaskScheduler

# Lexi's Engines 
from lexios.core.builtin.engines.SQLEngine import LexiDatabase
from lexios.core.builtin.engines.searchEngine import SearchEngine
from lexios.core.builtin.engines.userDataEngine import UserDataManager

# Built-in tools
from lexios.core.builtin.functions.calendar import GoogleCalendar
from lexios.core.builtin.functions.email import GmailClient 

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
        self.append_basic_IO()

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

    async def prepare_output(
            self, *args: str, 
            session_id = None, 
            spell=True, 
            user_id=None,
            conversation_id=None, 
            msg_type= "text", 
            images = None,
            metadata= None
        ):
        
        # process outbound messages to the user interface
        # msg_type : "text", "sys_notif", 

        try:
            # Prepare outbound message
            session_id = self.users.get(user_id).session_id

            outbound_message = {
                    "session_id" : str(session_id),
                    "conversation_id": conversation_id,
                    "msg_type": msg_type,
                    "metadata": metadata,
                    "spell": spell,
                }

            # Convert all elements to strings
            args = [str(arg) for arg in args]  
            # Try to make a string with the args
            message = " ".join(args)

            # Command line output:
            if self.command_line is True:
                print(f"{self.lexi_prompt} {message}")

            outbound_message['content'] = message
    
            # Images
            if images:
                outbound_message['images']  = images

            # Send message using broker
            async with aioredis.from_url(self.broker_url) as broker:
                await broker.publish("fastapi_channel", json.dumps(outbound_message))

        except Exception as e:
            print("Problems with sending the message: ", e)

    def append_basic_IO(self):

        # Append internal basic I/O methods / protocols

        # Time / Location:
        self.append_command(
            LexiExternalCommand(
                func=SearchEngine.time_and_location,
                show_return_to_user=False
            )
        )

        if SEARCH_ENGINE:
            # Search on the Internet:
            self.append_command(
                LexiExternalCommand(
                    func=SearchEngine.bing_search,
                    printer=SearchEngine.bing_search_printer,
                    show_return_to_user=False,
                )
            )
            # Extract URL content:
            self.append_command(
                LexiExternalCommand(
                    SearchEngine.access_website_content, show_return_to_user=False
                )
            )
            # Read a RSS channel:
            self.append_command(
                LexiExternalCommand(SearchEngine.read_rss, show_return_to_user=False)
            )
            # Check Stock prices:
            self.append_command(
                LexiExternalCommand(SearchEngine.get_stock_price_by_symbol, show_return_to_user=False)
            )
            # Check Weather Forecast:
            self.append_command(
                LexiExternalCommand(
                    SearchEngine.get_weather_forecast, 
                    show_return_to_user=False,
                    before="Weather data by Open-Meteo.com")
            )
            # Schedule an action:
            self.append_command(
                LexiExternalCommand(
                    LexiTaskScheduler.schedule_new_action, show_return_to_user=False
                )
            )
        
        if USER_DATA_MANAGER:
            # Create reminders, alarms, alerts
            self.append_command(
                LexiExternalCommand(
                    UserDataManager.schedule_reminder,
                    requires_dynamic_object=UserDataManager,
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                )
            )
            # Delete reminders, alarms, alerts
            self.append_command(
                LexiExternalCommand(
                    UserDataManager.delete_reminder,
                    requires_dynamic_object=UserDataManager,
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                )
            )
            # Create other user specific data
            self.append_command(
                LexiExternalCommand(
                    UserDataManager.add_user_specific_data,
                    requires_dynamic_object=UserDataManager,
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                )
            )
            # Retrieve the current categories for user_specific_data
            self.append_command(
                LexiExternalCommand(
                    UserDataManager.retrieve_user_data_categories,
                    requires_dynamic_object=UserDataManager, 
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                    allowed_in_background= True,
                )
            )
            # Retrieve all the content related to a certain category
            self.append_command(
                LexiExternalCommand(
                    UserDataManager.read_user_data_category_content, 
                    requires_dynamic_object=UserDataManager, 
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                    allowed_in_background= True,
                )
            )
            # Retrieve a specific data element by its data_id
            self.append_command(
                LexiExternalCommand(
                    UserDataManager.retrieve_user_data_content_by_id, 
                    requires_dynamic_object=UserDataManager, 
                    show_return_to_user=False,
                    session_data_check="lexi_learns",
                    allowed_in_background= True,
                )
            )
           
            # Create automated email responses 
            self.append_command(
                LexiExternalCommand(
                    UserDataManager.create_automated_email_response_rule, 
                    requires_dynamic_object=UserDataManager, 
                    show_return_to_user=False,
                    session_data_check="gmail_access",
                )
            )

            # Send email
            send_email_command = LexiExternalCommand(
                    GmailClient.send_email, 
                    requires_dynamic_object=GmailClient, 
                    show_return_to_user=False,
                    session_data_check="gmail_access",
                )
            
            # Load a dynamic scope
            send_email_command.load_scope(
                scope_name= "send_email_response",
                template= "Send automated e-mail to '{to_address}'.",
                vars = ["to_address"],
            )

            self.append_command(send_email_command)

            # Seacrh for a contact
            self.append_command(
                LexiExternalCommand(
                    GmailClient.search_email_by_name, 
                    requires_dynamic_object=GmailClient, 
                    show_return_to_user=False,
                    session_data_check="gmail_access",
                )
            )
            # Create automated email responses 
            self.append_command(
                LexiExternalCommand(
                    GoogleCalendar.create_google_calendar_event, 
                    requires_dynamic_object=GoogleCalendar, 
                    show_return_to_user=False,
                    session_data_check="google_calendar_access",
                )
            )

    def set_up_db_integration(self):
        # Sets up the integration steps for exchanging data with a local database

        if DATABASE_TOOLS:
            try:

                for db_connection in self.databases_list:
                    self.sql_engine = LexiDatabase(**db_connection.settings)

                if self.sql_engine:
                # Get a Database Entity Relationship Diagram - ERD
                    self.append_command(
                        LexiExternalCommand(
                            LexiDatabase.retrieve_database_erd,
                            requires_object=self.sql_engine,
                            show_return_to_user= False
                        )
                    )

                    # Execute queries in the Database & exctract results
                    self.append_command(
                        LexiExternalCommand(
                            LexiDatabase.execute_fetch_sql_query,
                            requires_object=self.sql_engine,
                            show_return_to_user= False
                        )
                    )

                    if MINING_TOOLS:
                        # Execute queries in the Database & exctract results
                        self.append_command(
                            LexiExternalCommand(
                                LexiDatabase.show_predictive_models_for_table,
                                requires_object=self.sql_engine,
                                show_return_to_user= False
                            )
                        )
                        
                        # Run automated data analysis on tables
                        if self.sql_engine.table_analyzer:
                            # The SQL Engine provides a customized external command with additional content when executed
                            self.append_command(
                                self.sql_engine.table_analyzer
                            )

                        # Make predictions using a model
                        self.append_command(
                            LexiExternalCommand(
                                LexiDatabase.make_prediction_using_model,
                                requires_object=self.sql_engine,
                                show_return_to_user= False
                            )
                        )   


            except Exception as e:
                print(f"Lexi- Problem setting up SQL / Mining features:{e}")

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
        session_id: str = None, 
        conversation_id: str = None,
        data = None, 
        filename = None, 
    ) -> str:
        
        if isinstance(data, dict):
            try:
                # Data package overrides default user
                user_id = data['user_id']
            except KeyError:
                pass

            try:
                # conversation_id
                conversation_id = data['conversation_id']
            except KeyError:
                pass

            # session_id
                session_id = data['session_id']
            except KeyError:
                pass

            try:
                # Text input
                user_input = data['user_input']
            except KeyError:
                pass

            try:
                # File attachments
                filename = data['filename']
            except KeyError:
                pass


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
                        await thread.new_user_message(user_input, filename)
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
                            'session_id': session_id,
                            'user_id': user_id,
                            'model': self.model,
                            'tools': self.toolbox,
                            'lexi': self,
                            'instructions': self.instructions
                        }
                    )
                    if thread.running_stat == "ready":
                        # Send the message to the initiated Thread
                        await thread.new_user_message(user_input, filename)

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
    

