#thread.py
import re
import openai
import asyncio

from admin.verify_folder import find_project_folder

from lexios.api.session_data import read_session_data_from_backend
from lexios.database.models import Conversation 
from lexios.database.conversations import save_conversation_in_db, delete_conversation_in_db
from lexios.database.users import get_user_data_by_user_id
from lexios.core.lexi_base_tools import *
from lexios.core.function_calling import ToolCall
from lexios.core.toolbox import UserToolBox
from lexios.core.logger import CustomLogger
from lexios.core.consent import ConsentScreen

PROJECT_FOLDER = find_project_folder()

class LexiAssistantThread(LexiBaseTools):
    # Represents one conversation with the user

    def __init__(
        self,
        lexi=None,
        run_in_background= False,
        user_assistant=None,
        user_id: str = None,
        user_message: str = None,
        files=None,
        tools=None,
        model=None,
        instructions = None,
        conversation_id = None,
        restore_conversation = False,
        model_assistant_id = None,
        model_thread_id = None,
        metrics = None,
        conversation_orm = None,
        title_generated = False,
        session_id: str = None,

    ) -> None:
        # Call the __init__ methods of the base classes
        super().__init__() 

        # Core object Lexi:
        self.lexi = lexi

        # User thread
        self.thread = None
        self.user_id = user_id
        self.conversation_id = conversation_id

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

        if restore_conversation is True:
            # Try to retrieve assistant and thread data
            try:
                restore_assistant_failed = False
                assistant = openai.beta.assistants.retrieve(model_assistant_id)

                # if assistant is retrieved, update tools
                if assistant:
                    assistant = openai.beta.assistants.update(
                        assistant_id= assistant.id,
                        tools= self.tools,
                    )

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
            
            # Restore messages from database
            if not restore_assistant_failed and not restore_thread_failed:
                self.conversation_orm = conversation_orm

        if restore_conversation is False or restore_assistant_failed or restore_thread_failed:
            # Create the user_assistant role
            self.user_assistant = openai.beta.assistants.create(
                instructions=self.instructions,
                name=self.lexi.name,
                tools=self.tools,   
                model=self.lexi.model,
            )

            if not self.run_in_background:

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

        # Conversation title status
        self.title_generated = title_generated
        if restore_conversation:
            self.title_generated = True

        # Consent dialog screen
        self.consent_dialog = None

    async def new_user_message(self, user_message: str = None, filename:str = None):
        # Handles the execution of a run Thread 
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
                    await self.update_thread_messages(new_message, new_file)
                except ValueError as e:
                    raise ValueError("Could not update messages in Thread.")
            
            if new_message:
                try:
                    # Define scpecific instructions for the run
                    instructions = str(self.metadata()) + self.instructions

                    # Run the thread
                    run = openai.beta.threads.runs.create(
                        thread_id=self.thread.id,
                        assistant_id=self.user_assistant.id,
                        model=self.model,
                        instructions= instructions,
                    )
                    self.run = run

                except Exception as e:
                    with CustomLogger("assistants") as log:
                        log.debug(f"Problem updating executing Thread for User_id: {self.user_id}. Details:{e}")

                    raise ValueError(
                        f"'process_run' could not execute this Run. Details: {e}"
                    )

                # Main loop to treat a Thread - Run
                while run.status not in ["completed", "cancelled", "failed", "expired"]:


                    # Await for Run to change status
                    while run.status in ["queued", "in_progress"]:

                        # Retrieve run status:
                        run = openai.beta.threads.runs.retrieve(
                            thread_id=self.thread.id, run_id=run.id
                        )

                    # Log run status
                    with CustomLogger("lexios") as log:
                        log.info(f"run object status - User: {self.user_id} Status:{run.status} Message:{self.user_message} Last Error: {run.last_error}")
                    
                    # Check if the run failed
                    if run.status == 'failed':
                        raise ValueError(f"openai: {run.last_error}")

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
                        assistant_reply, attachments  = self.manage_downloads(messages.data[0])

                        assistant_reply, link = self.manage_links(assistant_reply)

                        # If the Run requires action and shows some echo message, filter it:
                        if (
                            self.lexi.filter_echo is True
                            and assistant_reply == new_message
                            and run.status == "requires_action"
                        ):
                            # Log entry
                            with CustomLogger("messages") as log:
                                log.debug("new message", details={"from": "lexi", "content": assistant_reply, "filtered": True})
                        
                                
                        elif not self.run_in_background:

                            # Update conversation ORM
                            self.conversation_orm.app_messages_content.append({
                                    'source':'system',
                                    'type': 'text', 
                                    'time': self.format_datetime(str(datetime.now()))[:-3],
                                    'text':assistant_reply,
                                }
                            )
                            self.has_changed = True
                            
                            # Process required outputs by Lexi settings:
                            await self.lexi.prepare_output(assistant_reply, user_id=self.user_id, conversation_id=self.conversation_id)

                            # Log entry
                            with CustomLogger("messages") as log:
                                log.debug("new message", details={"from": "lexi", "content": assistant_reply, "filtered": False})

                        # Handle links
                        if link:
                            await self.lexi.prepare_output(
                                    link.get("text"),
                                    user_id = self.user_id,
                                    conversation_id=self.conversation_id,
                                    msg_type = "sys_notif",
                                    spell = False,
                                    metadata = {"attachment" : link },
                            )

                            # Update conversation ORM
                            self.conversation_orm.app_messages_content.append({
                                        'text': link.get("text"),
                                        'source': "system",
                                        'type':'sys_notif',
                                        'time': self.format_datetime(str(datetime.now()))[:-3],
                                        'metadata': {"attachment" : link },
                                    }
                            )

                        # Handle attachments
                        if attachments:
                            for filename in attachments:

                                await self.lexi.prepare_output(
                                    f'Download "{filename}"',
                                    user_id = self.user_id,
                                    conversation_id=self.conversation_id,
                                    msg_type = "sys_notif",
                                    spell = False,
                                    metadata = {"attachment" : attachments[filename]}
                                )

                                # Update conversation ORM
                                self.conversation_orm.app_messages_content.append({
                                        'text': f'Download "{filename}"',
                                        'source': "system",
                                        'type':'sys_notif',
                                        'time': self.format_datetime(str(datetime.now()))[:-3],
                                        'metadata': {"attachment" : attachments[filename]},
                                    }
                                )

                    # Check for requested tools:
                    if run.status == "requires_action":

                            # Create required tool calls:
                            await self.create_tool_calls(run)

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

        except Exception as e:
                
                # Inform the user about the problem:
                if not self.run_in_background:
                    await self.lexi.prepare_output(
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
        if run.status == "completed" and not self.title_generated and \
        not self.run_in_background:

            # Make a JSON structure with the conversation messages
            content = json.dumps(self.conversation_orm.app_messages_content)
            
            # Generate name, update title
            new_title = self.generate_conversation_name(content)
            self.update_conversation_title(new_title)

            # Notify the frontend
            await self.lexi.prepare_output(
                new_title,
                user_id = self.user_id,
                conversation_id=self.conversation_id,
                msg_type = "title_update",
            )

        # End of Run execution
        # Save the response generated, used for background tasks

        if self.run_in_background and run.status in ["completed", "cancelled", "failed", "expired"]:

            self.response = {
                'status': run.status,
                'output': assistant_reply,
            }

    async def update_thread_messages(self, new_message = None, new_file = None):
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
                
                # Log file upload:
                with CustomLogger("file_uploads") as log:
                    log.info(f"File {new_file} uploaded for user {self.user_id}")

                # Use os.path.basename to extract the filename
                filename = os.path.basename(new_file)

                #Notify the user:
                await self.lexi.prepare_output(
                    f'File "{filename}" uploaded', 
                    user_id=self.user_id, 
                    conversation_id=self.conversation_id,
                    spell = False, 
                    msg_type="sys_notif"
                )

                # Update conversation messages
                self.conversation_orm.app_messages_content.append(
                    {
                        'text': f'File "{filename}" uploaded',
                        'source': "system",
                        'type':'sys_notif',
                        'time': self.format_datetime(str(datetime.now()))[:-3],
                    }
                )

            except FileNotFoundError as e:
                # Log error
                with CustomLogger("file_uploads") as log:
                    log.error(f"Problem uploading file {new_file} for user {self.user_id}. Details: {e}")   

        # Text messages (with or without attachments):
        if new_message:

            if not self.run_in_background:

                # Update conversation ORM
                self.conversation_orm.app_messages_content.append({
                                        'source':'user',
                                        'type': 'text',
                                        'time': self.format_datetime(str(datetime.now()))[:-3],
                                        'text':new_message,
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
                
                except openai.error.BadResponseError as e:
                     
                    if self.run:

                        # Cancel current run
                        openai.beta.threads.runs.cancel(
                            thread_id=self.thread.id,
                            run_id=self.run.id,
                        )

                        # wait for a moment
                        await asyncio.sleep(1)

                        # Try again
                        openai.beta.threads.messages.create(**message_data)
                    
                except Exception as e:
                    with CustomLogger("lexios") as e:
                        log.error(f"Thread remains blocked. {e}")

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
                        messages=[user_msg], 
                        metadata=self.metadata()
                    )

                    if not self.run_in_background:
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
                     
    async def create_tool_calls(self, run):
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
            with CustomLogger("lexios") as log:
                log.error(f"Could not parse tool_calls from Run object. {e}")
        
        requires_consent_screen = False

        # Create Tool_calls:
        for call in calls:

            # Retrieve the external command associated to the Call
            ext_command = self.lexi.toolbox.get(call["function"]["name"], None)

            if ext_command:
                
                try:
                    # Create ToolCall
                    tool_call = ToolCall(
                        lexi=self.lexi,
                        thread=self.thread,
                        user_id=self.user_id,
                        conversation_id=self.conversation_id,
                        id=call["id"],
                        function_name=call["function"]["name"],
                        function_arguments=call["function"]["arguments"],
                        # Get the reference to the ext command:
                        ext_command=ext_command,
                    )

                    self.tool_calls.append(tool_call)

                    # Check if tool requires an scope request
                    if not requires_consent_screen and ext_command.scopes:
                        requires_consent_screen = True

                except Exception as e:
                    # Tool cannot be used (most probably wrong name):
                    with CustomLogger("lexios") as log:
                        log.error(f"Tool '{call['function']['name']}' could not be created. {e}")


        # Check if the action requires a consent screen
        if requires_consent_screen:
            try:

                # Create context for the screen
                context = {
                    'lexi' : self.lexi,
                    'user_id': self.user_id,
                    'conversation_id': self.conversation_id,
                    'calls': self.tool_calls, 
                    'timer': 60,
                }

                # Create consent screen verification
                self.consent_dialog = ConsentScreen(**context)
                
                # Show to user
                await self.consent_dialog.show_to_user()

            except Exception as e:
                with CustomLogger("lexios") as log:
                    log.warning(f"Could not verify consent screen due to {e}.")


    async def attend_tool_calls(self):
        # Execute tool actions:

        while not self.consent_dialog or self.consent_dialog.status not in ["expired", "cancelled"]:

            # Manage tasks pending to execute inside a required action:
            for tool_call in self.tool_calls:
                
                # Create a flag to control the call execution
                ready_to_execute = False

                # Verifiy if there is an active consent dialog
                if self.consent_dialog:

                # Validate the call with the dialog
                    call_consent_status = self.consent_dialog.validate_call(tool_call)

                    if call_consent_status == "granted":
                        ready_to_execute = True

                    elif call_consent_status in ["denied", "expired", "cancelled"]:
                        # Reject the tool call
                        tool_call.reject()

                else:
                    # If there is no active dialog go ahead
                    ready_to_execute = True

                # Execute the actions if they are still pending
                if ready_to_execute and tool_call.status == "queued":
                    
                    # Each action
                    await tool_call.async_tool_run()

                    # Check if the tool generated a custom output
                    if tool_call.custom_output:
                        
                        # Update conversation ORM
                        self.conversation_orm.app_messages_content.append({
                                                'source':'system',
                                                'time': self.format_datetime(str(datetime.now()))[:-3],
                                                'text': tool_call.custom_output.get("text", None),
                                                'images': tool_call.custom_output.get("images", None),
                                            }                    
                        )

            # Update the status of the pending calls
            if all(tool_action.status in ("completed", "failed", "rejected", "expired") \
                   for tool_action in self.tool_calls):
                
                break

            # Wait some time
            await asyncio.sleep(1)

        # Clear the consent token
        if self.consent_dialog:
            self.consent_dialog.clear()
            self.consent_dialog = None


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

    def manage_downloads(self, message):
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

                # Regular expression to match text starting with "[Download" and ending with "]"
                message_content = re.sub(r'\[Download[^\]]*\](?:\(\))?$', '', message_content)
                
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

                        # Create the user directory if it doesn't exist
                        user_folder = os.path.join(PROJECT_FOLDER, "temp", "downloads", str(self.user_id).zfill(5))
                        os.makedirs(user_folder, exist_ok=True)

                        # Create the file path inside the subfolder
                        save_file_path = os.path.join(user_folder, filename)

                        # Write the content to the file
                        with open(save_file_path, "wb") as output_file:
                            output_file.write(file_content)
                        
                        # Update the filename using the static folder of the fronted "downloads"
                        attachments[filename] = {'link': os.path.join("downloads", str(self.user_id).zfill(5), filename)}

                        with CustomLogger("downloads") as log:
                            log.info(f"User: {self.user_id} File name:{filename} Status: Downloaded.")

                    except Exception as e:
                        with CustomLogger("downloads") as log:
                            log.info(f"User: {self.user_id} File name:{filename} Status: Fail - Details: {e}")
    
        except Exception as e:
            pass
        return message_content, attachments

    def manage_links(self, text: str) -> str:
        # Identify links and create appropiate containers
        
        # Define a regular expression pattern for matching URLs and text within square brackets
        pattern = re.compile(r'(?P<text>[^\[]+)(?:\[(?P<text_in_brackets>[^\]]+)\])?(?:\((?P<link>https?://[^\)]+)\))?')

        # Search for the pattern in the input text
        match = re.search(pattern, text)

        if match:
            # Extract the matched groups
            modified_text = match.group('text').strip()
            text_in_brackets = match.group('text_in_brackets')
            link = match.group('link')

            if link:

                link_data = {
                    'text': text_in_brackets,
                    'link' : link, 
                }

                return modified_text, link_data
        
        
        return text, None

    def update_conversation_title(self, new_title):
        self.conversation_orm.title = new_title
        self.has_changed = True
        self.title_generated = True

    def save_conversation(self):
        # Save conversation orm
        # Serialize the binary data
        if self.has_changed:
            try:
                #self.conversation_orm.model_messages = pickle.dumps(self.conversation_orm.model_messages)
                self.conversation_orm.model_messages = None # for now
            except Exception as e:
                pass

            save_conversation_in_db(self.conversation_orm)
    
    def retrieve_messages(self):
        return self.conversation_orm.app_messages_content

    def delete(self):
        # Deactivates the thread and deletes the conversation orm from the database
        self.status = "deleted"
        delete_conversation_in_db(self.conversation_id)

    def generate_conversation_name(self, content):
        # Create automatic an automatic title for the conversation

        response = openai.chat.completions.create(
        model= LEXI_GPT_MODEL,
        # Constraint to valid JSON format
        response_format={ "type": "json_object" },
        temperature=0.5,
        messages=[
            {"role": "system", "content": "You are tool that generates a 'conversation_title' designed to output JSON."},
            {"role": "user", "content": f"conversation messages: {content}" }
        ]
        )
        # Load response as a dictionary
        response_generated = json.loads(response.choices[0].message.content)

        # Extract the value from the dictionary
        new_title = str(list(response_generated.values())[0])

        return new_title
