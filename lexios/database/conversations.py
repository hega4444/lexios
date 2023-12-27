# conversations.py

from lexios.database.models import Session, Conversation


def get_user_conversations(user_id):
    # Retrieve stored conversations
    # Create a session
    session = Session()

    try:
        # Query the database to retrieve conversations for the given user_id
        conversations = session.query(Conversation).filter_by(user_id=user_id).order_by(Conversation.last_updated.desc()).all()

        return conversations
    finally:
        # Close the session
        session.close()

def save_conversation_in_db(new_conversation):
    # Create a session
    session = Session()

    try:
        # Query the database to check if the conversation already exists
        existing_conversation = session.query(Conversation).filter_by(conversation_id=new_conversation.conversation_id).first()

        if existing_conversation:
            # Update the existing conversation with the new data
            existing_conversation.title = new_conversation.title  # Update each column as needed
            existing_conversation.app_messages_content = new_conversation.app_messages_content
            existing_conversation.model_assistant_id = new_conversation.model_assistant_id
            existing_conversation.model_thread_id = new_conversation.model_thread_id
            existing_conversation.metrics = new_conversation.metrics 
            # ...

            session.commit()  # Commit the changes
        else:
            # Conversation doesn't exist, so add the new one
            session.add(new_conversation)
            session.commit()

    except Exception as e:
        session.rollback()  # Rollback changes in case of an error
        raise  # Re-raise the exception for proper error handling

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