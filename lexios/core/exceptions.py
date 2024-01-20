# exceptions.py

import os
import inspect
from lexios.settings.main import LEXI_ALIAS
from lexios.core.logger import CustomLogger
from logging import DEBUG, INFO, WARNING, CRITICAL, ERROR


class LexiLogging(Exception):
    # A simple exception for easier logging
    def __init__(self, message=None, type=INFO, **kwargs):
        default_message = f"{message} {kwargs or ''}"

        with CustomLogger("lexios") as log:
            log.info(default_message)

class LexiWarning(Exception):
    # A simple exception for easier logging
    def __init__(self, message=None, type=WARNING, **kwargs):
        default_message = f"{message} {kwargs or ''}"

        with CustomLogger("lexios") as log:
            log.warning(default_message)       

class LexiException(Exception):
    # A more elaborate exception for logging errors
    def __init__(self, message=None, type=ERROR, **kwargs):
        # Get details from frame 0
        frame_info = self.get_calling_frame_info()

        # Construct the message
        self.message = f"Trace:{frame_info}: {str(kwargs or '')} {message}"
        
        # Log the message using CustomLogger
        with CustomLogger("lexios") as log:
            if type == ERROR:
                log.error(self.message)
            elif type == DEBUG:
                log.debug(self.message)
            elif type == INFO:
                log.info(self.message)
            elif type == WARNING:
                log.warning(self.message)
            elif type == CRITICAL:
                log.critical(self.message)

        super().__init__(self.message)

    def get_calling_frame_info(self):
        # Get details from the calling frame using inspect.stack()
        frame_info = inspect.stack()[2]
        filename = frame_info[1]
        # Omit the most base folder
        filename = os.path.relpath(filename, start=os.path.commonprefix([os.getcwd(), filename]))
        function_name = frame_info[3]
        line_number = frame_info[2]
        return f"{filename}:{function_name}:{line_number}"
    
class CreateAssistantFailed(LexiException):
    def __init__(self, message="Failed to create assistant", type=DEBUG, **kwargs):
        default_message = f"{message} {kwargs or ''}"
        super().__init__(default_message, type=type, **kwargs)

class VirtualAgentRequested(LexiException):
    """Handle a request for cloning a virtual agent in the routing process."""
    def __init__(self, to_agent:str=None, from_agent: str = None, user_message:str=None, information:str=None, **kwargs):
        default_message = f"Routing message to Virtual Agent {to_agent} {kwargs or ''}"
        
        self.to_agent = to_agent
        self.from_agent = from_agent
        self.user_message = user_message
        self.information = information
        super().__init__(default_message, type=INFO, **kwargs)

class MainAssistantRequested(LexiException):
    """Handle a request for routing back to a main assistant."""
    def __init__(self, from_agent:str=None, user_message:str=None, information:str=None, **kwargs):

        default_message = f"Virtual Agent {from_agent} raised this exception:{information} originated from user message:{user_message} {kwargs or ''}"

        # Define main assistant name as Lexi Alias (so it will change depending on the loaded project)
        self.to_agent = LEXI_ALIAS
        self.from_agent = from_agent
        self.user_message = user_message
        self.information = information
        super().__init__(default_message, type=INFO, **kwargs)

class LoadAssistantFailed(LexiException):
    def __init__(self, message=None, type=DEBUG, **kwargs):
        default_message = f"Failed to load assistant {kwargs or ''}"
        super().__init__(default_message, type=type, **kwargs)

class LoadThreadFailed(LexiException):
    def __init__(self, message="Failed to load thread",type=DEBUG, **kwargs):
        default_message = f"{message} {kwargs or ''}"
        super().__init__(default_message,type=type, **kwargs)

class LoadConversationFailed(LexiException):
    def __init__(self, message="Failed to load conversation",type=DEBUG, **kwargs):
        default_message = f"{message} {kwargs or ''}"
        super().__init__(default_message, type=type,**kwargs)

class SessionManagerException(LexiException):
    def __init__(self, message=None,type=ERROR, **kwargs):
        default_message = f"Session Manager Exception: {message} {kwargs or ''}"
        super().__init__(default_message, type=type,**kwargs)

class IntegrationsManagerException(LexiException):
    def __init__(self, message=None,type=ERROR, **kwargs):
        default_message = f"Integrations Manager Exception: {message} {kwargs or ''}"
        super().__init__(default_message, type=type,**kwargs)
