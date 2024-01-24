# Tools
import asyncio
import openai

from admin.verify_folder import find_project_folder

from lexios.frontend.session_data import read_session_data_from_backend 

from lexios.core.common_tools import *
from lexios.core.logger import CustomLogger, DEBUG
from lexios.core.task_scheduler import LexiTaskScheduler
from lexios.core.exceptions import VirtualAgentRequested, MainAssistantRequested
from lexios.core.exceptions import LexiException, MainAssistantRequested, VirtualAgentRequested
from lexios.core.thread import LexiAssistantThread
from lexios.core.external_command import LexiExternalCommand
from lexios.core.lexios_main import LexiOS_Backend
from lexios.integration.trusted_actions import TrustedAction
from lexios.integration.plugin import PluginTemplate
from lexios.core.consent import ConsentScreen


# To make the code easier to read and keep references

BEFORE_EVENT_NAME = PluginTemplate.before_execution_event.__name__
AFTER_EVENT_NAME =  PluginTemplate.after_execution_event.__name__

PROJECT_FOLDER = find_project_folder()

class ToolCall():


    """ Represents a ToolCall execution, adding an extra layer of security validations
        and also executing custom functionality that the external command may include as part 
        of its protocol when executed.
    """

    def __init__(
        self, 
        lexi : LexiOS_Backend, 
        thread : LexiAssistantThread, 
        user_id: int, 
        conversation_id: str, 
        id: str, 
        function_name: str, 
        function_arguments: str, 
        ext_command : LexiExternalCommand,
        user_message : str = None,
    ):
        super().__init__()

        # Possible states: "new" -> "executed" -> "failed".
        # Lexi
        self.lexi :LexiOS_Backend = lexi
        self.thread : LexiAssistantThread = thread
        self.user_id : int = user_id
        self.conversation_id : str = conversation_id
        self.id : str = id
        self.call_output :str = None
        self.output : any = None
        self.custom_output : any = None
        self.external_cmd : LexiExternalCommand= ext_command
        self.function_name : str = function_name
        self.function_arguments = function_arguments
        self.type : str = "function"
        self.error_details : str = None
        self.user_message : str = user_message
        
        # Determine if it is a valid call
        if ext_command:
            self.status = "queued"
        else:
            self.status = "not_found"
        
        self.signed_action = None

        self.scopes_required = None


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

            # Check if the external command protocol includes messages to the user
            # before executing the command
            try:
                show_message = self.external_cmd.custom_messages.get("before").get(
                    "text", None
                )
                if show_message:
                    await frontend_output(show_message, user_id=self.user_id, 
                                          conversation_id=self.conversation_id, msg_type="sys_notif")
                    await asyncio.sleep(0.4)

            except Exception as e:
                LexiWarning(f"Command {self.external_cmd.name} could not print its messages. {e}")

        
        # Before        
    #----------------------------------BEGIN OF EXECUTE ACTION ---------------------------------------------#
            # Record the execution
            LexiLogging(f"User Id: {self.user_id}: Executing '{self.function_name}'"
                        f" Parameters: {self.function_arguments}.")
            try:
                # Create a snapshot of the current context to share with the service that executes the command
                new_action = TrustedAction(

                    _name_=self.thread._name_,
                    user_id=self.user_id,
                    user=read_session_data_from_backend(self.user_id),
                    conversation_id=self.conversation_id,
                    user_message=self.user_message,
                    transaction_name = self.function_name,
                    virtual_agent_name=self.thread.virtual_agent_name or LEXI_ALIAS,
                    can_be_replaced=self.thread.can_be_replaced or False,
                    timestamp = datetime.now(),
                )

                # If there is a specific PluginTemplate implementation of 'before_execution_event', then call it
                try:
                    # Check directly the specific plugin implementation

                        if ( hasattr(self.external_cmd.dynamic_object, BEFORE_EVENT_NAME) and
                        callable(self.external_cmd.dynamic_object.before_execution_event)):                    
                        
                            # Retrieve the callback function associated to the plugin    
                            before_event = self.external_cmd.dynamic_object.before_execution_event
                            
                            # Submit signed context through the interface
                            await before_event(self.external_cmd.dynamic_object, action= new_action)
                
                except Exception as e: 
                    raise LexiException(f"User Id: {self.user_id}: Agent {self.thread.virtual_agent_name or LEXI_ALIAS} "
                                        f"Executing '{self.function_name}' {BEFORE_EVENT_NAME}(): {e}.")   

                # Execute command with parameters and aggregated context given by Lexi
                self.call_output = await self.external_cmd._execute_command(action=new_action, **params)

    #----------------------------------END OF EXECUTE ACTION ---------------------------------------------------#                 
            # Route to virtual agent
            except (VirtualAgentRequested, MainAssistantRequested) as request:
                
                # Append all the neccesary details to the TrustedAction
                new_action._add_exception(request)
                # Routing metadata
                new_action._add_routing_metadata(request.from_agent, request.to_agent)
                new_action._add_message(f"Aknowledged: Routing message to {request.to_agent}.")
                raise request

            except Exception as e:
                new_action._add_exception(e)
                raise
            
            finally:
                # Security # Attach the result to the action & generate a token response as a signature 
                new_action._sign_results(result= self.call_output)

                # Keep a copy of the action
                self.signed_action = new_action

                # Attach it to the external command as the lowest level of the interface
                self.external_cmd._append_action(new_action)

                # If there is a specific PluginTemplate implementation, call it and send the TrustedAction
                try:
                    # Check directly the specific plugin implementation
                        if (hasattr(self.external_cmd.dynamic_object, AFTER_EVENT_NAME) and
                        callable(self.external_cmd.dynamic_object.after_execution_event)):                    
                        
                            # Retrieve the callback function associated to the plugin    
                            callback = self.external_cmd.dynamic_object.after_execution_event
                            
                            # Submit signed context through the interface
                            await callback(self.external_cmd.dynamic_object, action= new_action)
                
                except Exception as e: 
                    raise LexiException(f"User Id: {self.user_id}: Agent {self.thread.virtual_agent_name or LEXI_ALIAS} "
                                        f"Executing '{self.function_name}' {AFTER_EVENT_NAME}(): {e}.")  
                    
                                                                                                   
            # Change tool_call status to completed
            self.status = "completed"

            # Check if the external command protocol includes messages after execution
            try:
                # Text data
                message = self.external_cmd.custom_messages.get("after").get("text", None)

                # IMG data
                images = self.external_cmd.custom_messages.get("after").get(
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

                # Prepare metadata
                if message or images:
                    
                    # Append custom output
                    self.custom_output = {
                        'text': message,
                        'images': images,
                    }
                    
                    # Send to the frontend for rendering
                    await frontend_output(
                                    content=message, 
                                    images=images, 
                                    user_id=self.user_id, 
                                    spell= False,
                                    conversation_id=self.conversation_id, 
                                    msg_type="text"
                    )   
                
            except Exception as e:
                # Log warning
                with CustomLogger("lexios") as log:
                    log.warning(f"Warning: '{self.function_name}' could not render custom messages/images. {e}")

            # Check if a preview output(automatic w/o checking with the AI model)
            if self.external_cmd.custom_messages.get("show_return_to_user", None):
                try:
                    # Check if there is a sub-routine for printing the function return
                    data = self.external_cmd.format_user_response(self.call_output, new_action)

                    # Print results
                    await frontend_output(data, spell=False, user_id=self.user_id, conversation_id=self.conversation_id)

                except Exception as e:
                    # Log warning
                    with CustomLogger("lexios") as log:
                        log.warning(f"Warning: '{self.function_name}' could not print its results. Details: {e}")

            return self.call_output
        
        # Handle the re routing exceptions
        except VirtualAgentRequested as request:
            self.status = "completed"
            self.call_output = f"Virtual agent {request.to_agent} will handle the request."
            raise 
        except MainAssistantRequested as request:
            self.status = "completed"
            self.call_output = "Routing to main assistant."
            raise
        
        # Other unexpected exceptions
        except Exception as e:
            # Change status to "failed"
            self.status = "failed"
            self.error_details = e.args

            # Check if the external command protocol includes messages after execution
            try:
                show_message = self.external_cmd.custom_messages.get("if_error").get(
                    "text", None
                )
                if show_message:
                    await frontend_output(show_message, user_id=self.user_id, 
                                          conversation_id=self.conversation_id, msg_type="sys_notif")
            except Exception:
                pass

                        
    def submit_function_output(self):
        """
        Prepare JSON to reply the AI model with the return from the external command.
        It prepares the structure but is actually the 'Required Action' that collects 
        all the tool outputs and sends them.
        
        """
        self.output = " "
        
        if self.status in ["completed", "rejected"]:
            self.output = {
                "tool_call_id": self.id, 
                "output": str(self.call_output)
            }

        # Return error details if needed
        elif self.status in ["failed", "not_found"]:
            self.output = {
                "tool_call_id": self.id,
                "output": str(self.error_details),
            }

        return self.output
    
    def reject(self):
        """
        Reject a tool call, denied at the Consent dialog.
        """

        self.status = "rejected"
        self.call_output = "The user denied the execution of this tool."
    
    def cancel(self):
        """ 
        Cancell a tool call, denied at the Consent dialog.
        """
        self.status = "cancelled"
        self.call_output = "Action is no longer needed."        


# Function calling auxiliar functions for LexiAssistantThread: #
        

        
async def create_tool_calls(thread: LexiAssistantThread):
    """ Create a ToolCall for each required action:
    
    Parameters:
    -`thread` : LexiAssistantThread
    """
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

        # Extract the function name from the call
        function_name = call["function"]["name"]

        # Remove the `functions.` prefix
        function_name = function_name.replace("functions.", "", 1)

        # Retrieve the external command associated to the Call
        ext_command : LexiExternalCommand = thread.loaded_toolbox.get(function_name, None)

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
                    user_message=thread.user_message,
                )

                thread.tool_calls.append(tool_call)

                # Check if tool requires an scope request
                if (not requires_consent_screen 
                    and (ext_command.scopes 
                            or 
                        tool_call.scopes_required)
                ):
                    requires_consent_screen = True

            except Exception as e:
                LexiWarning(f"Tool '{function_name}' could not be created. {e}")
        
        else:
            raise LexiException(f"Tool {function_name} was not found in the designated Toolbox.")
                    

           # Check if the action requires a consent screen
    if requires_consent_screen:
        try:

            # Create context for the screen
            context = {
                'lexi' : thread.lexi,
                'user_id': thread.user_id,
                'conversation_id': thread.conversation_id,
                'calls': thread.tool_calls, 
                'timer': 60, # valid for 60''
            }

            # Create consent screen verification
            thread.consent_dialog = ConsentScreen(**context)
            
            # Show to user
            await thread.consent_dialog.show_to_user()

        except Exception as e:
            with CustomLogger("lexios") as log:
                log.warning(f"Could not verify consent screen due to {e}.")


