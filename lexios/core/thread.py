#thread.py

import openai
import pickle  # For pickling/unpickling the Python object

from lexios.database.models import Conversation 
from lexios.database.conversations import save_conversation_in_db, delete_conversation_in_db
from lexios.core.lexi_base_tools import *
from lexios.core.function_calling import ToolCall
from lexios.core.logger import CustomLogger


class LexiAssistantThread(LexiBaseTools):
    # Represents one conversation with the user

    def __init__(
        self,
        lexi=None,
        admin_assistant=None,
        user_assistant=None,
        user_id: str = None,
        session_id = None,
        user_message: str = None,
        files=None,
        tools=None,
        model=None,
        instructions = None,
        conversation_id = None,
        restore_conversation = False,
        app_messages_content = None,
        model_assistant_id = None,
        model_thread_id = None,
        metrics = None,
        conversation_orm = None,
        title_stat = 'new'

    ) -> None:
        # Call the __init__ methods of the base classes
        super().__init__() 

        # Core object Lexi:
        self.lexi = lexi

        # User thread
        self.thread = None
        self.user_id = user_id
        self.conversation_id = conversation_id

        # Session that is running this thread
        self.session_id = session_id

        # Reset signal, will create a new thread on the next Run execution
        self.reset_signal = False

        # Running status
        self.running_stat = "ready"
        # Flag for checking if the conversation was updated
        self.has_changed = False 

        # Context for the Thread:
        self.admin_assistant = admin_assistant
        self.model = model
        self.tools = self.lexi.build_toolbox()

        # Thread specific instructions:
        self.instructions = instructions

        if restore_conversation is True:
            # Try to retrieve assistant and thread data
            try:
                restore_assistant_failed = False
                assistant = openai.beta.assistants.retrieve(model_assistant_id)
                self.user_assistant = assistant
            except Exception as e:
                restore_assistant_failed = True   
            
            # Try to recover the thread
            try:
                restore_thread_failed = False
                thread = openai.beta.threads.retrieve(model_thread_id)
                self.thread = thread
            except Exception as e:
                restore_thread_failed = True
            
            if not restore_assistant_failed and not restore_thread_failed:
                self.conversation_orm = conversation_orm
                self.conversation_orm.app_messages_content = pickle.loads(self.conversation_orm.app_messages_content)

        if restore_conversation is False or restore_assistant_failed or restore_thread_failed:
            # Create the user_assistant role
            self.user_assistant = openai.beta.assistants.create(
                instructions=self.instructions,
                name=self.lexi.name,
                tools=self.tools, 
                model=self.lexi.model,
            )

            # Create new conversation model for the db
            self.conversation_id = conversation_id
            self.conversation_orm = Conversation(
                                        user_id= self.user_id,
                                        conversation_id= self.conversation_id,
                                        title = "new chat..",
                                        app_messages_content=[],
                                        model_assistant_id= self.user_assistant.id,
                                        model_thread_id= None,
                                        model_messages= None,
                                        metrics= None,
                                    )           

        # Assistant files
        self.assistant_files = []

        # Update the first message for the assistant
        self.user_message = user_message

        # Tool_calls:
        self.tool_calls = []
        self.tool_calls_status = None

    async def new_user_message(self, user_message: str = None, filename:str = None):
        # Handles the creation of a new Thread 
        if user_message or filename:

            # clear the thread refrence if there is a reset signal request
            if self.reset_signal:
                self.thread = None
                self.reset_signal = False

            self.running_stat = "processing"
            try:

                await self.run_loop(new_message= user_message,new_file= filename)

            except Exception as e:
                # Log the problem:
                with CustomLogger("threads") as log:
                    log.debug(f"user: {self.user_id}, details: {e}")

    async def run_loop(self, new_message: str = None, new_file: str = None):

        # Process a new message (creates a Run)
        # Update messages in Thread:
        try:
            if new_message or new_file:
                try:
                    self.update_thread_messages(new_message, new_file)
                except ValueError as e:
                    raise ValueError("Could not update messages in Thread.")
            
            if new_message:
                try:
                    # Run the thread
                    run = openai.beta.threads.runs.create(
                        thread_id=self.thread.id,
                        assistant_id=self.user_assistant.id,
                        model=self.model,
                        instructions=json.dumps(self.metadata()),
                    )
                except Exception as e:
                    with CustomLogger("assistants") as log:
                        log.debug(f"Problem updating executing Thread for User_id: {self.user_id}. Details:{e}")

                    raise ValueError(
                        f"'process_run' could not execute this Run. Details: {e}"
                    )

                # Main loop to treat a Thread - Run
                while run.status not in ["completed", "cancelled", "failed", "expired"]:
                    with CustomLogger("run_status") as log:
                        log.debug("run_status", details=run.model_dump_json)

                    # Await for Run to change status
                        while run.status in ["queued", "in_progress"]:

                            # Retrieve run status:
                            run = openai.beta.threads.runs.retrieve(
                                thread_id=self.thread.id, run_id=run.id
                            )

                    # After changes status, process
                    with CustomLogger("run_status") as log:
                        log.debug("run_status", details=run.model_dump_json)

                    # Recover meesages from the model to the user
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
                        assistant_reply, attachments  = self.replace_annotations(messages.data[0])

                        # If the Run requires action and shows some echo message, filter it:
                        if (
                            self.lexi.filter_echo is True
                            and assistant_reply == new_message
                            and run.status == "requires_action"
                        ):
                            # Log entry
                            with CustomLogger("messages") as log:
                                log.debug("new message", details={"from": "lexi", "content": assistant_reply, "filtered": True})
                        else:

                            # Update conversation ORM
                            self.conversation_orm.app_messages_content.append({
                                    'type':'assistant',
                                    'time': self.format_datetime(str(datetime.now()))[:-3],
                                    'message':assistant_reply,
                                }
                            )
                            self.has_changed = True
                            
                            # Process required outputs by Lexi settings:
                            await self.lexi.prepare_output(assistant_reply, user_id=self.user_id, conversation_id=self.conversation_id)

                            # Log entry
                            with CustomLogger("messages") as log:
                                log.debug("new message", details={"from": "lexi", "content": assistant_reply, "filtered": False})

                        # Handle attachments
                        if attachments:
                            for filename in attachments:

                                self.lexi.prepare_output(
                                    f'Download "{filename}"',
                                    user_id = self.user_id,
                                    conversation_id=self.conversation_id,
                                    msg_type = "sys_notif",
                                    spell = False,
                                    metadata = {
                                        "attachment" : attachments[filename]
                                        }
                                )

                    # Exit the loop in case of failure
                    if run.status == "failed":
                        break

                    # Check for requested tools:
                    if run.status == "requires_action":

                            # Create required tool calls:
                            self.create_tool_calls(run)

                            # Attend calls generated:
                            await self.attend_tool_calls()

                            # When all calls are completed, submit tool_function_outputs:
                            self.submit_function_outputs(run)

                            # Update Run status:
                            run = openai.beta.threads.runs.retrieve(
                                thread_id=self.thread.id, run_id=run.id
                            )
                            # Clear to_dos:
                            self.tool_calls = []

        except ValueError as e:
                # Inform the user about the problem:
                self.lexi.prepare_output(
                    "I'm sorry, there was a problem processing your last request. Please try again...", 
                    user_id = self.user_id,
                    conversation_id=self.conversation_id
                )
                # Let know the LexiOS
                raise ValueError(f"Problem running process_run. Details: {e}")

        # End of Run execution
        # Release the LexiAssistant to attend new requests    
        self.running_stat = "ready"

    def update_thread_messages(self, new_message = None, new_file = None):
        # Appends messages and attachments to the current user_thread

        if new_file:
            # Upload File:
            try:
                file_object = openai.files.create(
                        file = open(new_file, "rb"),
                        purpose= "assistants"
                    )
                
                # Make it an assistant-file:
                assistant_file = openai.beta.assistants.files.create(
                    assistant_id=self.user_assistant.id, 
                    file_id=file_object.id
                )


                assistant_files = openai.beta.assistants.files.list(self.user_assistant.id)
                print(assistant_files)
                
                # Log file upload:
                with CustomLogger("file_uploads") as log:
                    log.info(f"File {new_file} uploaded for user {self.user_id}")

                # Use os.path.basename to extract the filename
                filename = os.path.basename(new_file)

                #Notify the user:
                self.lexi.prepare_output(
                    f'File "{filename}" uploaded', 
                    user_id=self.user_id, 
                    conversation_id=self.conversation_id,
                    spell = False, 
                    msg_type="sys_notif"
                )

            except FileNotFoundError as e:
                # Log error
                with CustomLogger("file_uploads") as log:
                    log.error(f"Problem uploading file {new_file} for user {self.user_id}. Details: {e}")   

        # Text messages (with or without attachments):
        if new_message:

            # Update conversation ORM
            self.conversation_orm.app_messages_content.append({
                                    'type':'user',
                                    'time': self.format_datetime(str(datetime.now()))[:-3],
                                    'message':new_message,
                                }                    
            )
            self.has_changed = True

            # Check if message includes attachment:
            try:
                file_ref = assistant_file.id
            except Exception:
                file_ref = None

            if self.thread:
            # Check if the thread was already initiated.
                # If so, update messages:
                message_data = {
                    "thread_id": self.thread.id,
                    "role": "user",
                    "content": new_message,
                    "metadata": self.metadata(),
                }

                if file_ref is not None:
                    message_data["file_ids"] = [file_ref]

                try:
                    openai.beta.threads.messages.create(**message_data)

                except Exception as e:
                    raise ValueError(f"Problem updating thread. Message: {new_message}, Files: {new_file}. Details: {e}")
            else:
                try:
                    # Starts a Thread with a new message:
                    user_msg = {
                        "role": "user",
                        "content": new_message,
                    }

                    if file_ref is not None:
                        user_msg["file_ids"] = [file_ref]

                    self.thread = openai.beta.threads.create(
                        messages=[user_msg], metadata=self.metadata()
                    )

                    # Register thread in conversation ORM
                    self.conversation_orm.model_thread_id = self.thread.id

                except Exception as e:
                    raise ValueError(f"Problem creating thread. Message: {new_message}, Files: {new_file}. Details: {e}")
            
            with CustomLogger("messages") as log:
                log.debug("new message", details={"from": "user", "content": new_message, "metadata": self.metadata()})

        # Only file attachments:
        # New files need to be uploaded first, and then be linked to an assistant

        if new_file and not new_message:

            # Append message to Thread
            try:
                # Create a thread if there is no active one yet:
                if self.thread is None:
                    try:
                        msg_with_file = {
                            "role" : "user",
                            "files_id" : [file_ref],
                        }
                        # API call
                        self.thread = openai.beta.threads.create(
                            messages= msg_with_file,
                            metadata= self.metadata()
                            )
                        
                    except Exception:
                        raise ValueError(f"Problem creating thread. Message: '{new_message}'. Files: {new_file}. Details: {e}")

                # Append uploaded file to Thread
                self.assistant_files.append(new_file)

                with CustomLogger('messages') as log:
                    log.debug("new message", details={"from": "lexi", "file uploaded": filename})                    

            except Exception as e:
                with CustomLogger("assistants") as log:
                    log.debug(f"Problem attaching file {new_file} to assistant. User {self.user_id}. Details: {e}") 

                raise ValueError(f"Problem attaching file {new_file} to Assistant. User {self.user_id}. Details: {e}")
                     
    def create_tool_calls(self, run):
        # Create a ToolCall for each required action:
        
        # Attend required action, an action can include more than a tool call:
        system_status = self.string_to_dict(run.model_dump_json()) 
        try:
            # Recover tool calls made by the AI model:
            calls = (
                system_status.get("required_action")
                .get("submit_tool_outputs")
                .get("tool_calls")
            )
        except Exception as e:
            pass
        
        # Create tool_calls:
        for call in calls:
            ext_command = self.lexi.toolbox.get(call["function"]["name"], None)
            try:
                tool_call = ToolCall(
                    self.lexi,
                    self.thread,
                    self.user_id,
                    self.conversation_id,
                    call["id"],
                    call["function"]["name"],
                    call["function"]["arguments"],
                    # Get the reference to the ext command:
                    ext_command
                )
                self.tool_calls.append(tool_call)
            except Exception as e:
                # Tool cannot be used (most probably wrong name):
                with CustomLogger("func_calls_err") as log:
                    log.error(f"Tool '{call['function']['name']}' not found.")

    async def attend_tool_calls(self):
        # Execute tool actions:
        self.status = "in_progress"

        # Manage tasks pending to execute inside a required action:
        for tool_action in self.tool_calls:
            # Execute the actions if they are still pending
            if tool_action.status == "queued":
                # Each action
                await tool_action.async_tool_run()

        # Update required action statuses
        if all(tool_action.status == "completed" for tool_action in self.tool_calls):
            self.status = "completed"

        elif all(
            tool_action.status == "completed" or tool_action.status == "failed"
            for tool_action in self.tool_calls
        ):
            self.status = "with_exceptions"

    def submit_function_outputs(self, run):
        # Create JSON output for function and submit to Run:
        outputs = [tool.submit_function_output() for tool in self.tool_calls]
        try:
            openai.beta.threads.runs.submit_tool_outputs(
                thread_id=self.thread.id, run_id=run.id, tool_outputs=outputs
            )
        except Exception as e:
            raise ValueError("Errors submitting tool outputs. ", e)
        
    def metadata(self):
        # Prepare metadata, information that can enhance the quality of the assistant replies:
        week_day = self.curr_day_short()
        date_time, tzcode = self.get_adjusted_time(
            self.lexi.time_zone, self.lexi.time_delta
        )
        date_time = date_time.strftime("%Y-%m-%d %H:%M:%S")
        metadata = {
            "current_date_time": f"{week_day} {date_time}",
            "time_zone": f"{tzcode}",
        }

        return metadata  # Return as a dictionary, not as a JSON string

    def replace_annotations(self, message) -> str:
        # Extract the message content

        message_content = message.content[0].text.value
        annotations = message.content[0].text.annotations
        citations = []
        attachments = {}

        try:

            # Iterate over the annotations and add footnotes
            for index, annotation in enumerate(annotations):

                # Remove the annotations (for now)
                message_content = message_content.replace(annotation.text, "")
                
                # Gather citations based on annotation attributes
                if (file_citation := getattr(annotation, 'file_citation', None)):
                    cited_file = openai.files.retrieve(file_citation.file_id)
                    citations.append(f'[{index}] {file_citation.quote} from {cited_file.filename}')
                     
                # File references
                if (file_path := getattr(annotation, 'file_path', None)):   
                    cited_file = openai.files.retrieve(file_path.file_id)
                    ext_file_path = cited_file.filename

                    # Extract the file name from the full path
                    filename = os.path.basename(ext_file_path)
                     
                    # File download
                    try:
                        
                        file_content =  openai.files.content(cited_file.id).content

                        # Create a subfolder with the first 5 characters of the session_id
                        subfolder_name = self.session_id[:5]
                        subfolder_path = os.path.join(DOWNLOAD_FOLDER, subfolder_name)

                        # Create the subfolder if it doesn't exist
                        if not os.path.exists(subfolder_path):
                            os.makedirs(subfolder_path)

                        # Create the file path inside the subfolder
                        save_file_path = os.path.join(subfolder_path, filename)

                        # Write the content to the file
                        with open(save_file_path, "wb") as output_file:
                            output_file.write(file_content)
                        
                        attachments[filename] = {'file_path': save_file_path}

                        with CustomLogger("downloads") as log:
                            log.info(f"User: {self.user_id} File name:{filename} Status: Downloaded.")

                    except Exception as e:
                        with CustomLogger("downloads") as log:
                            log.info(f"User: {self.user_id} File name:{filename} Status: Fail - Details: {e}")
    
        except Exception as e:
            pass
        return message_content, attachments

    def update_conversation_title(self, new_title):
        self.conversation_orm.title = new_title
        self.has_changed = True

    def save_conversation(self):
        # Save conversation orm
        # Serialize the binary data
        if self.has_changed:
            try:
                #self.conversation_orm.model_messages = pickle.dumps(self.conversation_orm.model_messages)
                self.conversation_orm.model_messages = None # for now
                self.conversation_orm.app_messages_content = pickle.dumps(self.conversation_orm.app_messages_content)
            except Exception as e:
                pass

            save_conversation_in_db(self.conversation_orm)
    
    def retrieve_messages(self):
        return self.conversation_orm.app_messages_content

    def delete(self):
        # Deactivates the thread and deletes the conversation orm from the database
        self.status = "deleted"
        delete_conversation_in_db(self.conversation_id)

