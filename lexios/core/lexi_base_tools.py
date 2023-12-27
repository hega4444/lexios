from datetime import timedelta, datetime
from dateutil import parser
import threading
import json
import pytz

# Configs
from lexios.settings.main import *

class LexiBaseTools:
    # Class for different custom tools useful along the code

    # Manage dynamic locks for reseources:
    log_locks = {}
    log_path = LOG_FOLDER
    time_delta = TIME_DELTA
    time_zone = TIME_ZONE
    
    def __init__(self) -> None:
        pass

    @classmethod
    def log_entry(cls, type, log_object) -> bool:
        log_time = datetime.now().strftime("%y%m%d_%H:%M")

        # Check if there is a lock for the resource, if not, create a new one:
        if type not in cls.log_locks:
            new_lock = threading.Lock()
            cls.log_locks[type] = new_lock
            selected_lock = new_lock
        else:
            selected_lock = cls.log_locks[type]
        
        # Ensure the resource and write logs:   
        with selected_lock:
            # Log an entry in the log
            try:
                with open(f"{cls.log_path}/log__{type}.json", "a") as file:
                    file.write(log_time + str(log_object).replace("\n", "") + "\n")
            except IOError as e:
                print("Log couldnt find file / folder.", type)

    def string_to_dict(self, s):
        try:
            # Try to parse the string as JSON
            return json.loads(s)
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
                    value = self.string_to_dict(value)

                if value.startswith('"') and value.endswith('"'):
                    value = value.strip('"')

                result[key] = value

            return result

    @classmethod
    def get_adjusted_time(cls, time_zone=None, time_delta=None):
        if time_zone:
            cls.time_zone = time_zone
        if time_delta:
            cls.time_delta = time_delta

        try:
            # Get the specified time zone
            target_timezone = pytz.timezone(cls.time_zone)

            # Get the current datetime in the specified time zone
            current_datetime = datetime.now(target_timezone)

            # If a time delta is provided, adjust the current time
            if cls.time_delta is not None:
                current_datetime += timedelta(minutes=cls.time_delta)

            # Get the time zone code
            timezone_code = current_datetime.tzinfo.zone

            return current_datetime, timezone_code
        except pytz.UnknownTimeZoneError:
            return None, None  # Return None if the provided time zone is invalid

    def format_datetime(self, datetime_str):
        try:
            # Parse the datetime string into a datetime object
            dt = parser.parse(datetime_str)

            # Format the datetime object as "YYYY-MM-DD/HH:MM:SS"
            formatted_datetime = dt.strftime("%Y-%m-%d/%H:%M:%S")

            return formatted_datetime
        except ValueError:
            return None  # Return None for invalid datetime strings
    

    @staticmethod
    def curr_day_short():
        # Get the current datetime
        now = datetime.now() + timedelta(minutes=TIME_DELTA)
        # Get the current day's name (e.g., 'Monday')
        day_name = now.strftime("%A")
        # Return the first three characters (e.g., 'Mon')
        return day_name[:3]
    