# thread_loading.py
import os
import asyncio
import openai
from logging import DEBUG

from lexios.core.common_tools import *
from lexios.core.thread import LexiAssistantThread
from lexios.database.models import Conversation
from lexios.core.thread_conversations import save_conversation


def load_assistant_and_orm_data(thread: LexiAssistantThread, conversation: Conversation):
    # Handles the load of both the assistant and the thread if possible

    try:
        loaded = False

        # Restore conversation
        if conversation: 
            # Restore the conversation_id 
            thread.conversation_id = conversation.conversation_id
            # Load messages
            thread.conversation_orm = conversation

        # Create new conversation model for the db
        else:
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
                    raise LoadConversationFailed(e)
            
                # Set False to start new conversation orm
                loaded = False
            
            except LoadThreadFailed:
                # It will be created on the next message
                pass
            
            finally:
                if loaded:
                    # Refresh the references to assistants for any change
                    refresh_assistant_references(thread, conversation)
        
        # Register new assistants
        elif not loaded: 
            load_assistants(thread, new_conversation, True)

    except Exception as e:
        raise LexiException(f"Thread_loading at load_assistant_orm_data() {e}",ERROR, e.args)
    
                
async def update_thread_messages(
        thread: LexiAssistantThread, 
        new_message :str = None, 
        new_file = None,
        message_to_agent :str = None,
):
    
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
                LexiException(f"Problem uploading file {new_file} for user {thread.user_id}. Details: {e}", WARNING, e)   

    # Text messages (with or without attachments):
    if new_message or message_to_agent:

        if new_message and not thread.run_in_background:
            
            # Update conversation ORM
            thread.save_message(new_message, "user")

        # Check if message includes attachment:
        try:
            file_ref = assistant_file.id
        except Exception:
            file_ref = None

        # Check if the thread was already initiated.
        if thread.loaded_thread:
            # If so, update messages:
            message_data = {
                "thread_id": thread.loaded_thread.id,
                "role": "user",
                # small fix to correct the user input when a new virtual agent is taking over the conversation
                "content": message_to_agent if message_to_agent else new_message,
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
                LexiException(f"At update thread messages. Thread cannot be loaded. {e}")

        else:
            try:
                # Starts a Thread with a new message:
                user_msg = {
                    "role": "user",
                    "content": message_to_agent if message_to_agent else new_message,
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
                    save_conversation(thread, push=True)

            except Exception as e:
                LexiException(f"Problem creating thread. User Id: "
                              f"{thread.user_id} Message: {new_message}, Files: {new_file}. Details: {e}")

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
                    raise LexiException(f"Problem creating thread. Message: '{new_message}'. Files: {new_file}. Details: {e}")

            # Append uploaded file to Thread
            thread.assistant_files.append(new_file)

            with CustomLogger('messages') as log:
                log.debug("new message", details={"from": "lexi", "file uploaded": filename})                    

        except Exception as e:
            raise LexiException(f"Problem attaching file {new_file} to Assistant. User {thread.user_id}. Details: {e}")


async def render_annotations(thread: LexiAssistantThread, links, attachments):
    # Issues messages to the frontend with onformation on how to render links and downloads
    try:
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
    
    except Exception as e:
        raise LexiException(f"At render annotations. {e}")
    

    
def load_assistants(thread: LexiAssistantThread, conversation: Conversation, new: bool = False):
    # Validate consistency and load assistant / virtual agents on thread

    # Here runs all the logic to determine, load, and refresh assistants and threads references, both
    # for the root assistant and the loaded virtual agent if defined in the thread.

    # Define target # 
    
    # Verify if whether it's a virtual agent
    agent = thread.lexi.agents_router.by_name(thread._name_, None)

    # Define the target, meaning the assistant most relevant for loading (root / agent)
    if agent and agent.name == LEXI_ALIAS:
      
        target = "root"

        thread.main_agent = True
    
    elif agent:
        target = "agent"
        
        # Determine if the agent is a main instance or a clone
        thread.main_agent= thread.user_id == agent.as_user_id 
             
    else:
        target = "root"

        thread.main_agent = False
    
   
    # Try to load from db #
    update_thread = False
        
    # If it's not an irreplaceable virtual agent, always load root assistant first
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
                update_thread = True

            elif not saved_root_assistant_id:
                raise LexiException("No root assistant id saved in the conversation.", DEBUG)

        except Exception as e:
        # If the recovery failed, try to create a new instance of the assistant    
            
            # If an assistant reference was given, try to recover that one
            if thread.pre_loaded_assistant_id:
            
                try:
                    # Create root assistant from preloaded settings
                    thread.root_assistant = openai.beta.assistants.retrieve(thread.pre_loaded_assistant_id)

                    # Update assistant and reload tools
                    thread.root_assistant = openai.beta.assistants.update(
                        assistant_id= thread.root_assistant.id,
                        tools= thread.loaded_tools,
                    )                    
                    
                    # Just to follow the setup sequence, also load root assistant 
                    thread.loaded_assistant = thread.root_assistant

                except Exception as e:
                    raise CreateAssistantFailed(f"Recovering Root assistant from DB : {e}", DEBUG, source="root")

            else:
            # If not, create a new one without reference
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

                except Exception as e:
                    raise CreateAssistantFailed(f"Recovering Root assistant from DB : {e}", DEBUG, source="root")
    
        
    # Other virtual agents or failed cases at loading from db #
    if target == 'agent':     
        

        # Try to retrieve loaded assistant and thread data
        if conversation:
            agent_assistant_id = conversation.model_loaded_assistant_id

            try:
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
                    update_thread = True

                else:
                    raise LoadAssistantFailed(f"Virtual Agent {agent.name} No assistant id found. New assistant required.")

            
            except LoadAssistantFailed as e:

                try:
                    # Create virtual agent assistant again
                    thread.loaded_assistant = openai.beta.assistants.create(

                        instructions= agent.instructions,
                        name= agent.name,
                        tools=thread.loaded_tools,   
                        model=thread.lexi.model,
                    )

                except Exception as e:
                        
                    # If agent has enabled 'can_be_replaced' meaning it can be rerouted, then delete its reference
                    if agent.can_be_replaced:
                        # Delete reference
                        thread.virtual_agent_name = None
                        # Default assistant name
                        thread._name_ = thread.lexi.name
                        # Ensure the minimun toolbox
                        thread.loaded_tools = thread.root_tools
    
                    elif not agent.can_be_replaced:
                        # Otherwise rise an exception for debug, problem could be originated in virtual agent can_be_replaced set to False 
                        # and not being able to start.
                        raise LoadAssistantFailed(f"Virtual Agent '{thread.virtual_agent_name}' cannot be loaded. Check 'can_be_replaced' attribute.", DEBUG, source="agent")
            

            except Exception as e:
                raise LexiException("Agent determination procedure failed.", DEBUG, e)
            
    try:        
        
        # Thread could be determined
        saved_loaded_thread_id =  conversation.model_loaded_thread_id
        if update_thread and saved_loaded_thread_id:

            try:
                # Retrieve
                restored_thread = openai.beta.threads.retrieve(saved_loaded_thread_id)
                # Load
                thread.loaded_thread = restored_thread

                # If the target is root refresh also the root_thread field
                if target == "root":
                    thread.root_thread = restored_thread
            
            except Exception as e:
                raise LoadThreadFailed(e)
        
        try:
            # To this point an asisstant should be loaded unless a LoadAssistantFailed exception
            refresh_assistant_references(thread, conversation)
            
            # For workers, save the loaded status aqquaried for a faster reboot
            if thread.virtual_agent_name:    
                # Verify the virtual agent, and keep the default value in case it ghosts 
                agent = thread.lexi.agents_router.by_name(thread._name_)
                if agent:
                    # Create a default title to identify the background conversations
                    conversation.title = f"Virtual Agent Worker - {agent.name} c_id {thread.conversation_id}" 
                    # Record user id used by the agent
                    conversation.user_id = agent.as_user_id
                    conversation.conversation_id = thread.conversation_id
                    
        except Exception as e:
            pass


        
    finally:
        # Push changes into the database
         save_conversation(thread, push=True)


    return True

def refresh_assistant_references(thread: LexiAssistantThread, conversation: Conversation):
    # Update assistants in the ORM object

    conversation.virtual_agent_name = thread.virtual_agent_name or None
    conversation.model_root_assistant_id = thread.root_assistant.id if thread.root_assistant else None
    conversation.model_root_thread_id = thread.root_thread.id if thread.root_thread else None
    conversation.model_loaded_assistant_id = thread.loaded_assistant.id if thread.loaded_assistant else None
    conversation.model_loaded_thread_id = thread.loaded_thread.id if thread.loaded_thread else None

    # Push the changes to the DB
    save_conversation(thread, push=True)