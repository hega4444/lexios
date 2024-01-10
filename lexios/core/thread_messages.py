# thread_messages.py
import os
import asyncio
import openai

from datetime import datetime

from lexios.core.logger import CustomLogger
from lexios.database.models import Conversation 


def restore_conversation_data(thread, conversation):

    # Restore the conversation_id 
    thread.conversation_id = conversation.conversation_id

    # Try to retrieve assistant and thread data
    try:
        restore_assistant_failed = False
        assistant = openai.beta.assistants.retrieve(conversation.model_assistant_id)

        # if assistant is retrieved, update tools
        if assistant:
            assistant = openai.beta.assistants.update(
                assistant_id= assistant.id,
                tools= thread.tools,
            )

        thread.user_assistant = assistant
    except Exception as e:
        restore_assistant_failed = True   
    
    # Try to recover the thread
    try:
        restore_thread_failed = False
        restored_thread = openai.beta.threads.retrieve(conversation.model_thread_id)
        thread.thread = restored_thread

    except Exception as e:
        restore_thread_failed = True
    
    # Restore messages from database
    if not restore_assistant_failed and not restore_thread_failed:
        thread.conversation_orm = conversation

        if restore_assistant_failed or restore_thread_failed:
            # Create the user_assistant role
            thread.user_assistant = openai.beta.assistants.create(
                instructions=thread.instructions,
                name=thread.lexi.name,
                tools=thread.tools,   
                model=thread.lexi.model,
            )

            if not thread.run_in_background:

                # Create new conversation model for the db
               
                thread.conversation_orm = Conversation(
                                            user_id= thread.user_id,
                                            conversation_id= thread.conversation_id,
                                            title = "new chat..",
                                            app_messages_content=[],
                                            model_assistant_id= thread.user_assistant.id,
                                            model_thread_id= None,
                                            model_messages= None,
                                            metrics= None,
                                        )           


