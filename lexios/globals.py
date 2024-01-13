# api.globals.py

ROOT_ID = 1
GENERAL_VIRTUAL_AGENT = 2

class Globals:
    _instance = None

    def __new__(
            cls, 
            user_input:str = None,
            lexi = None

        ):

        if cls._instance is None:
            cls._instance = super(Globals, cls).__new__(cls)
        
        if user_input:
            cls._instance.user_input = user_input
        
        if lexi:
            cls._instance.lexi = lexi

        return cls._instance