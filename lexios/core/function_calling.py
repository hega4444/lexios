# Tools
import asyncio
import openai

from admin.verify_folder import find_project_folder

from lexios.core.common import *
from lexios.core.logger import CustomLogger
from lexios.core.task_scheduler import LexiTaskScheduler
from lexios.core.consent import ConsentScreen
from lexios.api.session_data import read_session_data_from_backend 
from lexios.core.messages_backend import prepare_output


SCHEDULER_FUNCTION = LexiTaskScheduler.schedule_new_action.__name__

PROJECT_FOLDER = find_project_folder()

class ToolCall():
    # Represents a requested command by the AI model, to be attended.

    def __init__(
        self, 
        lexi, 
        thread, 
        user_id: int, 
        conversation_id: str, 
        id, 
        function_name: str, 
        function_arguments: str, 
        ext_command,
    ):
        super().__init__()

        # Possible states: "new" -> "executed" -> "failed".
        # Lexi
        self.lexi = lexi
        self.thread = thread
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.id = id
        self.ret_status = None
        self.output = None
        self.custom_output = None
        self.ext_command = ext_command
        self.function_name = function_name
        self.function_arguments = function_arguments
        self.type = "function"
        self.error_details = None

        # Determine if it is a valid call
        if ext_command:
            self.status = "queued"
        else:
            self.status = "not_found"

    async def async_tool_run(self):

        # Check the initiation status
        if self.status == "not_found":
            self.error_details = f"Function '{self.function_name}' does not exist."
            return
        
        try:
            params = None
            self.status = "in_progress"
  
            try:
                # Dump the JSON into a dict:
                params = json.loads(self.function_arguments)
            except json.JSONDecodeError:
                # If there are problems, try parsing with custom function:
                try:
                    params = self.string_to_dict(self.function_arguments)
                except Exception as e:
                    raise ValueError(
                        "Problems decoding JSON: ", self.function_arguments
                    )

            # Check if the external command protocol includes messages to the user:
            try:
                show_message = self.ext_command.custom_messages.get("before").get(
                    "text", None
                )
                if show_message:
                    await prepare_output(self.lexi, show_message, user_id=self.user_id, conversation_id=self.conversation_id, msg_type="sys_notif")

            except Exception as e:
                with CustomLogger("func_calls") as log:
                    log.warning(f"Command {self.ext_command.name} could not print its messages. {e}")

            # Check if the action is for scheduling (future action):
            if self.function_name == SCHEDULER_FUNCTION:
                try:
                    self.ret_status = self.lexi.scheduler.attend_action_request(
                        user_id = self.user_id, 
                        conversation_id = self.conversation_id,
                        params = params
                    ) 
                except Exception as e:
                    raise ValueError(f"Could not schedule action. {e}")
               
            else:

            # Before        
        #----------------------------------EXECUTE COMMAND ---------------------------------------------#
                

                try:

                    # Build the dynamic context for the command (some commands may need it)
                    context = {
                        'dynamic_context' : {
                            'lexi': self.lexi,
                            'user_id' : self.user_id,
                            'user': read_session_data_from_backend(self.user_id),
                            'conversation_id' : self.conversation_id,
                        }
                    }
                    
                    
                    self.ret_status = await self.ext_command.execute_command(context, **params)

                except Exception as e:
                    raise ValueError(
                        f"Ext_command '{self.function_name}' execution error: ", e
                    )      

        #----------------------------------EXECUTE COMMAND ---------------------------------------------#                    
                                                                                            # After


            # Change tool_call status to completed
            self.status = "completed"

            # Check if the external command protocol includes messages after execution
            try:
                # Text data
                message = self.ext_command.custom_messages.get("after").get("text", None)

                # IMG data
                images = self.ext_command.custom_messages.get("after").get(
                    "images", None
                )
                if images:

                    # Create the directory if it doesn't exist
                    user_folder = os.path.join(PROJECT_FOLDER, "temp", "downloads", str(self.user_id).zfill(5))
                    os.makedirs(user_folder, exist_ok=True)

                    # Save files in temporal folder
                    for filename, img in images.items():

                        filepath = os.path.join(user_folder, filename)

                        with open(filepath, 'wb') as file:
                            file.write(img.read())
                        
                        images[filename] = os.path.join("downloads", str(self.user_id).zfill(5), filename)

               
                if message or images:
                    
                    # Append custom output
                    self.custom_output = {
                        'text': message,
                        'images': images,
                    }
                    
                    # Send to the frontend for rendering
                    await prepare_output(
                                    self.lexi,
                                    message, 
                                    images=images, 
                                    user_id=self.user_id, 
                                    spell= False,
                                    conversation_id=self.conversation_id, 
                                    msg_type="text"
                    )   
                
            except Exception as e:
                # Log warning
                with CustomLogger("func_calls") as log:
                    log.warning(f"Warning: '{self.function_name}' could not render custom messages/images. {e}")

            # Check if a preview output(automatic w/o checking with the AI model)
            if self.ext_command.custom_messages.get("show_return_to_user", None):
                try:
                    # Check if there is a sub-routine for printing the function return
                    data = self.ext_command.format_user_response(self.ret_status)

                    # Print results
                    await prepare_output(self.lexi, data, spell=False, user_id=self.user_id, conversation_id=self.conversation_id)

                except Exception as e:
                    # Log warning
                    with CustomLogger("func_calls") as log:
                        log.warning(f"Warning: '{self.function_name}' could not print its results. Details: {e}")

            # Log execution: 
            if self.function_name != SCHEDULER_FUNCTION:
                with CustomLogger("func_calls") as log:
                    log.info(f"Function '{self.function_name}' executed with parameters: {params}.")

            return self.ret_status

        except Exception as e:
            # Change status to "failed"
            self.status = "failed"
            self.error_details = e.args

            # Check if the external command protocol includes messages after execution
            try:
                show_message = self.ext_command.custom_messages.get("if_error").get(
                    "text", None
                )
                if show_message:
                    await prepare_output(self.lexi, show_message, user_id=self.user_id, conversation_id=self.conversation_id, msg_type="sys_notif")
            except Exception:
                pass

            # Log the error:
            if self.function_name != SCHEDULER_FUNCTION:
                with CustomLogger("func_calls") as log:
                    log.error(f"Errors executing function '{self.function_name}'. Used parameters: {params}. Details: {e.args}")

    def submit_function_output(self):
        # Prepare JSON to reply the AI model with the return from the external command
        # It prepares the structure but is actually the 'Required Action'
        # that collects all the tool outputs and sends them.
        self.output = " "
        
        if self.status in ["completed", "rejected"]:
            self.output = {
                "tool_call_id": self.id, 
                "output": str(self.ret_status)
            }

        # Return error details if needed
        elif self.status in ["failed", "not_found"]:
            self.output = {
                "tool_call_id": self.id,
                "output": str(self.error_details),
            }

        return self.output
    
    def reject(self):
        # Reject a tool call, denied at the Consent dialog

        self.status = "rejected"
        self.ret_status = "The user denied the execution of this tool."


