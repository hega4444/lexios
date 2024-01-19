# signatures.py

from abc import ABC, abstractmethod
from typing import ForwardRef, List

class _LexiOS_Backend(ABC):

    @abstractmethod
    def __init__(
            self, 
            model: str = None, 
            instructions: str = None, 
            active_users: dict =None,
            virtual_agents: List[str] = None,
            databases = None,
    ):
        pass  

    @abstractmethod
    def set_up_admin_assistant(self):
        pass

    @abstractmethod
    def define_output_methods(self, command_line=None, backend=None):
        pass

    @abstractmethod
    def append_command(self, command, required_by_lexi=False):
        pass

    @abstractmethod
    def build_toolbox(self, code_interpreter=True, retrieval=True):
        pass

    @abstractmethod
    def show_toolbox(self):
        pass

    @abstractmethod
    async def process_user_request(self, user_input=None, user_id=None,
                                   conversation_id=None, data=None, filename=None):
        pass

    @abstractmethod
    def reset_user_thread_request(self, user_id='default', conversation_id='default'):
        pass

    @abstractmethod
    def route_virtual_agent(self, thread, agent):
        pass

    @abstractmethod
    def build_thread(self, user_id, conversation_id, virtual_agent=None,
                     instructions=None, restore_conversation=None,
                     run_in_background=False):
        pass

class _LexiSessionManager(ABC):
    @abstractmethod
    def __new__(cls, lexi: _LexiOS_Backend = None):
        pass

    @abstractmethod
    def new_lexi_account(self, email, password, user_data=None, gmail_data=None):
        pass

    @abstractmethod
    def load_conversation(self, conversation: any):
        pass

    @abstractmethod
    def get_thread(self, user_id, conversation_id):
        pass

    @abstractmethod
    def register_thread(self, thread):
        pass

    @abstractmethod
    def close_session(self, user_id):
        pass

    @abstractmethod
    def save_session(self, user_id):
        pass

    @abstractmethod
    def update_conversation_title(self, user_id, conversation_id, new_title):
        pass

    @abstractmethod
    def retrieve_conversation(self, user_id, conversation_id):
        pass

    @abstractmethod
    def delete_conversation(self, user_id, conversation_id):
        pass


class _LexiAssistantThread(ABC):
    @abstractmethod
    def __init__(self, 
                 lexi=None, 
                 user_id: 
                 str = None, 
                 user_message: 
                 str = None,
                 files: list = None, 
                 model: str = None, 
                 toolbox: dict = None,
                 instructions: str = None, 
                 conversation_id=None,
                 restore_conversation=None, 
                 title_generated: bool = False,
                 run_in_background: bool = False, 
                 name: str = None,
                 virtual_agent_name: str = None, 
                 can_be_replaced: bool = True,
                 retrieval: bool = False, interpreter: 
                 bool = False) -> None:
        pass

    @abstractmethod
    def metadata(self):
        pass

    @abstractmethod
    async def process_input(self, message: str = None, file: str = None,
                            from_agent: ForwardRef('MainAssistantRequested') = None):
        pass

    @abstractmethod
    def save_message(self, message: str, source: str = "system", type: str = "text",
                     metadata: any = None):
        pass

    @abstractmethod
    def load_root_assistant(self, agent_request):
        pass

    @abstractmethod
    def load_virtual_agent(self, agent: ForwardRef('LexiAssistantThread')):
        pass

    @abstractmethod
    def cancel_run(self):
        pass
