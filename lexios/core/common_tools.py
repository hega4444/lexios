# coommon_tools.py

import json
import aioredis
import pytz

from datetime import timedelta, datetime
from dateutil import parser

from lexios.settings.main import *
from lexios.core.exceptions import *
from lexios.core.signatures import _LexiAssistantThread, _LexiOS_Backend, _LexiSessionManager
from lexios.globals import Globals, GENERAL_VIRTUAL_AGENT, GENERAL_VIRTUAL_AGENT_LABEL, ROOT_ID
from lexios.core.logger import CustomLogger, DEBUG, WARNING, ERROR, INFO, CRITICAL

lexi_instance = None

def get_adjusted_time():
    # Adjust time delta if neccesary

    try:
        # Get the specified time zone
        target_timezone = pytz.timezone(TIME_ZONE)

        # Get the current datetime in the specified time zone
        current_datetime = datetime.now(target_timezone)

        # If a time delta is provided, adjust the current time
        if isinstance(TIME_DELTA, int):
            current_datetime += timedelta(minutes=TIME_DELTA)

        # Get the time zone code
        timezone_code = current_datetime.tzinfo.zone

        return current_datetime, timezone_code
    except pytz.UnknownTimeZoneError:
        return None, None  # Return None if the provided time zone is invalid

def format_datetime(datetime_str):
    try:
        # Parse the datetime string into a datetime object
        dt = parser.parse(datetime_str)

        # Format the datetime object as "YYYY-MM-DD/HH:MM:SS"
        formatted_datetime = dt.strftime("%Y-%m-%d/%H:%M:%S")

        return formatted_datetime
    except ValueError:
        return None  # Return None for invalid datetime strings

def curr_day_short():
    # Get the current datetime
    now = datetime.now() + timedelta(minutes=TIME_DELTA)
    # Get the current day's name (e.g., 'Monday')
    day_name = now.strftime("%A")
    # Return the first three characters (e.g., 'Mon')
    return day_name[:3]

def custom_json_parser(json_formatted_str: str):
    try:
        # Try to parse the string as JSON
        return json.loads(json_formatted_str)
    except json.JSONDecodeError:
        # If it's not valid JSON, manually parse it
        s = s.strip("{}")

        parts = [part.strip() for part in s.split(",")]
        result = {}

        for part in parts:
            key, value = part.split(":", 1)
            key = key.strip('"').strip()
            value = value.strip()

            if value.startswith("{") and value.endswith("}"):
                value = custom_json_parser(value)

            if value.startswith('"') and value.endswith('"'):
                value = value.strip('"')

            result[key] = value

        return result
    
# Send a message to the frontend  
async def frontend_output(
    

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
            
            name = alias or lexi_instance.name
            width = 8 # Adjust the width as needed

            # Left-align the string within the specified width
            formatted_alias = name.ljust(width)

            # Truncate assiatant reply
            max_content_length = 20
            truncated_content = content[:max_content_length] + '...' if len(content) > max_content_length else content + "."

            # Command line output:
            if lexi_instance.command_line is True:
                LexiLogging(f"User Id: {user_id}: Agent: {formatted_alias}- Output : {truncated_content}")
            
            # Message
            if content:
                outbound_message['content'] = str(content)

            # References to Images paths
            if images:
                outbound_message['images']  = images

            # Send message using broker
            async with aioredis.from_url(lexi_instance.broker_url) as broker:
                await broker.publish("fastapi_channel", json.dumps(outbound_message))

    except Exception as e:
        with CustomLogger("lexios") as log:
            log.error("Backend At send message: ", e)

