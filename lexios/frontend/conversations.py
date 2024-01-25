# frontend/conversations.py 

import json

from fastapi import Query, Depends, Form, APIRouter
from fastapi_csrf_protect import CsrfProtect
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from lexios.frontend.service import Session_manager
from lexios.frontend.session_data import LexiSessionData, verifier, cookie

# Conversations routes
conversations_router = APIRouter() 

# Retrieve the conversation data and focus:
@conversations_router.get("/get_conversation_data", response_class=JSONResponse, dependencies=[Depends(cookie)])
async def get_conversation_data(
    select_conversation_id: str = Query(default=None),
    session_data: LexiSessionData = Depends(verifier)
):
    """
    Retrieves conversation data from the user.
    """
    async with session_data:

        # Load a particular conversation by it's conversation_id
        if select_conversation_id:
            session_data.conversation_id_focus = select_conversation_id

            # Retrieve messages using the session manager
            messages = Session_manager.retrieve_conversation(session_data.user_id, select_conversation_id)

            if messages:
                if not isinstance(messages, list):
                    messages = json.loads(messages)  # Temporal fix while debugging main cause of issue

                conversation_data = {
                    'messages': messages,
                }

                # Return conversation messages
                return JSONResponse(conversation_data)
            
            else:
                raise HTTPException(status_code=404)
        
        # Gest a list of conversations to update the titles on screen 
        else:
         
            conversations = Session_manager.find_user_conversations(session_data.user_id)

            # Retrieve stored conversations
            if conversations:

                # Find the conversation with the newest last_updated timestamp
                newest_conversation = max(conversations, key=lambda c: c.last_updated)
                conversation_index = newest_conversation.conversation_id

                conversations_list = []
                for conversation in conversations:
                    # Create conversations list

                    conversations_list.append([
                        conversation.title,
                        conversation.conversation_id
                    ]
                    )

                # Set the focus on the latest conversation             
                session_data.conversation_id_focus = conversation_index
                
                conversation_data = {
                    'conversations_list' : conversations_list,
                    'conversation_focus': conversation_index,
                }
                return JSONResponse(conversation_data)

            else:
                # No saved chats
                # Determine next conversation index number
                conversation_index = session_data.get_conversation_index()

                # Set the focus on the new conversation
                session_data.conversation_id_focus = conversation_index

                # Prepare return 
                conversation_data = {
                        'conversations_list' : [['new chat..', conversation_index]],
                        'conversation_focus': conversation_index,
                }
                return JSONResponse(conversation_data)

# Update conversation title:
@conversations_router.post('/update_conversation_title', response_class=JSONResponse, dependencies=[Depends(cookie)])
async def update_conversation_title(
    conversation_id: str = Form(...),
    new_title: str = Form(...),
    csrf_protect: CsrfProtect = Depends(), 
    session_data: LexiSessionData = Depends(verifier),
):
    """
    Update conversation title in database.
    """
    Session_manager.update_conversation_title(session_data.user_id, conversation_id, new_title)

    return JSONResponse({'message': 'Conversation title updated successfully'})

# New conversation request
@conversations_router.get('/get_next_conversation_id', response_class=JSONResponse, dependencies=[Depends(cookie)])
async def get_next_conversation_id(
    session_data: LexiSessionData = Depends(verifier),
):
    async with session_data:
        # Get next index number for user_id
        convesation_id = session_data.get_conversation_index()

        # Update conversation focus
        session_data.conversation_id_focus = convesation_id

        # Return the value to the frontend
        return JSONResponse({"next_conversation_id": convesation_id})

# Get conversation focus:
@conversations_router.get('/get_conversation_id_focus', response_class=JSONResponse, dependencies=[Depends(cookie)])
def get_conversation_id_focus(
    session_data: LexiSessionData = Depends(verifier)

)->str:
    """
    Returns a (str) with the index of the conversation to be loaded on the screen main viewer.
    """
    return JSONResponse({'conversation_id_focus': session_data.conversation_id_focus})


# Delete conversation request
@conversations_router.post('/delete_conversation_id', response_class=JSONResponse, dependencies=[Depends(cookie)])
def delete_conversation(
    conversation_id: str = Form(...),
    session_data : LexiSessionData = Depends(verifier),
):
    """
    Deletes a conversation from the database.

    Parameters:
    - `conversation_id`(str): Conversation identifier.
    """
    # Call lexi session manager to take care of the task
    Session_manager.delete_conversation(session_data.user_id, conversation_id)

    return JSONResponse({'message': 'Conversation deleted successfully'})
