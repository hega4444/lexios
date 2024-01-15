
# context.py

class Context:
    def __init__(self, **kwargs):
        self.lexi = kwargs.get("lexi")
        self.user_id = kwargs.get("user_id")
        self.user = kwargs.get("user")
        self.conversation_id = kwargs.get("conversation_id")
        self.user_message = kwargs.get("user_message")
        self.virtual_agent_name = kwargs.get("virtual_agent_name")
        self.can_be_replaced = kwargs.get("can_be_replaced", False)
