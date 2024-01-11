# api.globals.py

class Globals:
    _instance = None

    def __new__(
            cls, 
            user_input:str = None,

        ):

        if cls._instance is None:
            cls._instance = super(Globals, cls).__new__(cls)
        
        if user_input:
            cls._instance.user_input = user_input

        return cls._instance