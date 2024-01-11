# virtual_agent.py
import markdown2

from lexios.settings.main import LEXI_GPT_MODEL
from lexios.core.external_command import LexiExternalCommand
from lexios.core.thread import LexiAssistantThread
from lexios.integrations.plugin import PluginTemplate
from lexios.core.logger import CustomLogger
from lexios.core.messages_backend import prepare_output

_internal_id = 500

class VirtualAgent(PluginTemplate):
    # Create a virtual agent that interacts within the system

    def __init__(self, 
                 name: str, 
                 instructions: str = None, 
                 hidden: bool = False,
                 full_access = False,
        ) -> None:

        self.commands = None
        self.resources = None
        self.instructions = instructions
        self.name = name
        self.hidden = hidden
        self.full_access = full_access
        self.status = "initiated"
        self.lexi_thread = None

        # Call construtor of the PluginTemplate class
        super().__init__(plugin_name= "VirtualAgent")

    async def process_inbound(
            self, 
            message: str, 
            attachments: any = None, 
            user_id: int = None,
            conversation_id: str = None,
            lexi = None, 
        
        ):
        # Send a message to the virtual agent

        try:
            if self.lexi_thread:
                await self.lexi_thread.process_input(message)

                # Retrieve output
                response = self.lexi_thread.response

                if response.get("status") == "completed":

                    plain_text = response.get('output')
                    # Use markdown2 to parse and get a better look on the responses
                    html_response = markdown2.markdown(plain_text)

                    await prepare_output(
                        lexi,
                        html_response,
                        user_id=user_id,
                        conversation_id=conversation_id,
                    )

                else:
                    raise ValueError("Could not process virtual agent request.")
        except Exception as e:
            pass

    def define_instructions(self, instructions: str):
        self.instructions = instructions

    def append_command(self, command):

        if not self.commands:
            self.commands = {}
        
        # Append the command to the virtual agent
        self.commands[command.name] = command

    def append_resource(self, resource: any):

        if not self.resources:
            self.resources = []
        
        self.resources.append(resource)

    def hide(self):
        self.hidden = True
    
    def unhide(self):
        self.hidden = False

    def load_lexi_thread(self, lexi):

        global _internal_id

        if self.full_access:
            tools = lexi.toolbox
        else:
            tools = {}
        
        try:
            # Build the LexiThread 
            self.lexi_thread= LexiAssistantThread(
                lexi= lexi,
                user_id= 1, #a special system id for the assistant
                conversation_id= str(_internal_id).zfill(3),
                instructions = self.instructions,
                tools = tools,
                model = LEXI_GPT_MODEL,
                run_in_background=True,
            )    

            # Update internal range
            _internal_id += 1

            # Change status
            self.status = "loaded"
        
        except Exception as e:

            self.status = "load_failed"
            with CustomLogger("lexios") as log:
                log.error(f"Could not load virtual agent '{self.name}'. {e}")


class VirtualAgentsRouter:

    _virtual_agents = None
    _agent_names = None

    def __init__(self, virtual_agents: list = None, **kwargs):
        # Initialization logic
        
        if virtual_agents:
            VirtualAgentsRouter._virtual_agents = virtual_agents
            VirtualAgentsRouter._agent_names = [agent.name for agent in VirtualAgentsRouter._virtual_agents] if virtual_agents else []

        # Update the context
        self.lexi = kwargs.get('lexi')
        self.user_id = kwargs.get('user_id')
        self.conversation_id = kwargs.get('conversation_id')
        self.user_message = kwargs.get('user_message')

    async def route_to_virtual_agent(self, virtual_agent_name: str, message: str, attachments: str = None):
        # SUMM: Forward the user input to another virtual assistant listed on the available options.
        # virtual_agent_name 'description': Virtual assistant name that will receive the message

        for agent in self._virtual_agents:
            if agent.name.lower() == virtual_agent_name.lower():


                # Send message to virtual agent
                await agent.process_inbound(
                    message=message, 
                    attachments= attachments,
                    user_id = self.user_id,
                    conversation_id = self.conversation_id, 
                    lexi = self.lexi,
                )

                return "Messaged relayed successfully. The virtual agent will answer the user."
        

        return f"Virtual agent {virtual_agent_name} not found. These are the valid agent names: {self.agent_names}"

if __name__ == "__main__":

    command = LexiExternalCommand(VirtualAgentsRouter.route_to_virtual_agent)

    names = ['Clarisa']

    command.add_key_spec("virtual_agent_name", "enum", names)

    print(command)