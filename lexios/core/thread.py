#thread.py
import openai

from admin.verify_folder import find_project_folder

from lexios.frontend.session_data import read_session_data_from_backend
from lexios.database.users import get_user_data_by_user_id
from lexios.core.common_tools import *
from lexios.core.function_calling import create_tool_calls, attend_tool_calls, submit_function_outputs
from lexios.core.downloads import manage_downloads, manage_links
from lexios.core.thread_messages import update_thread_messages, restore_conversation_data, render_annotations
from lexios.core.conversations import generate_conversation_name
from lexios.core.messages_backend import prepare_output

from lexios.core.toolbox import UserToolBox
from lexios.core.logger import CustomLogger


PROJECT_FOLDER = find_project_folder()

class LexiAssistantThread():
    # Represents one conversation with the user

    def __init__(
        self,
        lexi=None,
        user_id: str = None,
        user_message: str = None,
        files=None,
        model=None,
        tools=None,
        instructions = None,
        conversation_id = None,
        restore_conversation = None,
        title_generated = False,
        run_in_background= False,

    ) -> None:
        # Call the __init__ methods of the base classes
        super().__init__() 

        # Core object Lexi:
        self.lexi = lexi

        # User thread
        self.thread = None
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.assistant = None

        # Reset signal, will create a new thread on the next Run execution
        self.reset_signal = False

        # Running status
        self.running_stat = "ready"
        # Flag for checking if the conversation was updated
        self.has_changed = False 

        # Context for the Thread:
        self.run_in_background = run_in_background
        self.model = model

        # First try to get a fresh copy fronm the backend
        session_data = read_session_data_from_backend(user_id)
        if not session_data:
            session_data = get_user_data_by_user_id(self.user_id)

        # Create the toolbox for the thread
        self.tools = UserToolBox(
            user = session_data,
            commands= tools,
            setup={
                "run_in_background": run_in_background,
                "code_interpreter": True,
                "retrieval" : True,
            }
            )()

        # Thread specific instructions:
        self.instructions = instructions

        self.conversation_orm = None
        # Load conversation data from DB if any

        restore_conversation_data(self, restore_conversation)
        
        # Assistant files
        self.assistant_files = []

        # Update the first message for the assistant
        self.user_message = user_message

        # Tool_calls:
        self.tool_calls = []
        self.tool_calls_status = None

        # Conversation title status
        self.title_generated = title_generated
        if restore_conversation:
            self.title_generated = True

        # Consent dialog screen
        self.consent_dialog = None

        # Run
        self.run = None

    async def process_input(self, message: str = None, file:str = None):
        # Handles the execution of an openai Run 

        # clear the thread refrence if there is a reset signal request
        if self.reset_signal:
            self.thread = None
            self.reset_signal = False

        self.running_stat = "processing"

        # Process a new message (creates a Run)
        # Update messages in Thread:
        try:
            if message or file:
                try:
                    await update_thread_messages(self, message, file)
                except ValueError as e:
                    raise ValueError("Could not update messages in Thread.")
            
            if message:
                try:
                    # Define scpecific instructions for the run
                    instructions = str(self.metadata()) + self.instructions

                    # Run the thread
                    self.run = openai.beta.threads.runs.create(
                        thread_id=self.thread.id,
                        assistant_id=self.user_assistant.id,
                        model=self.model,
                        instructions= instructions,
                    )

                except Exception as e:
                    with CustomLogger("assistants") as log:
                        log.debug(f"Problem updating executing Thread for User_id: {self.user_id}. Details:{e}")

                    raise ValueError(
                        f"'process_run' could not execute this Run. Details: {e}"
                    )

                # Main loop to treat a Thread - Run
                while self.run.status not in ["completed", "cancelled", "failed", "expired"]:


                    # Await for Run to change status
                    while self.run.status in ["queued", "in_progress"]:

                        # Retrieve run status:
                        self.run = openai.beta.threads.runs.retrieve(
                            thread_id=self.thread.id, run_id=self.run.id
                        )

                    # Log run status
                    with CustomLogger("lexios") as log:
                        log.info(f"run object status - User: {self.user_id} Status:{self.run.status} Message:{self.user_message} Last Error: {self.run.last_error}")
                    
                    # Check if the run failed
                    if self.run.status == 'failed':
                        raise ValueError(f"openai: {self.run.last_error}")

                    # Recover meesages from the model
                    messages = openai.beta.threads.messages.list(thread_id=self.thread.id)

                    # Update conversation_orm
                    try:
                        self.conversation_orm.model_messages = messages
                    except Exception:
                        pass # just in case the user sent an attachment without any message

                    # Recover the text response from messages
                    assistant_reply = messages.data[0].content[0].text.value
                    
                    if assistant_reply:

                        # Replace annotations if included in the message
                        # Also get attachment references if any
                        assistant_reply, attachments  = manage_downloads(self, messages.data[0])

                        assistant_reply, links = manage_links(assistant_reply)

                        # If the Run requires action and shows some echo message, filter it:
                        if (
                            self.lexi.filter_echo is True
                            and assistant_reply == message
                            and self.run.status == "requires_action"
                        ):
                            # Log entry
                            with CustomLogger("messages") as log:
                                log.debug("new message", details={"from": "lexi", "content": assistant_reply, "filtered": True})
                        
                                
                        elif not self.run_in_background:

                            # Update conversation ORM
                            self.conversation_orm.app_messages_content.append({
                                    'source':'system',
                                    'type': 'text', 
                                    'time': format_datetime(str(datetime.now()))[:-3],
                                    'text':assistant_reply,
                                }
                            )
                            self.has_changed = True
                            
                            # Render text output
                            await prepare_output(self.lexi, assistant_reply, user_id=self.user_id, conversation_id=self.conversation_id)

                            # Render annotations
                            await render_annotations(self, links, attachments)

                            # Log entry
                            with CustomLogger("messages") as log:
                                log.debug("new message", details={"from": "lexi", "content": assistant_reply, "filtered": False})


                    # Check for requested tools:
                    if self.run.status == "requires_action":

                            # Create required tool calls:
                            await create_tool_calls(self)

                            # Attend calls generated:
                            await attend_tool_calls(self)

                            # When all calls are completed, submit tool_function_outputs:
                            submit_function_outputs(self)

                            # Update Run status:
                            self.run = openai.beta.threads.runs.retrieve(
                                thread_id=self.thread.id, run_id=self.run.id
                            )
                            # Clear to_dos:
                            self.tool_calls = []

        except Exception as e:
                
                # Inform the user about the problem:
                if not self.run_in_background:
                    await prepare_output(
                        self.lexi, 
                        "I'm sorry, there was a problem processing your last request. Please try again...", 
                        user_id = self.user_id,
                        conversation_id=self.conversation_id
                    )
                with CustomLogger("lexios") as log:
                    log.error(f"At running thread. User:{self.user_id}. Details {e}")

                # Let know the LexiOS component   
                raise ValueError(f"Problem running thread. Details: {e}")
        
        finally:
            # Release the LexiAssistant to attend new requests    
            self.running_stat = "ready"
        
        # Autogenerate conversation title
        if self.run.status == "completed" and not self.title_generated and \
        not self.run_in_background:

            # Generate name, update title
            await generate_conversation_name(self)


        # End of Run execution
        # Save the response generated, used for background tasks

        if self.run_in_background and self.run.status in ["completed", "cancelled", "failed", "expired"]:

            self.response = {
                'status': self.run.status,
                'output': assistant_reply,
            }
           
    def metadata(self):
        # Prepare metadata, information that can enhance the quality of the assistant replies:
        week_day = curr_day_short()
        date_time, tzcode = get_adjusted_time()
        date_time = date_time.strftime("%Y-%m-%d %H:%M:%S")
        metadata = {
            "current_date_time": f"{week_day} {date_time}",
            "time_zone": f"{tzcode}",
        }

        return metadata  # Return as a dictionary, not as a JSON string