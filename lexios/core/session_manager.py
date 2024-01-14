# session_manager.py

from lexios.core.signatures import _LexiSessionManager, _LexiOS_Backend, _LexiAssistantThread
from lexios.database.users import create_user_account_in_db
from lexios.database.roles import assign_role
from lexios.database.conversations import Conversation
from lexios.core.conversations import save_conversation, update_conversation_title, retrieve_messages, delete
from lexios.core.logger import CustomLogger
from lexios.core.exceptions import SessionManagerException
from logging import ERROR


class LexiSessionManager():
    # Manages open user sessions  

    _instance = None

    def __new__(cls, lexi = None):

        if not cls._instance:
            cls._instance = super(LexiSessionManager, cls).__new__(cls)
            cls._instance.active_connections = {}   
        
        if lexi:
            cls._instance.lexi = lexi

        return cls._instance
    

    def new_lexi_account(self, email: str, password: str, user_data = None, gmail_data = None):
        # Create an ORM for the the user
        new_user = create_user_account_in_db(email, password, user_data , gmail_data)

        # Assign the general role as baseline
        assign_role(new_user.user_id, "user", True, True, False)

        return new_user

    def load_conversation(self, conversation: Conversation):
        # Loads an existing conversation 
        try:
            user_id = conversation.user_id
            conversation_id = conversation.conversation_id

            # Check if the thread is in cache
            if (user_id, conversation_id) in self.active_connections:
                return self.active_connections[(user_id, conversation_id)]
            else:
                # Request a new thread
                new_thread = self.lexi.build_thread(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    restore_conversation=conversation
                )
                self.active_connections[(user_id, conversation_id)] = new_thread

        except Exception as e:
            raise SessionManagerException(f"At load conversation. {e}", ERROR, e.args)

    def get_thread(self, user_id: int, conversation_id: str):
        # Recovers the thread object for a user/conversation
        return self.active_connections.get((user_id, conversation_id))
    
    def register_thread(self, thread: _LexiAssistantThread):
        if thread.user_id and thread.conversation_id:
            self.active_connections[(thread.user_id, thread.conversation_id)] = thread

    def close_session(self, user_id: int):
        # Handles the close of active connections
        try:
            for (u_id, conversation_id), thread in list(self.active_connections.items()):
                    if u_id == user_id:
                        save_conversation(thread)

                        # Cancel the thread
                        thread.cancel_run()

                        # Remove pair key from active connections
                        del self.active_connections[(u_id, conversation_id)]

        except Exception as e:
            with CustomLogger("lexios") as log:
                log.warning(f"Could not save conersation data. User_id:{user_id}. Details:{e}")

        try:
            self.active_connections.pop(user_id)
            pass
        except Exception as e:
            with CustomLogger("lexios") as log:
                log.warning(f"Could not close session correctly. User_id:{user_id}. Details:{e}")
    
    def save_session(self, user_id: int):
        # Handles the close of active connections
        try:
            for (u_id, conversation_id), thread in list(self.active_connections.items()):
                if u_id == user_id:
                    save_conversation(thread)

        except Exception as e:
            with CustomLogger("lexios") as log:
                log.warning(f"Could not save conersation data. User_id:{user_id}. Details:{e}")
    
    def update_converstion_title(self, user_id: int, conversation_id: str, new_title: str):
        # Sends a message to the LexiThread to update the conversation title

        user_loaded = self.active_connections.get(user_id, None)
        if user_loaded:
            thread = user_loaded.get(conversation_id, None)
            if thread:
                update_conversation_title(thread, new_title)
    
    def rerieve_conversation(self, user_id: int, conversation_id: str):
        # Retrieves the messages from a conversation

        user_loaded = self.active_connections.get(user_id, None)
        if user_loaded:
            thread = user_loaded.get(conversation_id, None)
            if thread:
                return retrieve_messages(thread)
            
    def delete_conversation(self, user_id: int, conversation_id: str):
        # Deletes the messages from a conversation

        user_loaded = self.active_connections.get(user_id, None)
        if user_loaded:
            thread = user_loaded.get(conversation_id, None)
            if thread:
                delete(thread)

