# integration/message.py

from typing import Optional, Dict

class AgentMessage:
    def __init__(
        self,
        user_id: Optional[int] = None,
        conversation_id: Optional[str] = None,
        content: Optional[str] = None,
        msg_type: Optional[str] = None,
        metadata: Optional[Dict] = None,
        spell: Optional[str] = None,
        images: Optional[Dict] = None
    ):
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.content = content
        self.msg_type = msg_type
        self.metadata = metadata
        self.spell = spell
        self.images = images

class UserMessage:
    def __init__(
        self,
        user_id: Optional[int] = None,
        conversation_id: Optional[str] = None,
        content: Optional[str] = None,
        metadata: Optional[Dict] = None,
        assistant_instructions: Optional[str] = None
    ):
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.content = content
        self.metadata = metadata
        self.assistant_instructions = assistant_instructions
