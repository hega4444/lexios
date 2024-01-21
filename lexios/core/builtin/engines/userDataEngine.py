# userDataEngine.py

import uuid
import json

from lexios.globals import Globals
from lexios.settings.main import *
from lexios.core.logger import CustomLogger
from lexios.database.models import UserSpecificData
from lexios.core.common_tools import frontend_output
from lexios.integration.trusted_actions import TrustedAction
from lexios.database.users import (
    create_user_specific_data, 
    update_user_specific_data, 
    delete_user_specific_data, 
    retrieve_existing_data_categories,
    retrieve_category_content,
    retrieve_content_by_id
)

class UserDataManager():
    def __init__(self, action: TrustedAction = None) -> None:

        # Save context 
        if action:

            self.context = action
            self.user_id = action.user_id
            self.conversation_id = action.conversation_id
        
        # Keep a reference to lexi
        self.lexi = Globals().lexi

        # Define base categories (These are shown to the model as existing from the beginning)
        self.base_categories = ['reminders', 'preferences', 'memories']
        
        # Define hidden categories (These wont be accesible for the AI model)
        self.hidden_categories = ["processed_emails"]

    """
    deprecated
    def __schedule_reminder(self, 
                          start_at: str, 
                          subject:str, 
                          repeat_each: str = None, 
                          end_at:str = None, 
                          content: str = None
    ):
        

        # SUMM: Creates a reminder for the user at specific datetime with subject/content, it can also <repeat_each> number of seconds until <end_at>. Returns the data_id.
        # SUMM: DO NOT USE IT FOR SCHEDULING OTHER FUNCTIONS IN THE FUTURE (use "schedule_new_action() instead.")
        # KEYS: Reminder, alert, alarm, remember, remind.
        # datetime 'description' : "Time in format YYYY-MM-DD/HH:MM:SS"
        # subject 'description' : "Subject for reminder."
        # content 'description' : "Detailed information. Save a text as assistant reminding the event. Example: It is time for your xxxx apointment at yyyy"
        # repeat_each 'description' : "Repeat the reminder each <repeat_each> number of seconds." Please specify a <end_at> value when using periodic reminders.
        # end_at 'description' : periodic reminder finished at <end_at> time.

        # Build data structure
        try:

            # First validate start_at
            if start_at:
                start_at = parser.parse(start_at)
                now = datetime.now()
                # Check the event is not in the past
                if start_at <= now:
                    return {'error' : f'start_at is in the past. Current time: {now.isoformat()}'}
            
            # Validations for periodic reminders
            if repeat_each and not end_at:
                # Make it repeat three times by default.
                end_at = start_at + timedelta(seconds=(repeat_each * 3 + 1))
            
            elif end_at:
                end_at = parser.parse(end_at)

            reminder = {
                'start_at' : start_at.isoformat() if start_at else None,
                'repeat_each' : int(repeat_each) if repeat_each else None,
                'end_at': end_at.isoformat() if end_at else None,
                'subject': subject,
                'content': content,
            }
            # Save in database
            data_id = self.add_user_specific_data(
                data_category='reminders',
                data_content= reminder,
                internal_call = True,
            )

            if isinstance(data_id, str):
                # Creation was successful. Now register with TaskScheduler
                self.lexi.scheduler.new_time_event(
                    user_id = self.user_id,
                    data_id =data_id, 
                    conversation_id = self.conversation_id,
                    start_at = start_at or None,
                    repeat_each = timedelta(seconds=int(repeat_each)) if repeat_each else None,
                    end_at = end_at or None,
                    category = "reminder",
                    notify_to = "userDataManager",
                    arguments = {'subject': subject, 'content': content},

                )

                return {'status': 'created', 'reminder_id': id}
            else:
                # Else return the error details 
                raise ValueError("Could not create record. Try again.")
        except Exception as e:
            return {'error' : e}
    """
    def create_automated_email_response_rule(self, sender_email_address: str, instructions: str):
        # SUMM: Create a rule for answering emails coming from a 'sender', following the specified 'rules'.
        # sender_email_address 'description': valid email address from the sender (just email, no alias).
        # instructions 'description': attach instructions for a GPT model to create a response requested by the user.

        try:

            self.add_user_specific_data(
                data_category= "automated_email_responses",
                data_content= {
                    'rule_id': str(uuid.uuid4())[:4],
                    'sender' : sender_email_address,
                    'original_user_request': self.context.user_message,
                },
                internal_call = True,
            )
        except Exception as e:
            pass

    def update_reminder_element(self, data_id: str, start_at: str= None,repeat_each: str = None, end_at:str = None, subject: str = None, content: str = None):
        # SUMM: Update a data_id. Just populate fields to update.

        # Retrieve the original version 
        original_version = self.retrieve_user_data_content_by_id(data_id=data_id).data_content
        new_version = original_version
        if start_at:
            new_version['start_at'] = start_at
        if repeat_each:
            new_version['repeat_each'] = repeat_each
        if end_at:
            new_version['end_at'] = end_at
        if subject:
            new_version['subject'] = subject
        if content:
            new_version['content'] = content
        
        # Save changes in database
        update_user_specific_data(
            user_id= self.user_id,
            data_id= data_id,
            new_data= new_version
        )

        # Notify the task scheduler of changes
        self.lexi.scheduler.update_time_event(
            task_id = data_id
        )

    async def notify_reminder(self, data_id):

        try:
            # Retrieve data_id from database
            reminder = retrieve_content_by_id(user_id=self.user_id, data_id=data_id)

            # Build message
            data = json.loads(reminder.data_content)
            message = f"\nReminder for you... \n\nDetails: {data['content']}"

            # Send a message to user
            await frontend_output(
                content= message, 
                user_id= self.user_id, 
                conversation_id= self.conversation_id,
            )

            # Log activity
            with CustomLogger("messages") as log:
                log.debug("new message", details={"from": "lexi", "content": reminder.data_content, "filtered": False})

        except Exception as e:
            with CustomLogger("scheduled_tasks") as log:
                log.warning("new message", details={"from": "lexi", "content": reminder.data_content, "filtered": False})


    def delete_reminder(self, data_id: str):
        # SUMM: Delete a reminder by its data_id.
        
        try:
            # Delete from database
            delete_user_specific_data(user_id=self.user_id, data_id= data_id)

            # Notify the scheduler
            self.lexi.scheduler.cancel_time_event(data_id = data_id)

            return "record succesfully deleted"
        
        except Exception as e:
            return f"error: {e}"

    def retrieve_user_data_categories(self):
        # SUMM: Find which data categories are already implemented for the user.

        categories = retrieve_existing_data_categories(user_id= self.user_id)

        #Filter hidden categories
        categories = [category for category in categories if category not in self.hidden_categories]

        # Mix lists and remove duplicates
        return {
            'usage'  : "call read_user_data_category_content(<category>) to get all the data elements under the category.",  
            'categories available' :json.dumps(list(set(self.base_categories + categories)))
        }

    def read_user_data_category_content(self, data_category):
        # SUMM: Retrieve data_content for the specified data_category. It will return a list with all the data elements of such category.
        # data_category 'description' : "Type of data to save (use retrieve_existing_data_categories() if needed."
        
        # Search the database
        data = retrieve_category_content(user_id=self.user_id, data_category= data_category)

        if data:
            data = [content.__dict__ for content in data]
            # Return in JSON format
            return json.dumps(data)
        else:
            available_categories = self.retrieve_user_data_categories()
            return json.dumps({'status': f'No data found under "{data_category}". Available categories:{available_categories}.'})    
    
    def retrieve_user_data_content_by_id(self, data_id: str):
        # SUMM: Retrieve the data_content for a specific data_id.

        data = retrieve_content_by_id(user_id=self.user_id, data_id=data_id)

        if data:
            #return in JSON format
            return json.dumps(data.__dict__)
        
        else:
            return json.dumps({'status': 'data_id not found.'})

    def add_user_specific_data(self, data_category: str, data_content: str, **kwargs):
        # SUMM: Save user specific data. Use this method for new and custom specific data like user preferences, facts to remember.. 
        # SUMM: DO NOT use for reminders. DO NOT USE KWARGS, THATS FOR INTERAL USE ONLY.
        # SUMM: Example: "data_category='birthdays' data_content={'Tom':'10.11.99'}"
        # data_category 'description' : "Type of data to save (use retrieve_existing_data_categories() if needed. New categories can be created added."
        # data_content 'description' : JSON formatted content.

        if kwargs.get("internal_call", False) is False and data_category == "reminders":
            return {'error': 'For "reminders" use function "schedule_reminder()". This function is to store user preferences and other user relevant data.'}

        if kwargs.get("internal_call", False) is False and data_category == "automated_email_responses":
            return {'error': 'For "email_responses" use function "create_automated_email_response_rule()". This function is to store user preferences and other user relevant data.'}


        # Serialize JSON content before saving
        serialized_data_content = json.dumps(data_content)
        
        try:
            # Generate a data_id
            new_data_id = str(uuid.uuid4())

            # Save in database
            create_user_specific_data(UserSpecificData(
                data_id= new_data_id,
                user_id= self.user_id,
                data_category= data_category, 
                data_content= serialized_data_content, 
                )
            )

            return new_data_id
        
        except Exception as e:
            return {'error': e}
    