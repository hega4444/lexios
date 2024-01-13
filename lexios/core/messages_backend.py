# messages_backend.py

import aioredis
import json

from lexios.globals import Globals, GENERAL_VIRTUAL_AGENT
from lexios.core.logger import CustomLogger

lexi_instance = None

async def frontend_output(
    # Send a message to the frontend

    content: str, 
    spell: bool = True, 
    user_id: int = None,
    conversation_id: str= None, 
    msg_type: str = "text", 
    images: dict = None,
    metadata: dict = None,
    alias: str = None
):
    
    global lexi_instance

    # process outbound messages to the frontend
    # msg_type : "text", "sys_notif", "title_update"

    try:

        # Load lexi instance
        if not lexi_instance:
            lexi_instance = Globals().lexi

        # Log virtual agents messages
        if user_id == GENERAL_VIRTUAL_AGENT:
            with CustomLogger("lexios") as log:
                log.info(f"Virtual Agent message: {content}")

        # Recover session id from session data backend
        session_id = lexi_instance.users.get(user_id).session_id

        if session_id:
            outbound_message = {
                    "session_id" : str(session_id),
                    "conversation_id": conversation_id,
                    "msg_type": msg_type,
                    "metadata": metadata,
                    "spell": spell,
                    "alias": alias,
                }

            # Command line output:
            if lexi_instance.command_line is True:
                print(f"{lexi_instance.lexi_prompt} {content}")

            outbound_message['content'] = str(content)

            # Images
            if images:
                outbound_message['images']  = images

            # Send message using broker
            async with aioredis.from_url(lexi_instance.broker_url) as broker:
                await broker.publish("fastapi_channel", json.dumps(outbound_message))

    except Exception as e:
        with CustomLogger("lexios") as log:
            log.error("Backend At send message: ", e)
