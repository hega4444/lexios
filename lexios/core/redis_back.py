# redis_back.py
import aioredis
import json

from lexios.core.logger import CustomLogger

async def prepare_output(
    lexios, 
    *args: str, 
    session_id = None, 
    spell=True, 
    user_id=None,
    conversation_id=None, 
    msg_type= "text", 
    images = None,
    metadata= None
):
        
    # process outbound messages to the user interface
    # msg_type : "text", "sys_notif", 

    try:
        # Recover session id from session data backend
        session_id = lexios.users.get(user_id).session_id

        outbound_message = {
                "session_id" : str(session_id),
                "conversation_id": conversation_id,
                "msg_type": msg_type,
                "metadata": metadata,
                "spell": spell,
            }

        # Convert all elements to strings
        args = [str(arg) for arg in args]  
        # Try to make a string with the args
        message = " ".join(args)

        # Command line output:
        if lexios.command_line is True:
            print(f"{lexios.lexi_prompt} {message}")

        outbound_message['content'] = message

        # Images
        if images:
            outbound_message['images']  = images

        # Send message using broker
        async with aioredis.from_url(lexios.broker_url) as broker:
            await broker.publish("fastapi_channel", json.dumps(outbound_message))

    except Exception as e:
        with CustomLogger("lexios") as log:
            log.error("Problems with sending the message: ", e)
