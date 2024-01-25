# frontend/messages.py

import json
import aioredis

import inspect

from lexios.frontend.active_users import frontend_active_users
from lexios.integration.message import AgentMessage
from lexios.core.common_tools import (
    BROKER_URL, 
    LEXI_ALIAS, 
    GENERAL_VIRTUAL_AGENT,
    BROKER_URL,
    COMMAND_LINE_MESSAGES_OUTPUT,
    LexiLogging,
)


# Send a message to the frontend  
async def render_message(
    content: str, 
    spell: bool = True, 
    user_id: int = None,
    conversation_id: str= None, 
    msg_type: str = "text", 
    images: dict = None,
    metadata: dict = None,
    alias: str = None
):
    """ 
    Processes the outbound messages to the frontend.
    
    Parameters:

    - `content`: str The content of the message to be rendered.\n
    - `spell` <True> by default. Meaning if the message will have a typing effect when being rendered.
    - `user_id`: int
    - `conversation_id`: int
    - `msg_type` : "text", "sys_notif", "title_update"
    - `images`: dict with metadata used by the frontend to render images.
    - `metadata`: used by different components to send their specific details at rendering.
    - `alias`: str The name of the assistant the message comed from. Can be by default the root assistant name, or a virtual agent name.
    
    """


    """
    Following import is at function level to isolate the circular import: 
    """
    from lexios.core.agents_router import AgentsRouter, VirtualAgent

    try:

        # Log virtual agents messages
        if user_id == GENERAL_VIRTUAL_AGENT:
           LexiLogging(f"Virtual Agent message: {content}")

        # Recover session id from session data backend
        session_id = frontend_active_users.get(user_id).session_id

        if session_id:
            outbound_message = {
                    "session_id" : str(session_id),
                    "conversation_id": conversation_id,
                    "msg_type": msg_type,
                    "metadata": metadata,
                    "spell": spell,
                    "alias": alias,
                }
        
            
            name = alias or LEXI_ALIAS
            width = 8 # Adjust the width as needed

            # Left-align the string within the specified width
            formatted_alias = name.ljust(width)

            # Truncate assiatant reply
            max_content_length = 20
            truncated_content = content[:max_content_length] + '...' if len(content) > max_content_length else content + "."

            # Command line output:
            if COMMAND_LINE_MESSAGES_OUTPUT: 
                LexiLogging(f"User Id: {user_id}: Agent: {formatted_alias}- Output : {truncated_content}")
            
            # Message
            if content:
                outbound_message['content'] = str(content)

            # References to Images paths
            if images:
                outbound_message['images']  = images
            
            # Check if the virtual agent has a custom entry point to read/edit the message
            agent : VirtualAgent = AgentsRouter().by_name(alias or LEXI_ALIAS)

            implemented = not getattr(agent.at_agent_message_event, '__isabstractmethod__', False)

            if (implemented and callable(getattr(agent, VirtualAgent.at_agent_message_event.__name__))):

                # Create a AgentMessage to share with the VirtualAgent
                agent_message = AgentMessage(
                    user_id=user_id,
                    conversation_id= conversation_id,
                    content= content or '',
                    msg_type= msg_type,
                    metadata= metadata,
                    spell= spell,
                    images=None,
                )

                # Check if the method is a coroutine function
                is_coroutine = inspect.iscoroutinefunction(agent.at_agent_message_event)

                if is_coroutine:
                    # async call
                    modified_message = await agent.at_agent_message_event(agent_message= agent_message)
                else:
                    # sync call
                    modified_message = agent.at_agent_message_event(agent_message= agent_message)

                # Replace message content with the modified version
                outbound_message["content"] = modified_message.content
                outbound_message["metadata"] = modified_message.metadata
                outbound_message["spell"] = modified_message.spell
                outbound_message["images"] = modified_message.images

            # Send message using broker
            async with aioredis.from_url(BROKER_URL) as broker:
                await broker.publish("fastapi_channel", json.dumps(outbound_message))

    except Exception as e:
       LexiLogging("Backend At send message: ", e)


          