# thread_loading.py
import os
import asyncio
import openai
from logging import DEBUG

from lexios.core.common_tools import *
from lexios.core.logger import CustomLogger, DEBUG, ERROR
from lexios.database.models import Conversation
from lexios.core.signatures import _LexiAssistantThread
from lexios.core.messages_backend import frontend_output
from lexios.core.exceptions import LoadAssistantFailed, LoadThreadFailed, LoadConversationFailed, CreateAssistantFailed, LexiException

NEW_CHAT_PROMPT = "new chat.."


def load_assistant_and_orm_data(thread: _LexiAssistantThread, conversation: Conversation):
    # Handles the load of both the assistant and the thread if possible
    try:
        loaded = False
        new_conversation = None

        # Restore conversation
        if conversation: 
            # Restore the conversation_id 
            thread.conversation_id = conversation.conversation_id
            # Load messages
            thread.conversation_orm = conversation

        elif not thread.run_in_background:

            # Create new conversation model for the db
            new_conversation = Conversation(

                user_id= thread.user_id,
                conversation_id= thread.conversation_id,
                title = NEW_CHAT_PROMPT,
            )
            thread.conversation_orm = new_conversation

        # Load assistants from stored conversation settings
        if conversation:         
            try:
                loaded = load_assistants(thread, conversation)

            except LoadAssistantFailed as e:
                
                # Recover the source assistant that originated the issue
                source = e.args.get("source")
                
                # Raise an exception to alert for possible settings mistakes at virtual agent (or lexi ;)
                if source and source == "agent" and not thread.can_be_replaced:    
                    raise LoadConversationFailed(e, )
            
                # Set False to start new conversation orm
                loaded = False
            
            except LoadThreadFailed:
                # It will be created on the next message
                pass
        
        # Load new assistant
        elif not loaded:            
                load_assistants(thread, new_conversation, new= True)

    except Exception as e:
        raise LexiException(f"Thread. At load_assistantand_orm_data {e}",ERROR, e.args)
    
                
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


def load_assistants(thread: _LexiAssistantThread, conversation: Conversation, new: bool = False):
    # Validate consistency and load assistant / virtual agents on thread
    
    # Flag that gets updated along the verifications
    start_new = False

    # 1 # Root assistant # 
    
    # Verify if it is a virtual agent
    agent = thread.lexi.agents_router.by_name(thread._name_, None)
    
    # If it is not an irreplaceable virtual agent, always load root assistant first
    if not (agent and not agent.can_be_replaced):

        # Load the root assistant id stored in the conversation
        try:
            saved_root_assistant_id = conversation.model_root_assistant_id
            
            if saved_root_assistant_id:

                # Retrieve assistant
                thread.root_assistant = openai.beta.assistants.retrieve(saved_root_assistant_id)

                # Update assistant and reload tools
                thread.root_assistant = openai.beta.assistants.update(
                    assistant_id= thread.root_assistant.id,
                    tools= thread.loaded_tools,
                )
                # Just to follow the setup sequence, also load root assistant 
                thread.loaded_assistant = thread.root_assistant
                # Define a target for building the thread later
                target = "root"

            elif not saved_root_assistant_id:
                raise LexiException("No root assistant id saved in the conversation.", DEBUG)
            
        except Exception as e:
            # If the recovery failed, try to create a new instance of the assistant
        
            try:
                # Create root assistant
                thread.root_assistant = openai.beta.assistants.create(

                    instructions=thread.instructions,
                    name=thread._name_,
                    tools=thread.loaded_tools,   
                    model=thread.lexi.model,
                )
                
                # Just to follow the setup sequence, also load root assistant 
                thread.loaded_assistant = thread.root_assistant

                # Define a target for building the thread later
                target = "root"
                start_new = True

            except Exception as e:
                raise CreateAssistantFailed(f"Recovering Root assistant from DB : {e}", DEBUG, source="root")
    
    # 2 # Pre loaded Virtual Agent #
    
    # If the thread name and agent are the same it means this is a main virtual agent thread, not a clone
    # works as a deamon service to attend new requests
    if agent and agent.name == thread.virtual_agent_name and new:

        # Try to retrieve loaded assistant and thread data
        if conversation:
            agent_assistant_id = conversation.model_loaded_assistant_id

            # Only if the saved assistant differs from the root
            if agent_assistant_id and agent_assistant_id != thread.root_assistant.id:

                # Retrieve
                agent_assistant = openai.beta.assistants.retrieve(agent_assistant_id)

                # Update tools
                if agent_assistant:
                    updated_agent_assistant = openai.beta.assistants.update(
                        assistant_id= agent_assistant_id,
                        tools= thread.loaded_tools,
                    )
                # Load virtual agent assistant
                thread.loaded_assistant = updated_agent_assistant

                # Overwrite the target
                target = "agent"
        
        else:
            try:
                # Create agent assistant again
                thread.loaded_assistant = openai.beta.assistants.create(

                    instructions= agent.instructions,
                    name= agent.name,
                    tools=thread.loaded_tools,   
                    model=thread.lexi.model,
                )
                
                # Define a target for building the thread later
                target = "agent"
                start_new = True

            except Exception as e:
                    
                # If agent has enabled 'can_be_replaced' meaning it can be rerouted, then delete its reference
                if agent.can_be_replaced:
                    # Delete reference
                    thread.virtual_agent_name = None
                    # Default assistant name
                    thread._name_ = thread.lexi.name
                    # Ensure the minimun toolbox
                    thread.loaded_tools = thread.root_tools
                    # Ensure target
                    target = "root"
                    start_new = True
        
                elif not agent.can_be_replaced:
                    # Otherwise rise an exception for debug, problem could be originated in virtual agent can_be_replaced set to False 
                    # and not being able to start.
                    raise LoadAssistantFailed(f"Virtual Agent '{thread.virtual_agent_name}' cannot be loaded. Check 'can_be_replaced' attribute.", DEBUG, source="agent")
        
    # To this point an asisstant should be loaded at thread.loaded_assistant unless LoadAssistantFailed exception

    # First check the new thread flag, True means we can create a new thread 
    if start_new:
        # The thread creation will be handled later when the first message arrives
        target_thread_id = None

    elif target == "root":
        target_thread_id = conversation.model_root_thread_id

    elif target == "agent":
        target_thread_id = conversation.model_loaded_thread_id

    try:
        # Target thread was determined
        if target_thread_id:

            # Retrieve
            restored_thread = openai.beta.threads.retrieve(target_thread_id)
            # Load
            thread.loaded_thread = restored_thread

            # If the target is root refresh also the root_thread field
            if target == "root":
                thread.root_thread = restored_thread
        
    except Exception as e:
        # Raise exception
        raise LoadThreadFailed(e)

    return True