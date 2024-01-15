# context.py
from datetime import datetime
from typing import ForwardRef

class RunContext:
    def __init__(self, **kwargs):
        self.lexi = kwargs.get("lexi")
        self.user_id: int = kwargs.get("user_id")
        self.user: ForwardRef('LexiSessionData') = kwargs.get("user")
        self.requested_command: str = kwargs.get("requested_command")
        self.conversation_id: str = kwargs.get("conversation_id")
        self.user_message: str = kwargs.get("user_message")
        self.virtual_agent_name: str = kwargs.get("virtual_agent_name")
        self.can_be_replaced: bool = kwargs.get("can_be_replaced", False)
        self.timestamp: datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Variables for storing execution result, messages, and exceptions
        self.execution_result = None
        self.messages = []
        self.exceptions = []

    def add_message(self, message):
        self.messages.append(message)

    def add_exception(self, exception):
        self.exceptions.append(exception)

    def set_execution_result(self, result):
        self.execution_result = result
