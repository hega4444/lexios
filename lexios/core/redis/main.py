# core/redis/main.py

import subprocess
import time
import psutil

from lexios.settings.main import BROKER_PATH

def is_redis_running() -> bool:
    """
    Verifies if Redis server is active.

    Returns:

    - `bool`: True / False.
    """
    for process in psutil.process_iter(['pid', 'name']):
        if process.info['name'] == BROKER_PATH:
            return True
    return False

def start_redis_server(redis_path: str= BROKER_PATH):
    """
    Start the Redis server.

    Parameters:
    - `broker_path`(str): The broker path to run the server.
    """
    try:
        subprocess.run([redis_path])
    except FileNotFoundError:
        print(f"Error: The {BROKER_PATH} executable not found in the system. Check BROKER_PATH variable in lexi_settings.py")
        raise

def ensure_redis_running():
    """
    Setup logic to verify if the Redis server is running
    and start it if not.

    
    """
    if not is_redis_running():
        print("Redis is not running. Starting Redis server...")
        start_redis_server()
        time.sleep(1)  # Give some time for Redis to start
        if is_redis_running():
            print("Redis server started successfully.")
        else:
            print("Error: Failed to start Redis server.")
            
if __name__ == "__main__":
    ensure_redis_running()
