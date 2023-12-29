import json
from cryptography.fernet import Fernet

from lexios.database.users import validate_password, create_user_account_in_db
from lexios.core.thread import LexiAssistantThread
from lexios.api.session_data import LexiSessionData
from lexios.api.session_data import backend


# Configs
from lexios.settings.main import *

class LexiSessionManager:
    # Manages open user sessions  

    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(LexiSessionManager, cls).__new__(cls)
            cls._instance.active_connections = {}
        return cls._instance

    def new_lexi_account(self, email, password, user_data = None, gmail_data = None):
        # Create an ORM for the the user
        new_user = create_user_account_in_db(email, password, user_data , gmail_data)
        return new_user

    def validate_user_profile(self, email, password, gmail_data = None):
        # Validates a user in the database and recovers their data

        user = validate_password(email=email, password=password)

        if user == 'NEW_GOOGLE_ACCOUNT':
            # Create a new account
            user = self.new_lexi_account(email, password, gmail_data= gmail_data) 

        if user:
            
            # Get the content of the user before decryption
            user_dict = user.__dict__  

            if user.encrypted_google_details:
                
                cipher_suite = Fernet(GOOGLE_ID_SECURE_KEY)
                decrypted_google_details = cipher_suite.decrypt(user.encrypted_google_details)

                # Load decrypted gmail data
                user_dict['google_details'] = json.loads(decrypted_google_details)

            # Create session_data
            session_data = LexiSessionData.model_validate(user.__dict__)
            return session_data
        
        else:
            return None

    def new_lexi_thread(self, user_id, conversation_id, args):
        # Create a new thread and registers with user and conversation id

        user_loaded = self.active_connections.get(user_id, None)

        new_thread = LexiAssistantThread(**args)

        if user_loaded:
            self.active_connections[user_id][conversation_id] = new_thread

        else:
            self.active_connections[user_id] = {}
            self.active_connections[user_id][conversation_id] = new_thread
        
        return new_thread


    def get_thread(self, user_id, conversation_id):
        # Recovers the thread object for a user / conversation
        try:
            return self.active_connections.get(user_id).get(conversation_id)
        except Exception:
            return None
    
    def close_session(self, user_id):
        # Handles the close of active connections
        try:
            for thread in self.active_connections[user_id].values():
                thread.save_conversation()
        except Exception as e:
            pass

        try:
            self.active_connections.pop(user_id)
        except Exception:
            pass
    
    def update_converstion_title(self, user_id, conversation_id, new_title):
        # Sends a message to the LexiThread to update the conversation title
        user_loaded = self.active_connections.get(user_id, None)
        if user_loaded:
            thread = user_loaded.get(conversation_id, None)
            if thread:
                thread.update_conversation_title(new_title)
    
    def rerieve_conversation(self, user_id, conversation_id):
        # Retrieves the messages from a conversation
        user_loaded = self.active_connections.get(user_id, None)
        if user_loaded:
            thread = user_loaded.get(conversation_id, None)
            if thread:
                return thread.retrieve_messages()
            
    def delete_conversation(self, user_id, conversation_id):
        # Deletes the messages from a conversation
        user_loaded = self.active_connections.get(user_id, None)
        if user_loaded:
            thread = user_loaded.get(conversation_id, None)
            if thread:
                return thread.delete()



