import re
import asyncio
import uuid
from dateutil import parser
from datetime import datetime


from lexios.core.lexi_base_tools import *
from lexios.core.logger import CustomLogger
from lexios.database.models import ScheduledTaskPydantic
from lexios.database.users import retrieve_users_with_background_tasks, get_user_data_by_user_id
from lexios.database.tasks import get_all_scheduled_tasks, save_scheduled_task_in_db, update_task_status
from lexios.core.builtin.engines.userDataEngine import UserDataManager
from lexios.core.builtin.functions.email import GmailReader
from lexios.core.builtin.functions.calendar import GoogleCalendar

REMINDER_FUNCTION = UserDataManager().schedule_reminder.__name__

class LexiTaskScheduler(LexiBaseTools):
    # Manages the event loop, schedules actions and keeps a persistent state in database.

    def __init__(self, lexi = None):
        super().__init__()


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
                        repeat_each= GmailReader.check_frequency, 
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
        
        # Start the background coroutine to listen for tasks
        asyncio.create_task(self.check_pending_tasks())
    
    def load_scheduled_tasks_from_db(self):
        # Retrieve scheduled tasks from the database as ORM models
        stored_tasks = get_all_scheduled_tasks()

        # Convert ORM models to Pydantic models
        pydantic_tasks = [ScheduledTaskPydantic.model_validate(task.__dict__) for task in stored_tasks]

        # Save the Pydantic models in the class attribute
        return pydantic_tasks

    def attend_action_request(self, user_id, conversation_id, params):
        # Receives a request for scheduling an event
        # Resolves some parsing and common scenerarios when the ai model calls the scheduling function

        # Adjust time format:
        try:
            original_action_time = params.get("action_time", None)
            if original_action_time:

                # Validate is not in the past:
                entered_action_time = parser.parse(original_action_time)
                if entered_action_time <= datetime.now():
                    raise ValueError(" Error: action time is in the past.")

                action_time = self.format_datetime(original_action_time)
            else:
                action_time = None
            
            # If the function is called with a time delta it has priority over a specific time
            delay = params.get("delay_seconds", None)
            if delay:
                delay_seconds = int(delay)
                action_time = None
            else:
                delay_seconds = 0

            corr_params = {
                "action_time": action_time,
                "delay_seconds": delay_seconds,
                "function_name": params.get("function_name"),
                "user_id": user_id,
                "conversation_id": conversation_id,
                "arguments": params.get("arguments", {}),
                "annotations": params.get("annotations", ""),
            }
        except Exception as e:
            return f"{'status': 'Failed', 'details': {e}}"

        ret_status = None
        # Execute scheduling function:
        try:
            ret_status = self.schedule_new_action(
                **corr_params)
            
            # Log call to function for scheduling: 
            with CustomLogger("func_calls") as log:
                log.info(f"Function 'add_scheduled_action' executed with parameters: {corr_params}.")

            return "{'status': 'Scheduled'}"
            
        except Exception as e:
            # Log the problem
            with CustomLogger("func_calls") as log:
                log.error(f"Errors executing function 'add_scheduled_action'. Used parameters: {corr_params}. Details: {e}")

            return f"{'status': 'Failed', 'details': {e}}"
        
    def schedule_new_action(
        self,
        function_name: str,
        user_id: int,
        conversation_id: int,
        action_time: str = None,
        delay_seconds: int = 0,
        arguments=None,
        annotations=None,
    ):
        # KEYS: schedule remind forget remember book task
        # SUMM: scheduler for executing functions at specefic time or with a delay in (seconds). DO NOT use for reminders (use schedule_reminder() instead)
        # action_time 'description' : "Time in format YYYY-MM-DD/HH:MM:SS"
        # action_time 'regex': r'^\d{4}-\d{2}-\d{2}/[0-2][0-9]:[0-5][0-9]:[0-5][0-9]$'
        # delay_seconds 'description' : "Execute the function in <delay> seconds."
        # function_name 'description': "name".
        # annotations 'description': "Text description of the task to be executed."

        if function_name.startswith("functions."):
            # The model adds 'functions.' string sometimes, small fix:
            try:
                alternative_name = function_name.split("functions.")[1]
                if alternative_name in self.lexi.toolbox:
                    function_name = alternative_name
            except Exception:
                pass
        
        if function_name == REMINDER_FUNCTION:
            raise ValueError(f"error: 'cannot schedule function {REMINDER_FUNCTION}(), call function directly instead.")

        if function_name not in self.lexi.toolbox:
            # Let know the assistant if the function name is not available.
            raise ValueError("error : 'Function name not recognized.")

        # Try to use 'regex' validators in comments to prevent mistakes (only if 'regex' was defined):
        try:
            specs = self.lexi.toolbox.get(function_name).specs
            param_specs = specs.get("function").get("parameters").get("properties")
            input_params = json.loads(arguments)
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
            pass

        # Format arguments:
        if arguments == "":
            params = {}
        else:
            if not isinstance(arguments, dict):
                try:
                    params = json.loads(arguments)
                except json.JSONDecodeError as e:
                    try:
                        params = self.string_to_dict(arguments)
                    except Exception:
                        # Communicate with the AI model to check its input:
                        raise ValueError("Error - Arguments should be passed as dictionary.")
            else:
                params = arguments

        if action_time:
            # Parse date and time with custom function (provides flexibility):
            action_time_formatted = parser.parse(action_time)

        elif delay_seconds:
            # Set the action time using the time_delta input:
            action_time_formatted = datetime.now().replace(microsecond=0) + timedelta(seconds=delay_seconds)

        # After checks, append action
        action = ScheduledTaskPydantic(
            task_id= str(uuid.uuid4()),
            user_id= user_id,
            conversation_id= conversation_id,
            start_at= action_time_formatted,
            function_name= function_name,
            arguments= params,
            annotations= annotations or "",
            status= "scheduled",
            category="external_command"
        )

        # Append action in-memory
        self.scheduled_tasks.append(action)

        # Save the scheduled task in the database as backup in case recovery is needed
        save_scheduled_task_in_db(action) 

    def update_status(self, task_id, new_status):
        # Perform an update in the database based on task_id and new_data
        update_task_status(task_id, new_status)

    async def check_pending_tasks(self):
        while True:
            # Check for tasks that are ready to be executed
            ready_tasks = [task for task in self.scheduled_tasks if self.is_task_ready(task)]

            # Execute the ready tasks
            for task in ready_tasks:
                if task.category == "external_command":
                    await self.execute_scheduled_action(task)               
                else:
                    await self.attend_internal_event(task)

                try:
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
                except Exception as e:
                    with CustomLogger("scheduled_tasks") as log:
                        log.warning(f"Could not reschedule task '{task.task_id}'. {e}")

            # Remove executed tasks from the list
            self.scheduled_tasks = [task for task in self.scheduled_tasks if task.status != "completed"]

            # Sleep for a short duration before checking again
            await asyncio.sleep(1)
    
    def is_task_ready(self, task: ScheduledTaskPydantic):
        # Return True if the task is ready, False otherwise
        current_time = datetime.now().replace(microsecond=0)

        # Check time and status
        return task.start_at == current_time and task.status == "scheduled"

    async def execute_scheduled_action(self, action: ScheduledTaskPydantic):
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

            await self.lexi.prepare_output(
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
        
        # Define an internal time event for lexi processes
        
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
               manager = UserDataManager(self.lexi, event.user_id, event.conversation_id)
               
               # Trigger notification process
               await manager.notify_reminder(event.data_id)
        
        elif event.notify_to == "email_listener":
            # Recover user data
            user = get_user_data_by_user_id(event.user_id)
            # Initiate handler
            await GmailReader(user).execute_applying_rules()

        elif event.notify_to == "calendar_listener":
            # Recover user data
            user = get_user_data_by_user_id(event.user_id)
            # Initiate handler
           # await GmailReader(user).get_unread_emails()

        #update event status
        
        event.status = "completed"
        



