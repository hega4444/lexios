# Tools

from admin.verify_folder import find_project_folder

from lexios.core.lexi_base_tools import *
from lexios.core.logger import CustomLogger
from lexios.core.task_scheduler import LexiTaskScheduler


SCHEDULER_FUNCTION = LexiTaskScheduler().schedule_new_action.__name__

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
                    await self.lexi.prepare_output(show_message, user_id=self.user_id, conversation_id=self.conversation_id, msg_type="sys_notif")

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
                # Execute the external command
                try:

                    # Build the dynamic context for the command (some commands may need it)
                    context = {
                        'dynamic_context' : {
                            'lexi': self.lexi,
                            'user_id' : self.user_id,
                            'conversation_id' : self.conversation_id,
                        }
                    }

                    self.ret_status = self.ext_command.execute_command(context, **params)
                    
                except Exception as e:
                    raise ValueError(
                        f"Ext_command '{self.function_name}' execution error: ", e
                    )

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

                # Send to the frontend for rendering
                if message or images:
                    await self.lexi.prepare_output(message, 
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
                    await self.lexi.prepare_output(data, spell=False, user_id=self.user_id, conversation_id=self.conversation_id)

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
                    await self.lexi.prepare_output(show_message, user_id=self.user_id, conversation_id=self.conversation_id, msg_type="sys_notif")
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
        if self.status == "completed":
            self.output = {
                "tool_call_id": self.id, 
                "output": str(self.ret_status)
            }

        # Return error details if needed
        elif self.status in ["failed", "not_found"]:
            self.output = {
                "tool_call_id": self.id,
                "output": "Errors: " + str(self.error_details),
            }

        return self.output