async def update_thread_messages(thread, new_message = None, new_file = None):
    # Appends messages and attachments to the current user_thread

    if new_file:
        # Upload File:
        try:
            file_object = openai.files.create(
                    file = open(new_file, "rb"),
                    purpose= "assistants"
                )
            
            # Make it an assistant-file:
            assistant_file = openai.beta.assistants.files.create(
                assistant_id=thread.user_assistant.id, 
                file_id=file_object.id
            )

            assistant_files = openai.beta.assistants.files.list(thread.user_assistant.id)
            
            # Log file upload:
            with CustomLogger("file_uploads") as log:
                log.info(f"File {new_file} uploaded for user {thread.user_id}")

            # Use os.path.basename to extract the filename
            filename = os.path.basename(new_file)

            #Notify the user:
            await thread.lexi.prepare_output(
                f'File "{filename}" uploaded', 
                user_id=thread.user_id, 
                conversation_id=thread.conversation_id,
                spell = False, 
                msg_type="sys_notif"
            )

            # Update conversation messages
            thread.conversation_orm.app_messages_content.append(
                {
                    'text': f'File "{filename}" uploaded',
                    'source': "system",
                    'type':'sys_notif',
                    'time': thread.format_datetime(str(datetime.now()))[:-3],
                }
            )

        except FileNotFoundError as e:
            # Log error
            with CustomLogger("file_uploads") as log:
                log.error(f"Problem uploading file {new_file} for user {thread.user_id}. Details: {e}")   

    # Text messages (with or without attachments):
    if new_message:

        if not thread.run_in_background:

            # Update conversation ORM
            thread.conversation_orm.app_messages_content.append({
                                    'source':'user',
                                    'type': 'text',
                                    'time': thread.format_datetime(str(datetime.now()))[:-3],
                                    'text':new_message,
                                }                    
            )
        thread.has_changed = True

        # Check if message includes attachment:
        try:
            file_ref = assistant_file.id
        except Exception:
            file_ref = None

        if thread.thread:
        # Check if the thread was already initiated.
            # If so, update messages:
            message_data = {
                "thread_id": thread.thread.id,
                "role": "user",
                "content": new_message,
                "metadata": thread.metadata(),
            }

            if file_ref is not None:
                message_data["file_ids"] = [file_ref]

            try:
                openai.beta.threads.messages.create(**message_data)
            
            except openai.error.BadResponseError as e:
                    
                if thread.run:

                    # Cancel current run
                    openai.beta.threads.runs.cancel(
                        thread_id=thread.thread.id,
                        run_id=thread.run.id,
                    )

                    # wait for a moment
                    await asyncio.sleep(1)

                    # Try again
                    openai.beta.threads.messages.create(**message_data)
                
            except Exception as e:
                with CustomLogger("lexios") as e:
                    log.error(f"Thread remains blocked. {e}")

        else:
            try:
                # Starts a Thread with a new message:
                user_msg = {
                    "role": "user",
                    "content": new_message,
                }

                if file_ref is not None:
                    user_msg["file_ids"] = [file_ref]

                thread.thread = openai.beta.threads.create(
                    messages=[user_msg], 
                    metadata=thread.metadata()
                )

                if not thread.run_in_background:
                    # Register thread in conversation ORM
                    thread.conversation_orm.model_thread_id = thread.thread.id

            except Exception as e:
                raise ValueError(f"Problem creating thread. Message: {new_message}, Files: {new_file}. Details: {e}")
        
        with CustomLogger("messages") as log:
            log.debug("new message", details={"from": "user", "content": new_message, "metadata": thread.metadata()})

    # Only file attachments:
    # New files need to be uploaded first, and then be linked to an assistant

    if new_file and not new_message:

        # Append message to Thread
        try:
            # Create a thread if there is no active one yet:
            if thread.thread is None:
                try:
                    msg_with_file = {
                        "role" : "user",
                        "files_id" : [file_ref],
                    }
                    # API call
                    thread.thread = openai.beta.threads.create(
                        messages= msg_with_file,
                        metadata= thread.metadata()
                        )
                    
                except Exception:
                    raise ValueError(f"Problem creating thread. Message: '{new_message}'. Files: {new_file}. Details: {e}")

            # Append uploaded file to Thread
            thread.assistant_files.append(new_file)

            with CustomLogger('messages') as log:
                log.debug("new message", details={"from": "lexi", "file uploaded": filename})                    

        except Exception as e:
            with CustomLogger("assistants") as log:
                log.debug(f"Problem attaching file {new_file} to assistant. User {thread.user_id}. Details: {e}") 

            raise ValueError(f"Problem attaching file {new_file} to Assistant. User {thread.user_id}. Details: {e}")


async def render_annotations(thread, links, attachments):

    # Handle links
    if links:
        await thread.lexi.prepare_output(
                links.get("text"),
                user_id = thread.user_id,
                conversation_id=thread.conversation_id,
                msg_type = "sys_notif",
                spell = False,
                metadata = {"attachment" : links },
        )

        # Update conversation ORM
        thread.conversation_orm.app_messages_content.append({
                    'text': links.get("text"),
                    'source': "system",
                    'type':'sys_notif',
                    'time': thread.format_datetime(str(datetime.now()))[:-3],
                    'metadata': {"attachment" : links },
                }
        )

    # Handle attachments
    if attachments:
        for filename in attachments:

            await thread.lexi.prepare_output(
                f'Download "{filename}"',
                user_id = thread.user_id,
                conversation_id=thread.conversation_id,
                msg_type = "sys_notif",
                spell = False,
                metadata = {"attachment" : attachments[filename]}
            )

            # Update conversation ORM
            thread.conversation_orm.app_messages_content.append({
                    'text': f'Download "{filename}"',
                    'source': "system",
                    'type':'sys_notif',
                    'time': thread.format_datetime(str(datetime.now()))[:-3],
                    'metadata': {"attachment" : attachments[filename]},
                }
            )

