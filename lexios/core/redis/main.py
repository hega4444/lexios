import subprocess
import time
import psutil

from lexios.settings.main import BROKER_PATH

def is_redis_running():
    for process in psutil.process_iter(['pid', 'name']):
        if process.info['name'] == BROKER_PATH:
            return True
    return False

def start_redis_server(redis_path= BROKER_PATH):
    try:
        subprocess.run([redis_path])
    except FileNotFoundError:
        print(f"Error: The {BROKER_PATH} executable not found in the system. Check BROKER_PATH variable in lexi_settings.py")
        raise

def ensure_redis_running():
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