async def attend_tool_calls(thread: LexiAssistantThread):
    """
    Execute tool actions.

    Parameters:
    - `thread`: LexiAssistantThread
    """
    try:

        while not thread.consent_dialog or thread.consent_dialog.status not in ("expired", "cancelled"):

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

                    elif call_consent_status in ("denied", "expired", "cancelled"):
                        # Reject the tool call
                        tool_call.reject()

                else:
                    # If there is no active dialog go ahead
                    ready_to_execute = True

                # Execute the actions if they are still pending
                if ready_to_execute and tool_call.status == "queued":
                    try:

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

                    # Handle request to route the conversation to the main assistant (root)     
                    except MainAssistantRequested as request:
                        if (request.from_agent.lower() == thread._name_.lower() == LEXI_ALIAS.lower() or
                            not thread.can_be_replaced):
                            # For now, do nothing.
                            pass
                        else:
                            # Raise exception at Thread Level
                            raise
                        
                    # Handle request to route the conversation to a Vritual Agent    
                    except VirtualAgentRequested as request:
                        # Verifiy the requested agent is not already loaded
                        if request.to_agent == thread._name_:
                            pass
                        else:
                            # Raise at Thread
                            raise

                    except Exception:
                        LexiException("At function calling, attend_tool_calls(), ", DEBUG)
        

            # Update the status of the pending calls
            if all(tool_action.status in ("completed", "failed", "rejected", "expired") \
                for tool_action in thread.tool_calls):
                
                break

            else:
                # Wait some time
                await asyncio.sleep(1)
    
    except (MainAssistantRequested, VirtualAgentRequested):
        raise

    except Exception:
        thread.running_stat = "inconsistent"

    finally:
        # Clear the consent dialog
        if thread.consent_dialog:
            thread.consent_dialog.clear()
            thread.consent_dialog = None


def submit_function_outputs(thread: LexiAssistantThread):
    """
    Creates a JSON output to submit to the current Run.

    Parameters:
    -`thread`: LexiAssistantThread
    """
    outputs = [tool.submit_function_output() for tool in thread.tool_calls]
    try:
        openai.beta.threads.runs.submit_tool_outputs(
            thread_id=thread.loaded_thread.id, run_id=thread.run.id, tool_outputs=outputs
        )
    except openai.BadRequestError as e:
        pass

    except Exception:
        raise LexiException(f"Error at submit_function_outputs. {e}")