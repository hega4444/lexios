# api.globals.py

ROOT_ID = 1
GENERAL_VIRTUAL_AGENT = 2

GENERAL_VIRTUAL_AGENT_LABEL = "Virtual Agent"

class Globals:
    """
    This class acts as a global data store for the project.

    -`lexi` (LexiOS_Backend) The singleton instance of the backend.
    """
    _instance = None

    def __new__(
            cls, 
            lexi = None

        ):

        if cls._instance is None:
            cls._instance = super(Globals, cls).__new__(cls)
        
        if lexi:
            cls._instance.lexi = lexi

        return cls._instance