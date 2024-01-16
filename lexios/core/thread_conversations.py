# thread_conversations.py

import json
import openai

from lexios.settings.main import *
from lexios.database.conversations import save_conversation_in_db, delete_conversation_in_db
from lexios.core.messages_backend import frontend_output
from lexios.core.thread import LexiAssistantThread


def update_conversation_title(thread: LexiAssistantThread, new_title):
    thread.conversation_orm.title = new_title
    thread.has_changed = True
    thread.title_generated = True

def save_conversation(thread: LexiAssistantThread, push: bool=False):

    # Save conversation orm
    try:
        if push or thread.conversation_orm.app_messages_content:
            # Only save if push is true or if there are app messages
            thread.conversation_orm.model_messages = None  # for now
            save_conversation_in_db(thread.conversation_orm)
    except Exception as e:
        pass

def retrieve_messages(thread: LexiAssistantThread):
    return thread.conversation_orm.app_messages_content

def delete(thread: LexiAssistantThread):
    # Deactivates the thread and deletes the conversation orm from the database
    thread.running_stat = "deleted"
    delete_conversation_in_db(thread.conversation_id)

async def generate_conversation_name(thread: LexiAssistantThread):
    # Create automatic an automatic title for the conversation

    # Make a JSON structure with the conversation messages
    content = json.dumps(thread.conversation_orm.app_messages_content)

    response = openai.chat.completions.create(
    model= LEXI_GPT_MODEL,
    # Constraint to valid JSON format
    response_format={ "type": "json_object" },
    temperature=0.5,
    messages=[
        {"role": "system", "content": "You are tool that generates a 'conversation_title' designed to output JSON."},
        {"role": "user", "content": f"conversation messages: {content}" }
    ]
    )
    # Load response as a dictionary
    response_generated = json.loads(response.choices[0].message.content)

    # Extract the value from the dictionary
    new_title = str(list(response_generated.values())[0])

    update_conversation_title(thread, new_title)

    # Notify the frontend
    await frontend_output(
        content = new_title,
        user_id = thread.user_id,
        conversation_id=thread.conversation_id,
        msg_type = "title_update",
    )

