# session_manager.py

from lexios.database.users import create_user_account_in_db
from lexios.database.roles import assign_role
from lexios.core.conversations import save_conversation, update_conversation_title, retrieve_messages, delete
from lexios.core.logger import CustomLogger


class LexiSessionManager:
    # Manages open user sessions  

    _instance = None

    def __new__(cls, lexi = None):

        if not cls._instance:
            cls._instance = super(LexiSessionManager, cls).__new__(cls)
            cls._instance.active_connections = {}   
        
        if lexi:
            cls._instance.lexi = lexi

        return cls._instance

    def new_lexi_account(self, email, password, user_data = None, gmail_data = None):
        # Create an ORM for the the user
        new_user = create_user_account_in_db(email, password, user_data , gmail_data)

        # Assign the general role as baseline
        assign_role(new_user.user_id, "user", True, True, False)

        return new_user

    def load_conversation(self, conversation):

        # Loads a existing conversation retrieved by the session manager
        try:
            
            user_id = conversation.user_id
            conversation_id = conversation.conversation_id
            user_loaded = self.active_connections.get(user_id, None)
           
            new_thread = self.lexi.build_thread(
                user_id= user_id,
                conversation_id= conversation_id,
                restore_conversation= conversation
            )

            if user_loaded:
                self.active_connections[user_id][conversation_id] = new_thread

            else:
                self.active_connections[user_id] = {}
                self.active_connections[user_id][conversation_id] = new_thread
        
        except Exception as e:
            with CustomLogger("lexios") as log:
                log.error(f"Could not load conversation: {e}")

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
                save_conversation(thread)
        except Exception as e:
            with CustomLogger("lexios") as log:
                log.warning(f"Could not save conersation data. User_id:{user_id}. Details:{e}")

        try:
            self.active_connections.pop(user_id)
            pass
        except Exception as e:
            with CustomLogger("lexios") as log:
                log.warning(f"Could not close session correctly. User_id:{user_id}. Details:{e}")
    
    def save_session(self, user_id):
        # Handles the close of active connections
        try:
            for thread in self.active_connections[user_id].values():
                save_conversation(thread)
        except Exception as e:
            with CustomLogger("lexios") as log:
                log.warning(f"Could not save conersation data. User_id:{user_id}. Details:{e}")
    
    def update_converstion_title(self, user_id, conversation_id, new_title):
        # Sends a message to the LexiThread to update the conversation title

        user_loaded = self.active_connections.get(user_id, None)
        if user_loaded:
            thread = user_loaded.get(conversation_id, None)
            if thread:
                update_conversation_title(thread, new_title)
    
    def rerieve_conversation(self, user_id, conversation_id):
        # Retrieves the messages from a conversation

        user_loaded = self.active_connections.get(user_id, None)
        if user_loaded:
            thread = user_loaded.get(conversation_id, None)
            if thread:
                return retrieve_messages(thread)
            
    def delete_conversation(self, user_id, conversation_id):
        # Deletes the messages from a conversation

        user_loaded = self.active_connections.get(user_id, None)
        if user_loaded:
            thread = user_loaded.get(conversation_id, None)
            if thread:
                delete(thread)

