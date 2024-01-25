# coommon_tools.py

import json
import aioredis
import pytz

from datetime import timedelta, datetime
from dateutil import parser


from lexios.settings.main import *
from lexios.core.exceptions import *
from lexios.globals import Globals, GENERAL_VIRTUAL_AGENT, GENERAL_VIRTUAL_AGENT_LABEL, ROOT_ID
from lexios.core.logger import CustomLogger, DEBUG, WARNING, ERROR, INFO, CRITICAL


def get_adjusted_time():
    """
    Internal shared function to adjust time zone if needed.
    """
    
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
    """
    Util to get the shorter version of the weekday name.
    """
    # Get the current datetime
    now = datetime.now() + timedelta(minutes=TIME_DELTA)
    # Get the current day's name (e.g., 'Monday')
    day_name = now.strftime("%A")
    # Return the first three characters (e.g., 'Mon')
    return day_name[:3]

def custom_json_parser(json_formatted_str: str):
    """
    This custom json parser makes the transition from json like structures 
    to python dictionaries a bit smother, as it does not rely solely in 
    standarized JSON but accepts some variations (specially regarding the 
    use of '' or ""). It is used in different parts of the solution. To name:

    - Function caliing: To parse the arguments given by the AI model.
    - Task scheduling: Again to parse the input parameters when scheduling 
    a function execution.
    
    """
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
    