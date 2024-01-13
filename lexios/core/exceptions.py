# exceptions.py

class VirtualAgentRequested(Exception):
    """Handle request for cloning a virtual agent in the routing process."""
    
    def __init__(self, name = None):
        super().__init__()

        self.name = name

class MainAssistantRequested(Exception):
    """Handle request routing back to a main assistant."""
    
    def __init__(self, agent = None, user_message = None, information = None):
        super().__init__()

        self.agent = agent
        self.information = information
        self.user_message = user_message