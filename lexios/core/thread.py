#thread.py
import openai
from typing import Optional, Union
from admin.verify_folder import find_project_folder

from lexios.core.common_tools import *
from lexios.core.builtin.functions.greetings import greetings

PROJECT_FOLDER = find_project_folder()

class LexiAssistantThread():
    """ Represents a conversation with the user.

        Can handle multiple assistants, having set a static root assistand given
        by Lexi. If agent routing settings are enabled, it loads an additional 
        assistant than can be replaced several times along the conversation. 

    """
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
        pre_loaded_assistant_id: str = None, 
        pre_loaded_thread_id: str = None, 

    ) -> None:
        # Call the __init__ methods of the base classes
        super().__init__() 
          
        # Imports needed only by  LexiThread __init__()
        from lexios.core.toolbox import ToolBox
        from lexios.core.thread_loading import load_assistant_and_orm_data
        from lexios.frontend.session_data import read_session_data_from_backend
        from lexios.database.users import get_user_data_by_user_id

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

        # Virtual Agents - Preloaded Assistant Id
        self.pre_loaded_assistant_id = pre_loaded_assistant_id
        self.pre_loaded_thread_id = pre_loaded_thread_id
      
        # Specify if the thread can be replaced for another virtual agent 
        self.can_be_replaced = can_be_replaced
        
        # Assistant name determination
        if name:
            # Set a specific name for this assistant
            self._name_ = name
        else:
            self._name_ = self.lexi.name
        
        # Virtual Agent Name means this is a system created thread
        self.virtual_agent_name = virtual_agent_name
        if virtual_agent_name:
            self._name_ = virtual_agent_name
        
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
        self.root_toolbox = toolbox
        self.loaded_toolbox = toolbox
        
        # Security: Validate tools authorized for this thread
        self.root_tools  = ToolBox()(self)
        # Load tools
        self.loaded_tools = self.root_tools

        # Thread specific instructions:
        self.instructions = instructions

        self.conversation_orm = None

        # Load conversation data from DB if any
        load_assistant_and_orm_data(self, restore_conversation)
        
        # Assistant files
        self.assistant_files = []

        # Update the first message for the assistant
        self.user_message = user_message
        self.message_to_agent = None

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

        # Keep a counter of unanswered requests
        self.nr_retries = 0

        ## Final verifications ##

        # Verifiy root assistant is loaded if not a main virtual agent
        if not self.root_assistant and not self.virtual_agent_name:
            LexiException("At Thread init(). Something went wrong on loading the root assistant.")
        
        # If a thread was recovered and loaded, verify consistency
        self.verify_consistency()

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

    async def process_input(
            self, 
            message: str = None, 
            file:str = None, 
            request: Optional[Union[VirtualAgentRequested, MainAssistantRequested]] = None,
        ):  
            """
            Handles the execution of an external Run. 
            

            """
            # Child methods
            from lexios.core.thread_loading import update_thread_messages, render_annotations
            from lexios.core.function_calling import create_tool_calls, attend_tool_calls, submit_function_outputs
            from lexios.core.downloads import manage_downloads, manage_links
            from lexios.core.thread_conversations import generate_conversation_name
            

            try:
                if message:
                    # Update user message, attaching the name to give a special touch
                    self.user_message = f"User {self.session_data.name_first}: '{message or ''}'" 

                # Log message on console
                LexiLogging(f"User Id: {self.user_id}: Processing message: {self.user_message[:10]}...")

                # First check the status 

                # Signal its busy attending a request
                self.running_stat = "processing"

                # clear the thread refrence if there is a reset signal request
                if self.reset_signal:
                    self.loaded_thread = None
                    self.reset_signal = False

            
                # Define scpecific instructions for the run
                instructions = "\n".join(
                    (
                    f"Your name is {self._name_}.\n",
                    self.instructions,
                    str(self.metadata()),
                    )
                )

                # Routing requests
                
                # Clear just in case
                self.message_to_agent = None
                
                if request:

                    # Generate an automatic salutation when switching assistants
                    salutation = greetings(agent_name=self.virtual_agent_name or LEXI_ALIAS, 
                                            user_name=self.session_data.name_first or None
                                )
                    
                    # Determine the kind of opening an agent will have in a conversation
                    if (isinstance(request, VirtualAgentRequested) 
                        and hasattr(request, 'just_say_hi')
                        and request.just_say_hi is True
                    ):
                        # Render the automated salutation 
                        await frontend_output(
                            content = salutation,
                            user_id= self.user_id, 
                            conversation_id= self.conversation_id,
                            alias= self._name_,
                        )

                        # End and await for further user input
                        self.running_stat = "ready"
                        return

                    # Elaborate a context for the agent to follow up on an specific topic
                    elif isinstance(request, (VirtualAgentRequested, MainAssistantRequested)):

                        # Create a context for the next virtual agent using a predefined template
                        message_from_prev_agent = (
                            
                            # Context #
                            f"\nIMPORTANT:\n"
                            f"This conversation is being routed to you by request of virtual agent {request.from_agent}. \n"
                            f"Details:\n"
                            f"User '{self.session_data.name_first}', Original request: '{request.user_message}'.\n"
                            f"Prev. generated metadata: '{request.information}'.\n"
                            # New directives #
                            f"DIRECTIVES:\n"
                            f"Start with this '{salutation}' or resolving user's request."
                        )
                    
                        # Append new instructions for the virtual agent taking over the conversation
                        self.message_to_agent = "\n".join((instructions, message_from_prev_agent))

                        # Load the previous message from the user
                        message = None

                # Update messages in Thread:
                if message or file or self.message_to_agent:
                    try:
                        await update_thread_messages(self, message, file, 
                                                     message_to_agent= self.message_to_agent)
                    except ValueError as e:
                        raise LexiException("Could not update messages in Thread.")
                
                if message or self.message_to_agent:
                    try:
                        # Run the thread
                        self.run = openai.beta.threads.runs.create(
                            thread_id=self.loaded_thread.id,
                            assistant_id=self.loaded_assistant.id,
                            model=self.model,
                            instructions= instructions,
                        )
                    except Exception as e:
                        raise LexiException(f"At create process input, creating Run, "
                                    f"user_id {self.user_id} message {self.user_message} {e}")
                        

                    # Main loop to treat a Thread - Run
                    while self.run.status not in ("completed", "cancelled", "failed", "expired"):

                        # Await for Run to change status
                        while self.run.status in ("queued", "in_progress"):

                            # Retrieve run status:
                            self.run = openai.beta.threads.runs.retrieve(
                                thread_id=self.loaded_thread.id, run_id=self.run.id
                            )

                        # Log run status
                        LexiLogging(f"User Id: {self.user_id} run Status: '{self.run.status}' "
                                    f"Last Error: '{self.run.last_error or 'No errors'}'.")
                        
                        # Check if the run failed
                        if self.run.status == 'failed':
                            raise LexiException(f"openai: {self.run.last_error}")

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
                                and self.run 
                                and self.run.status == "requires_action"
                            ):
                                
                                if not self.run_in_background:
                                    # Log entry
                                    with CustomLogger("messages") as log:
                                        log.debug("System", details={"from": self._name_, 
                                            "content": assistant_reply, "filtered": True})
                                
                                    
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
    
                        # Check for requested tools:
                        if (self.run.status == "requires_action" and 
                            self.run.required_action.type == "submit_tool_outputs"):

                                # Create required tool calls:
                                await create_tool_calls(self)

                                # Attend calls generated:
                                # Inse this method the external commands are being executed
                                await attend_tool_calls(self)        

                                # When all calls are completed, submit tool_function_outputs:
                                submit_function_outputs(self)

                                # Update Run status:
                                self.run = openai.beta.threads.runs.retrieve(
                                    thread_id=self.loaded_thread.id, run_id=self.run.id
                                )
                                # Clear to_dos:
                                self.tool_calls = []


            # Virtual Agent was solicited 
            except VirtualAgentRequested as request:
                if self.can_be_replaced:
                    # Change the status to "on hold" during the routing
                    self.running_stat = "on hold"
                    # Cancel the current run
                    self.cancel_run()
                    # Mark as changed to save in db
                    raise

            # Root assistant requested
            except MainAssistantRequested as request:
                if self.virtual_agent_name and self.can_be_replaced:
                    # Change the status to "on hold" during the routing
                    self.running_stat = "ready"
                    # Cancel run
                    self.cancel_run()
                    # Load root assistant
                    self.load_root_assistant(request)
            
            except Exception as e:
                    
                    # Inform the user about the problem:
                    if not self.run_in_background:
                        await frontend_output(
                            "I'm sorry, there was a problem processing your last request. Please try again...", 
                            user_id = self.user_id,
                            conversation_id=self.conversation_id,
                            alias= self._name_
                        )

                    # Let know the LexiOS component   
                    raise LexiException(f"Problem running thread. Details: {e}", WARNING)
            
            finally:

                # Verify the consistency of the thread after execution
                if (self.run and self.run.status in ('required_action', 'in_progress') 
                    or self.running_stat == 'inconsistent'
                ):

                    # Keep on hold
                    self.running_stat = "on_hold"
                    # Cancel run
                    try:
                        self.verify_consistency()

                    except Exception as e:
                        self.running_stat = "unexpected_error"

                # Release the LexiAssistant to attend new requests  
                elif self.run and self.run.status in ("completed", "cancelled", "failed", "expired"): 
                    self.running_stat = "ready"
                    
                    # Autogenerate conversation title
                    if self.run.status == "completed" and not self.title_generated and \
                    not self.run_in_background:

                        # Generate name, update title
                        await generate_conversation_name(self)
                
                # For cases where a run was no needed
                else:
                    self.running_stat = "ready"

                    # End of Run execution
                    # Save the response generated, used for background tasks

                    if self.run_in_background:

                        self.response = {
                            'status': self.run.status,
                            'output': assistant_reply,
                        }

                        # Return the response
                        return self.response
                    
            
    # Update conversation ORM
    def save_message(self, message: str, source: str= "system",type: str = "text", metadata: any = None):

        if not self.run_in_background:
            try:
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

            except Exception as e:
                raise LexiException(f"Thread.save_message() {e}")

            finally:
                # Flag for saving
                self.has_changed = True

    # Load the main assiatant
    def load_root_assistant(self, agent_request: MainAssistantRequested):

        from lexios.core.thread_conversations import save_conversation

        try:
            self.running_stat = "loading"

            # Reset virtual agent
            self.virtual_agent_name = None

            # Load the root assistant context
            self._name_ = self.lexi.name
            self.loaded_assistant = self.root_assistant
            self.loaded_thread = self.root_thread
            self.loaded_tools = self.root_tools
            self.loaded_toolbox = self.root_toolbox
            self.has_changed = True
            
            # Try to save conversation
            save_conversation(self)
        
        except Exception as e:
            pass

        finally:
            self.running_stat = "ready"

        # Check if there is any information to start a new run 
        if agent_request.user_message:
            # Notify lexiOs
            raise agent_request

    # Load the context of a virtual agent
    def load_virtual_agent(self, agent: 'LexiAssistantThread', request: VirtualAgentRequested):

        from lexios.core.thread_conversations import save_conversation
        
        try:
            self.running_stat = "loading"

            # Virtual agent name
            self._name_ = agent.virtual_agent_name

            # Overwrite assistant related data
            self.virtual_agent_name = agent.virtual_agent_name
            self.loaded_tools = agent.root_tools
            self.loaded_toolbox = agent.root_toolbox
            self.loaded_thread = agent.loaded_thread
            self.loaded_assistant = agent.loaded_assistant
            self.instructions = agent.instructions
            self.assistant_files = agent.assistant_files
            self.model = agent.model
            self.can_be_replaced = agent.can_be_replaced
            self.has_changed = True

            # Update fields in the ORM
            self.conversation_orm.model_loaded_assistant_id = agent.loaded_assistant.id
            self.conversation_orm.model_loaded_thread_id = agent.loaded_thread.id if agent.loaded_thread else None
            self.conversation_orm.virtual_agent_name = agent.virtual_agent_name

            # Try to save in changes db (there is a chance the conversation does not exist in DB yet, that is expected.)
            try:
                save_conversation(self, push= True)
            except Exception as e:
                pass

        except Exception as e:
            with CustomLogger("lexios") as log:
                log.error(f"At Thread, loading virtual agent: {e}")
        
        finally:
            # Reset running status just in case
            self.running_stat = "ready"

    def cancel_run(self, run_id: str = None):
        """ 
        Cancel the current thread run

        - run_id: str The id of the Run object.
        """ 
        run_id = run_id or (self.run.id if self.run else None)
        
        if (run_id or (self.run 
                       and self.run.status in ["queued", "in_progress", "requires_action"])):

            try:
                status = "started"

                # Cancel current run
                openai.beta.threads.runs.cancel(
                    thread_id=self.loaded_thread.id,
                    run_id=run_id,
                )

                status = "finished"

            except openai.BadRequestError:
                with CustomLogger("openai") as log:
                    log.warning("At cancel run:", WARNING, e)
                
                status = "finished"

            except Exception as e:
                status = "failed"
                raise LexiException("At cancel run:", WARNING, e)
            
            finally:
                if status == "finished":
                    self.running_stat = "ready"
    
    def verify_consistency(self):
        # Checks if there are runs open for the object and closes them
        try:
            # Verification started
            status = "started"

            if self.loaded_thread:

                runs_data = openai.beta.threads.runs.list(thread_id= self.loaded_thread.id)

                # Extract the list
                runs = runs_data.data

                # Verify is a list
                if isinstance(runs,list):

                    for run in runs:
                        # If the run is in an inconsistent status,
                        if run.status in ("in_progress", "queued", "requires_action"):

                            # Cancel the run
                            self.cancel_run(run_id = run.id)

                            # Log the inconsistency
                            LexiLogging(f"User Id: {self.user_id}. Inconsistency detected. Cancelling run.")

            # Verification is finished        
            status = "finished"

        except openai.BadRequestError:
            pass
        except Exception as e:
            raise LexiException(f"At verify_consistency().. {e}.", DEBUG)
        finally:
            if status == "finished":
                self.running_stat = "ready"
            else:
                self.running_stat = "inconsistent"


