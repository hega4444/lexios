# conversations.py
import json  
from lexios.database.models import Session, Conversation
from lexios.core.logger import CustomLogger, DEBUG
from lexios.core.exceptions import LexiException

def get_user_conversations(user_id):
    # Retrieve stored conversations
    # Create a session
    session = Session()

    try:
        # Query the database to retrieve conversations for the given user_id
        conversations = session.query(Conversation).filter_by(user_id=user_id).order_by(Conversation.last_updated.desc()).all()

        return conversations
    
    except Exception as e:
        with CustomLogger("lexios") as log:
            log.warning(f"Could not retrieve conversations data. Type returned: {e.c_type}, details: {e} ")
            
        session.rollback()  # Rollback changes in case of an error
        raise  # Re-raise the exception for proper error handling

    finally:
        # Close the session
        session.close()

def save_conversation_in_db(conversation: Conversation):
    # Create a session
    with Session() as session:
        try:
            # Query the database to check if the conversation already exists
            existing_conversation = session.query(Conversation).filter_by(conversation_id=conversation.conversation_id).first()

            if existing_conversation:
                # Update the existing conversation with the new data
                existing_conversation.title = conversation.title  # Update each column as needed
                existing_conversation.virtual_agent_name = conversation.virtual_agent_name
                existing_conversation.app_messages_content = conversation.app_messages_content
                existing_conversation.model_root_assistant_id = conversation.model_root_assistant_id
                existing_conversation.model_root_thread_id = conversation.model_root_thread_id
                existing_conversation.model_loaded_assistant_id = conversation.model_loaded_assistant_id
                existing_conversation.model_loaded_thread_id = conversation.model_loaded_thread_id
                existing_conversation.metrics = conversation.metrics 
                # ...

            else:
                # Conversation doesn't exist, so add the new one
                session.add(conversation)

            session.commit()  # Commit the changes

        except Exception as e:
            session.rollback()  # Rollback changes in case of an error
            raise LexiException(f"Could not save conversation data. {e}", DEBUG, e)

        finally:
            session.close()  # Close the session

def delete_conversation_in_db(conversation_id):
    # Create a session
    session = Session()

    try:
        # Query the database to find the conversation by conversation_id
        conversation_to_delete = session.query(Conversation).filter_by(conversation_id=conversation_id).first()

        if conversation_to_delete:
            # Delete the conversation from the database
            session.delete(conversation_to_delete)
            session.commit()  # Commit the changes

    except Exception as e:
        session.rollback()  # Rollback changes in case of an error
        raise  # Re-raise the exception for proper error handling

    finally:
        session.close()  # Close the session