from datetime import timedelta, datetime
from dateutil import parser
import json
import pytz

# Configs
from lexios.settings.main import *

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
   
