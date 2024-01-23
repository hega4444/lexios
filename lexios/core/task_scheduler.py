# task_scheduler.py

import re
import asyncio
import uuid
from dateutil import parser
from datetime import datetime

from lexios.core.common_tools import *
from lexios.database.models import ScheduledTaskPydantic
from lexios.database.users import retrieve_users_with_background_tasks, get_user_data_by_user_id
from lexios.database.tasks import get_all_scheduled_tasks, save_scheduled_task_in_db, update_task_status

from lexios.integration.trusted_actions import TrustedAction
from lexios.core.builtin.engines.userDataEngine import UserDataManager
from lexios.core.builtin.functions.email import GmailClient
from lexios.core.builtin.functions.calendar import GoogleCalendar
from lexios.core.agents_router import AgentsRouter

from lexios.core.external_command import LexiExternalCommand


REESTRICTED_COMMANDS = (AgentsRouter.route_to_main_assistant.__name__,
                     AgentsRouter.route_to_virtual_agent.__name__,
                     AgentsRouter.list_virtual_agents.__name__)

class LexiTaskScheduler():
    """
    The LexiTaskScheduler is a component that works as a clock for the system. It executes 
    schdeduled tasks in the background, and if a session with the user is open it renders 
    a message to inform the correct execution. It also helps creating reminders and alarms
    for the user. All scheduled tasks are stored in Database for the event of system shutdown. 
    Whenever the system is back up again the tasks are restored from database.

    It's active listerner method is check_pending_tasks, running in async mode to share resources
    with the rest of the backend solution.
    
    """

    _instance = None
    _init_done = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LexiTaskScheduler, cls).__new__(cls)
        return cls._instance

    # Manages the event loop, schedules actions and keeps a persistent state in database.

    def __init__(self, action: TrustedAction = None, lexi = None):
        
        # Use the init as pivot to catch the action context
        if self._init_done:
            self.context = action
            return
        
        else:
            # Link with LexiOS
            self.lexi = lexi
        
            # Retrieve all scheduled tasks from the database into memory
            self.scheduled_tasks = self.load_scheduled_tasks_from_db()

            # Start background listeners
            users = retrieve_users_with_background_tasks()
            for user in users:

                now = datetime.now().replace(microsecond=0) + timedelta(seconds=5)

                if user.gmail_access:
                    try:
                        # Schedule background task
                        self.new_time_event(
                            user_id= user.user_id,
                            data_id= None,
                            category= "backgroud_tasks",
                            start_at= now,
                            repeat_each= GmailClient.check_frequency, 
                            notify_to= "email_listener",
                            save_in_db= False,
                        )
                    except Exception as e:
                        pass
                
                if user.google_calendar_access:
                    try:
                        # Schedule background task
                        self.new_time_event(
                            user_id= user.user_id,
                            data_id= None,
                            category= "backgroud_tasks",
                            start_at= now,
                            repeat_each= GoogleCalendar.check_frequency,
                            notify_to="calendar_listener",
                            save_in_db= False,
                        )
                    except Exception as e:
                        pass
                    
        # Mark the class as initialized            
        self._init_done = True

    def load_scheduled_tasks_from_db(self):
        # Retrieve scheduled tasks from the database as ORM models
        stored_tasks = get_all_scheduled_tasks()

        # Convert ORM models to Pydantic models
        pydantic_tasks = [ScheduledTaskPydantic.model_validate(task.__dict__) for task in stored_tasks]

        # Save the Pydantic models in the class attribute
        return pydantic_tasks


    def schedule_new_task(
        self,
        task_type: str,
        description : str,
        function_name: str = None,
        at_time: str = None,
        delay_seconds: str = None,
        repeat_each: str = None,
        end_at: str = None, 
        arguments=None,
        
    ):
        """
        Schedule a new task in the system. It can be either a function execution or a reminder. This method is offered to 
        the Ai model as an external command.

        - KEYS: schedule task function reminder forget remember book task
        - SUMM: scheduler for executing functions at specefic time or with a delay in (seconds).
        - at_time 'description' : "Time in format YYYY-MM-DD/HH:MM:SS"
        - task_type 'description' : 'reminder' for alarms or reminders or 'function' for function calling. 
        - delay_seconds 'description' : "Use it instead of action time to execute the task in x seconds."
        - function_name 'description': "name".
        - repeat_each 'description' : "For tasks that need to be executed periodically."
        - end_at 'description' : " YYYY-MM-DD/HH:MM:SS For periodic jobs, when is the finalization time."
        - description 'description': "Text description of the reminder or task to be executed."
        
        The comment section below is used to parse the tool definition in JSON format.
        """
        # KEYS: schedule task function reminder forget remember book task
        # SUMM: scheduler for executing functions at specefic time or with a delay in (seconds).
        # at_time 'description' : "Time in format YYYY-MM-DD/HH:MM:SS"
        # task_type 'description' : 'reminder' for alarms or reminders or 'function' for function calling. 
        # task_type 'enum': ["function", "reminder"]
        # delay_seconds 'description' : "Use it instead of action time to execute the task in x seconds."
        # function_name 'description': "name".
        # repeat_each 'description' : "For tasks that need to be executed periodically."
        # end_at 'description' : " YYYY-MM-DD/HH:MM:SS For periodic jobs, when is the finalization time."
        # description 'description': "Text description of the reminder or task to be executed."
        
        try:
            # Retrieve the context
            if self.context:
                
                user_id = self.context.user_id
                conversation_id = self.context.conversation_id
            else:
                raise AttributeError("Missing action context.")
            
            # Validate the action type
            if task_type not in ('reminder', 'function'):
                raise AttributeError("Valid options for task_type are 'reminder' or 'function'.")
            
            if task_type == 'reminder' and function_name:
                task_type = 'function'

            # Convert the current time to HHMM format as an integer
            current_time_hhmm = int(datetime.now().strftime("%H%M"))
            
            # Determine execution time 
            action_time_formatted = None
            
            if at_time:
                # Validate is not in the past:
                entered_action_time = parser.parse(at_time)

                if entered_action_time <= datetime.now():
                    raise ValueError(f" Error: action time is in the past. Current time: {current_time_hhmm}")
                
                # Keep the formatted date    
                action_time_formatted = entered_action_time
            
            elif delay_seconds:
                # Set the action time using the time_delta input:
                action_time_formatted = datetime.now().replace(microsecond=0) + timedelta(seconds=int(delay_seconds))

            # Logic for function calling
            if task_type == "function":

                # Validation over the function name
                if function_name.startswith("functions."):
                    # The model adds 'functions.' string sometimes, small fix:
                    try:
                        # Remove the `functions.` prefix
                        function_name = function_name.replace("functions.", "", 1)
                    except Exception:
                        pass
                
                # Filter access to resstricted command 
                if function_name in REESTRICTED_COMMANDS:
                    raise ValueError(f"Invalid access. Call tool {function_name} directly.")

                if function_name not in self.lexi.toolbox:
                    # Let know the assistant if the function name is not available.
                    raise ValueError("Error : 'Function name not recognized.")

                # Try to use 'regex' validators in comments to prevent mistakes (only if 'regex' was defined):
                try:
                    if arguments:
                        # Retrieve the function specs 
                        specs = self.lexi.toolbox.get(function_name).specs
                        param_specs = specs.get("function").get("parameters").get("properties")
                        
                        # Parse arguments
                        try:
                            input_params = json.loads(arguments)
                        except Exception as e:
                            raise LexiException(f"Task scheduler could not parse function calling parameters. {e}")

                       # Check if there is a regex rule 
                        for param_name in input_params:
                            if param_name in param_specs and param_specs.get(param_name).get(
                                "regex", False
                            ):
                                pattern_string = param_specs.get(param_name).get("regex")[2:-1]
                                # Compile the pattern with the IGNORECASE flag
                                pattern = re.compile(pattern_string, re.IGNORECASE)

                                # Use re.match to check if the string matches the pattern from the beginning
                                param_value = input_params[param_name]
                                if pattern.match(param_value):
                                    pass
                                else:
                                    return f"Invalid format for argument '{param_name}'. Expected regex: {pattern}"
                except Exception as e:
                    LexiLogging(f"Task scheduler: {e}")

                # Format arguments:
                if arguments == None:
                    params = {}
                else:
                    if not isinstance(arguments, dict):
                        try:
                            params = json.loads(arguments)
                        except json.JSONDecodeError as e:
                            try:
                                params = custom_json_parser(arguments)
                            except Exception:
                                # Communicate with the AI model to check its input:
                                raise ValueError("Error - Arguments should be passed as dictionary.")
                    else:
                        params = arguments


                # After checks, append action
                action = ScheduledTaskPydantic(
                    task_id= str(uuid.uuid4()),
                    user_id= user_id,
                    conversation_id= conversation_id,
                    start_at= action_time_formatted,
                    function_name= function_name,
                    arguments= params,
                    annotations= description or "",
                    status= "scheduled",
                    category="external_command"
                )

                # Append action in-memory
                self.scheduled_tasks.append(action)

                # Save the scheduled task in the database as backup in case recovery is needed
                save_scheduled_task_in_db(action) 
            
            elif task_type == "reminder":
                
                try:
                    if not USER_DATA_MANAGER:
                        raise ValueError("Reminders are not enabled in the user settings.")

                    # Create a reminder
                    reminder = {
                        'start_at' : action_time_formatted.isoformat(),
                        'repeat_each' : int(repeat_each) if repeat_each else None,
                        'end_at': end_at.isoformat() if end_at else None,
                        'content': description,
                    }

                    # Call the user data manager component
                    user_dmc = UserDataManager(action=self.context)

                    # Save in database
                    data_id = user_dmc.add_user_specific_data(
                        data_category='reminders',
                        data_content= reminder,
                        internal_call = True,
                    )

                    # Validations for periodic reminders
                    if repeat_each and not end_at:
                        # Make it repeat three times by default.
                        end_at = action_time_formatted + timedelta(seconds=(repeat_each * 3 + 1))
                
                    elif end_at:
                        end_at = parser.parse(end_at)

                    if isinstance(data_id, str):
                        # Creation was successful. Now register as a time event
                        self.new_time_event(
                            user_id = user_id,
                            data_id =data_id, 
                            conversation_id = conversation_id,
                            start_at = action_time_formatted or None,
                            repeat_each = timedelta(seconds=int(repeat_each)) if repeat_each else None,
                            end_at = end_at or None,
                            category = "reminder",
                            notify_to = "userDataManager",
                            arguments = {'content': description},

                        )

                        return "Reminder scheduled succesfully."

                except Exception as e:
                    raise LexiException(f"At schedule new task_ reminder {e}")

        except Exception as e:
            raise LexiException(f"Schedule new task {e}")


    def update_status(self, task_id, new_status):
        # Perform an update in the database based on task_id and new_data
        update_task_status(task_id, new_status)

    async def check_pending_tasks(self):
        """
        Periodically checks for tasks that are ready to be executed.
        """
        try:
            while True:
                # Check for tasks that are ready to be executed
                ready_tasks = [task for task in self.scheduled_tasks if self.is_task_ready(task)]

                # Execute the ready tasks
                for task in ready_tasks:
                    try:
                        
                        if task.category == "external_command":
                            await self.execute_scheduled_action(task)               
                        else:
                            await self.attend_internal_event(task)

                        # Schedule next event 
                        if task.repeat_each:

                            if (task.end_at and  task.end_at < datetime.now()):
                                continue
            
                            # Calculate new execution time and update in memory
                            task.start_at = datetime.now().replace(microsecond=0) + timedelta(seconds=task.repeat_each)
                            task.status = "scheduled"

                            # Update in database
                            update_task_status(
                                task_id=task.task_id,
                                new_start_at= task.start_at,
                                new_status= task.status,
                            )

                    except asyncio.CancelledError:
                        return

                    except Exception as e:
                        with CustomLogger("scheduled_tasks") as log:
                            log.warning(f"Could not reschedule task '{task.task_id}'. {e}")
        
                # Remove executed tasks from the list
                self.scheduled_tasks = [task for task in self.scheduled_tasks if task.status != "completed"]

                # Sleep for a short duration before checking again
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            return

    def is_task_ready(self, task: ScheduledTaskPydantic):
        """ Return True if the task is ready, False otherwise

        Parameters:
        - `task`: ScheduledTaskPydantic model.
        """
        current_time = datetime.now().replace(microsecond=0)

        # Check time and status
        return task.start_at == current_time and task.status == "scheduled"

    async def execute_scheduled_action(self, action: ScheduledTaskPydantic):
        """
        Executes a task.

        Parameters:
        - `action` ScheduledTaskPydantic to be executd.
        """
        try:
            function_name = action.function_name

            # Recover the external command
            ext_command = self.lexi.toolbox.get(function_name, None)
            execute_function = ext_command.func

            # Execute the function
            with_arguments = action.arguments

            try:
                execute_function(**with_arguments)

                # Log the execution
                with CustomLogger("scheduled_tasks") as log:
                    log.info(f"Function '{function_name}' executed with parameters: {action.arguments}")
                
                # Update in database
                self.update_status(action.task_id, "completed")

            except Exception as e:
                # Log the error
                with CustomLogger("scheduled_tasks") as log:
                    log.error(f"Function '{function_name}' execution failed. Parameters: {action.arguments}. Details: {e}")

                # Update in database
                self.update_status(action.task_id, "failed")

            # Inform in the interface
            hhmm = datetime.now().strftime('%H:%M')

            await frontend_output(
                f"Scheduled action '{function_name}' executed at {hhmm}.",
                user_id= action.user_id,
                conversation_id= action.conversation_id,
                spell= False,
                msg_type= "sys_notif"
            )

            return {"status": "completed"}
        except Exception as e:
            return {"status": "errors", "details": e}
    
    def new_time_event(self,
                       user_id: int,
                       data_id: str, 
                       category: str,
                       notify_to: str,
                       delay_seconds: int = 0,
                       start_at: datetime = None,
                       end_at: datetime = None,
                       repeat_each: timedelta = None,
                       conversation_id: str = None,
                       arguments: dict = None,
                       annotations: str = None,
                       save_in_db: bool = True,
    ):
        
        """ Creates an internal time event for lexi processes
        """

        # Calculate time
        if delay_seconds:
            action_time_formatted = datetime.now().replace(microsecond=0) + timedelta(seconds=delay_seconds)

        # Remove  
        elif start_at:
            action_time_formatted = start_at.replace(microsecond=0)
        
        if end_at:
            end_at = end_at.replace(microsecond=0)

        try:
            # After checks, append time event
            event = ScheduledTaskPydantic(
                task_id= str(uuid.uuid4()),
                user_id= user_id,
                data_id= data_id,
                conversation_id= conversation_id,
                start_at= action_time_formatted,
                end_at = end_at or None,
                arguments= arguments,
                annotations= annotations or "",
                status= "scheduled",
                category= category or "internal_event",
                notify_to= notify_to,
                repeat_each= repeat_each.seconds if repeat_each else None,
            )

            # Append event in-memory
            self.scheduled_tasks.append(event)

            # Save the scheduled event in the database as backup in case recovery is needed
            if save_in_db:
                save_scheduled_task_in_db(event)
        
        except Exception as e:
            with CustomLogger("scheduled_tasks") as log:
                log.error(f"Problem at scheduling {category if category else 'internal_event'}. Details: {e}")
    
    def update_time_event(self,
                        data_id: str,
                        start_at: datetime = None,
                        end_at: datetime = None,
                        repeat_each: timedelta = None,
                        arguments: dict = None,           
    ):
        
        # Update in-memory
        # Find the task with the matching task_id
        for task in self.scheduled_tasks:
            if task.data_id == data_id:
                # Update the task attributes
                if start_at is not None:
                    task.start_at = start_at
                if end_at is not None:
                    task.end_at = end_at
                if repeat_each is not None:
                    task.repeat_each = repeat_each
                if arguments is not None:
                    task.arguments = arguments
                
                # Update in the database
                update_task_status(
                    task_id=task.task_id,
                    new_start_at=start_at,
                    new_end_at=end_at,
                    new_repeat_each=repeat_each,
                    new_arguments=arguments,
                    new_status="scheduled",
                )
                # Break out of the loop since we found and updated the task
                break

    def cancel_time_event(self, data_id: str):
        # Find the task with the matching task_id
        for task in self.scheduled_tasks:
            if task.data_id == data_id:
                # Update status in memory
                task.status = "cancelled"
        
                # Update in db
                update_task_status(task_id= task.task_id, new_status="cancelled")
                
                # Break out of the loop since we found and updated the task
                break

    async def attend_internal_event(self, event: ScheduledTaskPydantic):
        
        if event.notify_to == "userDataManager":
            if event.category == "reminder":

               # Instantiate a UserDataManager 
               manager = UserDataManager(action= self.context)
               
               # Trigger notification process
               await manager.notify_reminder(event.data_id)
        
        elif event.notify_to == "email_listener":
            # Recover user data
            user = get_user_data_by_user_id(event.user_id)
            # Initiate handler
            await GmailClient(user=user).execute_applying_rules()

        elif event.notify_to == "calendar_listener":
            # Recover user data
            user = get_user_data_by_user_id(event.user_id)
            # Initiate handler
            await GoogleCalendar(user=user).get_calendar_data()

        #update event status
        
        event.status = "completed"
        

if __name__ == "__main__":

    command = LexiExternalCommand(LexiTaskScheduler.schedule_new_task)
    print(command)
