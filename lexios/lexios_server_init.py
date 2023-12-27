# my_library/server.py
import uvicorn

from lexios.settings.main import *
from lexios.core.redis.main import ensure_redis_running

class lexiOS():

    def __init__(self):

        # Ensure message broker is active
        ensure_redis_running()
        
        # Init fastAPI server in asynchronous mode
        uvicorn.run(

            app = "lexios.api.server_main:app", 
            host = SERVER_IP, 
            port = SERVER_PORT, 
            reload = DEBUG_MODE,
        )


if __name__ == "__main__":

    lexiOS()