# thread_messages.py
import os
import asyncio
import openai
from logging import DEBUG

from lexios.core.common_tools import *
from lexios.core.logger import CustomLogger
from lexios.database.models import Conversation
from lexios.core.signatures import _LexiAssistantThread
from lexios.core.messages_backend import frontend_output
from lexios.core.exceptions import LoadAssistantFailed, LoadThreadFailed, LoadConversationFailed, CreateAssistantFailed, LexiException

def load_assistand_and_orm_data(thread: _LexiAssistantThread, conversation: Conversation):
    # Handles the load of both the assistant and the thread if possible

    # Check if there is a conversation to restore
    if conversation:
        try:
            # Restore the conversation_id 
            thread.conversation_id = conversation.conversation_id

            # Try to retrieve preset assistant and thread data
            try:
                saved_assistant_id = conversation.model_loaded_assistant_id
                if saved_assistant_id:
                    assistant = openai.beta.assistants.retrieve(saved_assistant_id)

                    # Update tools
                    if assistant:
                        assistant = openai.beta.assistants.update(
                            assistant_id= saved_assistant_id,
                            tools= thread.loaded_tools,
                        )
                    thread.loaded_assistant = assistant
                else:
                    raise LexiException("No assistant id saved in the conversation.", DEBUG)
            except Exception as e:
                raise LoadAssistantFailed(e)
                
            # Try to recover the thread
            try:
                saved_thread_id = conversation.model_loaded_thread_id

                if saved_thread_id:
                    restored_thread = openai.beta.threads.retrieve(saved_thread_id)
                    thread.loaded_thread = restored_thread
                else:
                    raise ValueError("No thread id saved in the conversation.")
                
            except Exception as e:
                raise LoadThreadFailed(e)
            
            # Restore messages from database
            thread.conversation_orm = conversation

            return
        
        except (LoadAssistantFailed, LoadThreadFailed) as e:
            new_assistant_required = True
        
        except Exception as e:
            raise LoadConversationFailed(e)

    if not conversation or new_assistant_required:
            
            try:
                # Create root assistant
                thread.root_assistant = openai.beta.assistants.create(
                    instructions=thread.instructions,
                    name=thread._name_,
                    tools=thread.root_tools,   
                    model=thread.lexi.model,
                )
                
                # Load the root assistant 
                thread.loaded_assistant = thread.root_assistant

                # Create conversation data only for foreground threads
                if not thread.run_in_background:

                    if conversation :
                        # Restore messages from database
                        thread.conversation_orm = conversation
                    
                    else:
                        # Create new conversation model for the db
                        thread.conversation_orm = Conversation(
                                                    user_id= thread.user_id,
                                                    conversation_id= thread.conversation_id,
                                                    title = "new chat..",
                                                    app_messages_content=[],
                                                    root_assistant_id= thread.root_assistant.id,
                                                    root_thread_id= None,
                                                    loaded_assistant_id= thread.root_assistant.id,
                                                    loaded_thread_id= None,
                                                    model_messages= None,
                                                    metrics= None,
                                                    virtual_agent_name=None,
                                                )      
            except Exception as e:
                raise CreateAssistantFailed(e, e.args)
                
async def update_thread_messages(thread: _LexiAssistantThread, new_message = None, new_file = None):
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
            await frontend_output(
                f'File "{filename}" uploaded', 
                user_id=thread.user_id, 
                conversation_id=thread.conversation_id,
                spell = False, 
                msg_type="sys_notif"
            )

            # Update conversation messages
            thread.save_message(f'File "{filename}" uploaded', type="sys_notif")

        except Exception as e:
            # Log error
            with CustomLogger("file_uploads") as log:
                log.error(f"Problem uploading file {new_file} for user {thread.user_id}. Details: {e}")   

    # Text messages (with or without attachments):
    if new_message:

        if not thread.run_in_background:
            
            # Update conversation ORM
            thread.save_message(new_message, "user")

        # Check if message includes attachment:
        try:
            file_ref = assistant_file.id
        except Exception:
            file_ref = None

        if thread.loaded_thread:
        # Check if the thread was already initiated.
            # If so, update messages:
            message_data = {
                "thread_id": thread.loaded_thread.id,
                "role": "user",
                "content": new_message,
                "metadata": thread.metadata(),
            }

            if file_ref is not None:
                message_data["file_ids"] = [file_ref]

            try:
                openai.beta.threads.messages.create(**message_data)
            
            except openai.BadRequestError as e:
                    
                if thread.run:

                    # Cancel current run
                    openai.beta.threads.runs.cancel(
                        thread_id=thread.loaded_thread.id,
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

                thread.loaded_thread = openai.beta.threads.create(
                    messages=[user_msg], 
                    metadata=thread.metadata()
                )

                if not thread.run_in_background:
                    # Register thread in conversation ORM
                    thread.conversation_orm.model_loaded_thread_id = thread.loaded_thread.id

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
            if thread.loaded_thread is None:
                try:
                    msg_with_file = {
                        "role" : "user",
                        "files_id" : [file_ref],
                    }
                    # API call
                    thread.loaded_thread = openai.beta.threads.create(
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


async def render_annotations(thread: _LexiAssistantThread, links, attachments):

    # Handle links
    if links:
        await frontend_output(
                content = links.get("text"),
                user_id = thread.user_id,
                conversation_id=thread.conversation_id,
                msg_type = "sys_notif",
                spell = False,
                metadata = {"attachment" : links },
        )

        # Update conversation ORM
        thread.save_message(links.get("text"), type="sys_notif", metadata={"attachment" : links })

    # Handle attachments
    if attachments:
        for filename in attachments:

            await frontend_output(
                f'Download "{filename}"',
                user_id = thread.user_id,
                conversation_id=thread.conversation_id,
                msg_type = "sys_notif",
                spell = False,
                metadata = {"attachment" : attachments[filename]}
            )

            # Update conversation ORM
            thread.save_message(f'Download "{filename}"', type="sys_notif", metadata= {"attachment" : attachments[filename]})


