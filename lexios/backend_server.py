# my_library/server.py


import uvicorn

from lexios.settings.main import *
from lexios.core.redis.main import ensure_redis_running

class LexiOS():

    def __init__(self):

        # Ensure message broker is active
        ensure_redis_running()
        

        settings = {
            
            'app': "lexios.frontend.server:app", 
            'host': SERVER_IP, 
            'port': SERVER_PORT, 
            'reload': DEBUG_MODE,
        }

        if ENABLE_SSL:

            settings.update(
                {
                    'ssl_keyfile': SSL_KEYFILE,
                    'ssl_certfile': SSL_CERTFILE,
                }
            )

        # Init fastAPI server in asynchronous mode
        uvicorn.run(**settings)



if __name__ == "__main__":

    LexiOS()