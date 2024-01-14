#thread.py
import openai

from admin.verify_folder import find_project_folder

from lexios.core.signatures import _LexiAssistantThread
from lexios.frontend.session_data import read_session_data_from_backend
from lexios.database.users import get_user_data_by_user_id
from lexios.core.common_tools import *
from lexios.core.function_calling import create_tool_calls, attend_tool_calls, submit_function_outputs
from lexios.core.thread_messages import update_thread_messages, load_assistand_and_orm_data, render_annotations
from lexios.core.downloads import manage_downloads, manage_links
from lexios.core.conversations import generate_conversation_name, save_conversation
from lexios.core.messages_backend import frontend_output
from lexios.core.exceptions import VirtualAgentRequested, MainAssistantRequested, LexiException
from lexios.core.logger import CustomLogger, WARNING, ERROR

PROJECT_FOLDER = find_project_folder()

class LexiAssistantThread(_LexiAssistantThread):
    # Represents one conversation with the user

    # Imports required only by this class
    
    def __init__(
        self,
        lexi=None,
        user_id: str = None,
        user_message: str = None,
        files: list= None,
        model: str= None,
        toolbox: dict=None,
        instructions: str= None,
        conversation_id= None,
        restore_conversation = None,
        title_generated: bool = False,
        run_in_background: bool= False,
        name: str = None,
        virtual_agent_name: str = None,
        can_be_replaced: bool = True,
        retrieval: bool= False,
        interpreter: bool = False,

    ) -> None:
        # Call the __init__ methods of the base classes
        super().__init__() 
          
        # Imports needed only by __init__
        from lexios.core.toolbox import MakeToolBox

        # Set running status
        self.running_stat = "loading"

        # Core object Lexi:
        self.lexi = lexi
        
        # Main identifiers 
        self.user_id = user_id
        self.conversation_id = conversation_id

        # Root assistant
        self.root_assistant = None
        self.root_thread = None
        
        # Loaded thread
        self.loaded_assistant = None
        self.loaded_thread = None
      
        # Specify if the thread can be replaced for another virtual agent 
        self.can_be_replaced = can_be_replaced
        
        # Assistant name determination
        if name:
            # Set a specific name for this assistant
            self._name_ = name
        else:
            self._name_ = self.lexi.name
        
        self.virtual_agent_name = virtual_agent_name
        if virtual_agent_name:
            self._name_ = virtual_agent_name
        
        # Needed to transfer messages between threads
        self.buffered_last_message = None

        # Reset signal, will create a new thread on the next Run execution
        self.reset_signal = False

        # Flag for checking if the conversation was updated
        self.has_changed = False 

        # Context for the Thread:
        self.run_in_background = run_in_background
        self.model = model

        # First try to get a fresh copy fronm the backend
        self.session_data = read_session_data_from_backend(user_id)
        if not self.session_data:
            self.session_data = get_user_data_by_user_id(self.user_id)

        # Decide on activating model-builin-tools
        self.code_interpreter_active = interpreter
        self.retrieval_active = retrieval

        # Toolbox
        self.toolbox = toolbox
        
        # Security: Validate tools authorized for this thread
        self.root_tools = MakeToolBox()(self)

        # Load tools
        self.loaded_tools = self.root_tools

        # Thread specific instructions:
        self.instructions = instructions

        self.conversation_orm = None
        
        # Load conversation data from DB if any
        load_assistand_and_orm_data(self, restore_conversation)
        
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
        
        # Set to Ready
        self.running_stat = "ready"

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

    async def process_input(self, message: str = None, file:str = None, from_agent: MainAssistantRequested= None):
        # Handles the execution of an openai Run 

        from lexios.core.thread_messages import update_thread_messages, render_annotations

        # clear the thread refrence if there is a reset signal request
        if self.reset_signal:
            self.loaded_thread = None
            self.reset_signal = False

        self.running_stat = "processing"

        # Define scpecific instructions for the run
        instructions = "\n".join(
            (
            f"Your name is {self._name_}.\n",
            self.instructions,
            str(self.metadata()),
            )
        )

        # Give the context of a callback to the root assistant
        if from_agent:
            message_from_agent = (
                f"\nIMPORTANT!:\n"
                f"You are being summoned by virtual agent '{from_agent.name}' after failing to attend user request.\n"
                f"User '{self.session_data.name_first}' original request: '{from_agent.user_message}'.\n"
                f"Virtual agent metadata generated: '{from_agent.information}'.\n"
                )
            "\n".join((instructions, message_from_agent))

            # Update with user message that originated the callback
            message = from_agent.user_message           
            
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

                    # Run the thread
                    self.run = openai.beta.threads.runs.create(
                        thread_id=self.loaded_thread.id,
                        assistant_id=self.loaded_assistant.id,
                        model=self.model,
                        instructions= instructions,
                    )

                except Exception as e:
                    with CustomLogger("assistants") as log:
                        log.debug(f"Problem updating executing Thread foself.buffered_last_message r User_id: {self.user_id}. Details:{e}")

                    raise ValueError(
                        f"'process_run' could not execute this Run. Details: {e}"
                    )

                # Main loop to treat a Thread - Run
                while self.run.status not in ["completed", "cancelled", "failed", "expired"]:


                    # Await for Run to change status
                    while self.run.status in ["queued", "in_progress"]:

                        # Retrieve run status:
                        self.run = openai.beta.threads.runs.retrieve(
                            thread_id=self.loaded_thread.id, run_id=self.run.id
                        )

                    # Log run status
                    with CustomLogger("lexios") as log:
                        log.info(f"run object status - User: {self.user_id} Status:{self.run.status} Message:{self.user_message} Last Error: {self.run.last_error}")
                    
                    # Check if the run failed
                    if self.run.status == 'failed':
                        raise ValueError(f"openai: {self.run.last_error}")

                    # Recover meesages from the model
                    messages = openai.beta.threads.messages.list(thread_id=self.loaded_thread.id)

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
                            
                            if not self.run_in_background:
                                # Log entry
                                with CustomLogger("messages") as log:
                                    log.debug("System", details={"from": self._name_, "content": assistant_reply, "filtered": True})
                            
                                
                        elif not self.run_in_background:

                            # Update conversation ORM
                            self.save_message(assistant_reply)
                            
                            # Render assistant reply to frontend
                            await frontend_output(
                                content= assistant_reply, 
                                user_id= self.user_id, 
                                conversation_id= self.conversation_id,
                                alias= self._name_
                            )

                            # Render annotations
                            await render_annotations(self, links, attachments)

                            # Log entry
                            if not self.run_in_background:
                                with CustomLogger("messages") as log:
                                    log.debug("new message", details={"from": self._name_, "content": assistant_reply, "filtered": False})
   
                        if self.virtual_agent_name:
                            # Keep last message to save in the source conversation
                            self.buffered_last_message = assistant_reply

                    # Check for requested tools:
                    if self.run.status == "requires_action":

                            # Create required tool calls:
                            await create_tool_calls(self)

                            try:
                                # Attend calls generated:
                                await attend_tool_calls(self)

                            # Root assistant requested
                            except MainAssistantRequested as from_agent:
                                if self.virtual_agent_name and self.can_be_replaced:
                                    # Cancel run
                                    self.cancel_run()
                                    # Load root assistant
                                    self.load_root_assistant(from_agent)

                            # When all calls are completed, submit tool_function_outputs:
                            submit_function_outputs(self)

                            # Update Run status:
                            self.run = openai.beta.threads.runs.retrieve(
                                thread_id=self.loaded_thread.id, run_id=self.run.id
                            )
                            # Clear to_dos:
                            self.tool_calls = []

        # Virtual Agent was solicited 
        except VirtualAgentRequested as agent:
            if self.can_be_replaced:
                # Cancel the current run
                self.cancel_run()
                # Mark as changed to save in db
                self.has_changed = True
                # Propagate to lexios only after checking it can be replaced
                raise         

        except Exception as e:
                
                # Inform the user about the problem:
                if not self.run_in_background:
                    await frontend_output(
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
    
        # Update conversation ORM
    def save_message(self, message: str, source: str= "system",type: str = "text", metadata: any = None):
    
        record = {
            'source': source,
            'type': type, 
            'time': format_datetime(str(datetime.now()))[:-3],
            'text': message,
        }

        if metadata:
            record['metadata'] = str(metadata)

        if source == "system":
            record['alias'] = self._name_

        self.conversation_orm.app_messages_content.append(record)

        # Flag for saving
        self.has_changed = True
    
    def load_root_assistant(self, agent_request):
        #load the root assistant

        try:
            self.running_stat = "loading"

            # Reset virtual agent
            self.virtual_agent_name = None

            # Load the root assistant context
            self._name_ = self.lexi.name
            self.loaded_assistant = self.root_assistant
            self.loaded_thread = self.root_thread
            self.loaded_tools = self.root_tools
            self.has_changed = True
            
            # Try to save conversation
            save_conversation(self)
        
        except Exception as e:
            pass

        finally:
            self.running_stat = "ready"

        # Check if there is any information to start a new run 
        if agent_request.information:
            # Notify lexiOs
            raise agent_request

    def load_virtual_agent(self, agent: 'LexiAssistantThread'):
        # Load the context of a virtual agent
        
        try:
            self.running_stat = "loading"

            # Virtual agent name
            self._name_ = agent.virtual_agent_name

            # Overwrite assistant related data
            self.virtual_agent_name = agent.virtual_agent_name
            self.loaded_tools = agent.root_tools
            self.loaded_thread = agent.loaded_thread
            self.loaded_assistant = agent.loaded_assistant
            self.run = agent.run
            self.instructions = agent.instructions
            self.assistant_files = agent.assistant_files
            self.model = agent.model
            self.can_be_replaced = agent.can_be_replaced
            self.has_changed = True,

            # Append the last virtual agent response into this conversation
            self.save_message(agent.buffered_last_message)

            # Update fields in the ORM
            self.conversation_orm.model_loaded_assistant_id = agent.loaded_assistant.id
            self.conversation_orm.model_loaded_thread_id = agent.loaded_thread.id if agent.loaded_thread else None
            self.conversation_orm.virtual_agent_name = agent.virtual_agent_name

            # Try to save in changes db (there is a chance the conversation does not exist in DB yet, that is expected.)
            try:
                save_conversation(self)
            except Exception as e:
                pass

        except Exception as e:
            with CustomLogger("lexios") as log:
                log.error(f"Routing agent: {e}")
        
        finally:
            # Reset running status just in case
            self.running_stat = "ready"
        
    def cancel_run(self):
        # Cancel the run
        
        if self.run and self.run.status in ["queued", "in_progress", "requires_action"]:

            try:
                # Cancel current run
                openai.beta.threads.runs.cancel(
                    thread_id=self.loaded_thread.id,
                    run_id=self.run.id,
                )
            except Exception as e:
                raise LexiException("At cancel run:", WARNING, e)


