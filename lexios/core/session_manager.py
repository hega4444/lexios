# session_manager.py

from lexios.core.common_tools import *
from lexios.core.thread import LexiAssistantThread
from lexios.core.lexios_main import LexiOS_Backend
from lexios.core.thread_conversations import (
    save_conversation, 
    update_conversation_title_backend, 
    mark_thread_as_deleted
    )
from lexios.database.conversations import get_user_conversations, delete_conversation_in_db
from lexios.database.users import create_user_account_in_db
from lexios.database.roles import assign_role
from lexios.database.conversations import Conversation


class LexiSessionManager():
    """
    - Manages open user sessions, acts as an intermediary between frontend and backend data

    - Isolates the frontend from direct access to the Database

    """


    _instance = None

    def __new__(cls, lexi: LexiOS_Backend = None):

        if not cls._instance:
            cls._instance = super(LexiSessionManager, cls).__new__(cls)
            cls._instance.active_connections = {}

        if lexi:
            cls._instance.lexi = lexi

        return cls._instance

    def new_lexi_account(self, email: str, password: str, user_data=None, gmail_data=None):
        """ Create an ORM for the user"""
        new_user = create_user_account_in_db(email, password, user_data, gmail_data)

        # Assign the general role as baseline
        assign_role(new_user.user_id, "user", True, True, False)

        return new_user

    def load_conversation(self, conversation: Conversation):
        """ Loads an existing conversation"""
        try:
            user_id = conversation.user_id
            conversation_id = conversation.conversation_id

            # Check if the thread is in cache
            thread = self.active_connections.get((user_id, conversation_id))
            if not thread:
                # Request a new thread
                thread = self.lexi.build_thread(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    restore_conversation=conversation
                )
                self.active_connections[(user_id, conversation_id)] = thread

            return thread

        except Exception as e:
            raise SessionManagerException(f"At load conversation. {e}", ERROR, e.args)

    def get_thread(self, user_id: int, conversation_id: str):
        """ Retrieves the thread object for a user/conversation"""

        return self.active_connections.get((user_id, conversation_id))

    def register_conversation(self, thread: LexiAssistantThread):
        if thread.user_id and thread.conversation_id:
            self.active_connections[(thread.user_id, thread.conversation_id)] = thread

    def close_session(self, user_id: int):
        """ Handles the close of active connections"""
        try:
            for key, thread in list(self.active_connections.items()):
                u_id, _ = key
                if u_id == user_id:
                    save_conversation(thread)

                    if thread.running_stat != "ready":
                        # Cancel the thread
                        thread.cancel_run()

                    # Remove key from active connections
                    del self.active_connections[key]

        except Exception as e:
                raise SessionManagerException(f"Error saving conversation data. User_id:{user_id}. Details:{e}")

        try:
            self.active_connections = {key: thread for key, thread in self.active_connections.items() if
                                       key[0] != user_id}
        except Exception as e:
                raise SessionManagerException(f"Could not close session correctly. User_id:{user_id}. Details:{e}")

    def save_session(self, user_id: int):
        """ Handles the close of active connections"""
        try:
            for key, thread in list(self.active_connections.items()):
                u_id, _ = key
                if u_id == user_id:
                    save_conversation(thread)

        except Exception as e:
                raise SessionManagerException(f"Could not save conversation data. User_id:{user_id}. Details:{e}")

    def update_conversation_title(self, user_id: int, conversation_id: str, new_title: str):
        """ Sends a message to LexiAssistantThread to update its conversation title"""

        thread = self.get_thread(user_id, conversation_id)
        if thread:
            update_conversation_title_backend(thread, new_title)


    def retrieve_conversation(self, user_id: int, conversation_id: str):
        """ Retrieves the messages from a conversation"""

        conversation = get_user_conversations(user_id, conversation_id)
        if conversation:

            # Check if the thread was loaded
            thread = self.get_thread(user_id, conversation_id)
            if not thread:
                self.load_conversation(conversation)
            
            # Return the messages
            return conversation.app_messages_content
    
    def find_user_conversations(self, user_id:int):
        """ Return the conversations ORM objects linked to the user_id"""
        return get_user_conversations(user_id)


    def delete_conversation(self, user_id: int, conversation_id: str):
        """ Finds the associated thread and marks it for deletion.\n
         Also deletes the orm from Database."""

        thread = self.get_thread(user_id, conversation_id)
        if thread:
            # In this case the thread will take care of the orm itself
            mark_thread_as_deleted(thread)

        else:
            # Directly delete the orm
            delete_conversation_in_db(conversation_id)            


        
