# exceptions.py
from lexios.core.logger import CustomLogger
from logging import DEBUG, INFO, WARNING, CRITICAL, ERROR

class LexiException(Exception):
    def __init__(self, message, type=ERROR, **kwargs):
        self.message = f"{message} {kwargs or ''}"

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

class CreateAssistantFailed(LexiException):
    def __init__(self, message="Failed to create assistant", type=DEBUG, **kwargs):
        default_message = f"{message} {kwargs or ''}"
        super().__init__(default_message, type=type, **kwargs)

class VirtualAgentRequested(LexiException):
    """Handle a request for cloning a virtual agent in the routing process."""
    def __init__(self, name: str=None, **kwargs):
        default_message = f"Routing message to Virtual Agent {name} {kwargs or ''}"
        self.name = name
        super().__init__(default_message, type=INFO, **kwargs)

class MainAssistantRequested(LexiException):
    """Handle a request for routing back to a main assistant."""
    def __init__(self, agent:str=None, user_message:str=None, information:str=None, **kwargs):

        default_message = f"Virtual Agent {agent} raised this exception:{information} from user message:{user_message} {kwargs or ''}"

        self.agent = agent
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