# Other functions related to calls
        
async def create_tool_calls(thread):
    # Create a ToolCall for each required action:

    requires_consent_screen = False

    # Attend required action, an action can include more than a tool call:
    system_status = custom_json_parser(thread.run.model_dump_json()) 
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


    # Create Tool_calls:
    for call in calls:

        # Retrieve the external command associated to the Call
        ext_command = thread.lexi.toolbox.get(call["function"]["name"], None)

        if ext_command:
            
            try:
                # Create ToolCall
                tool_call = ToolCall(
                    lexi= thread.lexi,
                    thread= thread,
                    user_id= thread.user_id,
                    conversation_id= thread.conversation_id,
                    id=call["id"],
                    function_name=call["function"]["name"],
                    function_arguments=call["function"]["arguments"],
                    # Get the reference to the ext command:
                    ext_command=ext_command,
                )

                thread.tool_calls.append(tool_call)

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
                'lexi' : thread.lexi,
                'user_id': thread.user_id,
                'conversation_id': thread.conversation_id,
                'calls': thread.tool_calls, 
                'timer': 60,
            }

            # Create consent screen verification
            thread.consent_dialog = ConsentScreen(**context)
            
            # Show to user
            await thread.consent_dialog.show_to_user()

        except Exception as e:
            with CustomLogger("lexios") as log:
                log.warning(f"Could not verify consent screen due to {e}.")


async def attend_tool_calls(thread):
    # Execute tool actions:

    while not thread.consent_dialog or thread.consent_dialog.status not in ["expired", "cancelled"]:

        # Manage tasks pending to execute inside a required action:
        for tool_call in thread.tool_calls:
            
            # Create a flag to control the call execution
            ready_to_execute = False

            # Verifiy if there is an active consent dialog
            if thread.consent_dialog:

            # Validate the call with the dialog
                call_consent_status = thread.consent_dialog.validate_call(tool_call)

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
                    thread.conversation_orm.app_messages_content.append({
                                            'source':'system',
                                            'time': format_datetime(str(datetime.now()))[:-3],
                                            'text': tool_call.custom_output.get("text", None),
                                            'images': tool_call.custom_output.get("images", None),
                                        }                    
                    )

        # Update the status of the pending calls
        if all(tool_action.status in ("completed", "failed", "rejected", "expired") \
                for tool_action in thread.tool_calls):
            
            break

        # Wait some time
        await asyncio.sleep(1)

    # Clear the consent token
    if thread.consent_dialog:
        thread.consent_dialog.clear()
        thread.consent_dialog = None


def submit_function_outputs(thread):
    # Create JSON output for function and submit to Run:
    outputs = [tool.submit_function_output() for tool in thread.tool_calls]
    try:
        openai.beta.threads.runs.submit_tool_outputs(
            thread_id=thread.thread.id, run_id=thread.run.id, tool_outputs=outputs
        )
    except Exception as e:
        raise ValueError("Errors submitting tool outputs. ", e)