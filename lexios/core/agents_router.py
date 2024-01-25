# virtual_agent.py

import inspect

from lexios.settings.main import LEXI_ALIAS
from lexios.core.external_command import LexiExternalCommand
from lexios.core.executor import execute_event
from lexios.core.exceptions import VirtualAgentRequested, MainAssistantRequested, LexiException


from lexios.integration.plugin import PluginTemplate
from lexios.integration.trusted_actions import TrustedAction
from lexios.integration.tools import VirtualAgent, AgentEvent



class AgentsRouter(PluginTemplate):

    """
    The VirtualAgentRouter class redirects a LexiAssistantThread by loading onto it a new 
    pre defined assistant. After switching context the tools and commands the assistant can
    access to are uptaded. 

    """

    _virtual_agents = []
    _agent_names = []

    def __init__(self, virtual_agents: list = None, action: TrustedAction = None):
        # Initialization logic

        # Register the plugin by calling the super class
        super().__init__(plugin_name="AgentsRouter")
        
        if virtual_agents:
            # Update the list of virtual aents 
            AgentsRouter._virtual_agents = virtual_agents
            AgentsRouter._agent_names = [agent.name for agent in AgentsRouter._virtual_agents] if virtual_agents else []

        if action:
            # Save the action context 
            self.action = action
        
        # Keep a internal cache of attended requests
        self.attended_callbacks = {}
    
    # Return a VirtualAgent by its label name
    def by_name(self, agent_name: str, _default: any = None) -> VirtualAgent:
        """returns a VirtualAgent or a given _default (None)
        """

        for agent in self._virtual_agents:
            if agent.name.lower() == agent_name.lower():

                return agent
        
        return _default


    # Route to main assistant
    def route_to_main_assistant(self, information: str = None):

        # SUMM: Use when assistant cannot complete user request and requires a higher level of supervision. 
        # information 'description': include any relevant data that can help the main assistant to find a better solution.

        # Check if there is a virtual agent loaded
        if (not self.action.virtual_agent_name or
            # And the virtual agent is not root already:
            self.action.virtual_agent_name and self.action.virtual_agent_name.lower() == LEXI_ALIAS.lower()):
            
            # Let know the assitant that they are already root
            return f"You are already the main-root assistant. Your name is '{LEXI_ALIAS}'."
        
        else:
            # Raise Exception
            raise MainAssistantRequested(
                                user_message= self.action.user_message,
                                from_agent= self.action.virtual_agent_name,
                                information= information,                 
            )

    # Route to a virtual agent
    async def route_to_virtual_agent(self, 
                                     virtual_agent_name: str, 
                                     information: str= None, 
                                     no_callback: bool = True,
                                     just_say_hi: bool = True,
    ):
        """
        Forward the user input to another VirtualAgent.


        -This is an internal method of the router that receives commands from the AI model.\n
        -`virtual_agent_name` : str Label that identifies the virtual agent.
        -`information` : str Aggregated data for the next assitant to take over.
        -`no_callback` : bool By debault True, meaning the conversation is handled to the next assistant. 
        False for awaiting a response from the asistant.
        - `just_say_hi`: bool True: No need for follow up, the agent will open with "hi..". False: Agent is required to solve an specific issue.
        
        """
        # SUMM: Forward the user input to another virtual assistant listed on the available options.
        # viertual_agent_name  'description' : Virtual assistant name that will receive the message.
        # information 'description' : A brief comment for the next agent to gain context on how to help the user.
        # no_callback 'description' : <default>True: Next assistant takes over conversation with user. False: await results from virtual agent.
        # just_say_hi 'description' : <default>True: No need for follow up, the agent will open with "hi..". False: Agent is required to solve an specific issue.

        # Identify the virtual agents at play
        root = self.by_name(LEXI_ALIAS)
        current_agent = self.by_name(self.action.virtual_agent_name or LEXI_ALIAS)
        requested_agent = self.by_name(virtual_agent_name)

        # Run validations #
        if not requested_agent:
            
            # Return Information about the current routes available from this node.   
            return (f"Virtual agent {virtual_agent_name} not found. These are the valid agent names: {self._agent_names}"
                    f"\n Root assist. alias is '{LEXI_ALIAS}'.")
        
        # Or cannot be replaced (settings on virtual agents)
        elif not current_agent.can_be_replaced:
            return "You are currently set as the permanent assistant in this conversation. Routing service is Disabled."
        
        # Check the requested agent is not already loaded
        elif requested_agent.name == current_agent.name:
            return f"You already are '{virtual_agent_name}'. Current agents: {self.list_virtual_agents()}." 
        
        # Check if the current agent has enabled a relationship with the requested agent
        elif not any(neighbor.name == requested_agent.name for neighbor in current_agent.get_neighbors() or [] ):
            return f"Agent {virtual_agent_name} cannot be accessed. Current agents: {self.list_virtual_agents()}."
 
        # If requested for the root assistant, redirect the message.
        elif requested_agent.name.lower() == root.name.lower():
            self.route_to_main_assistant(information=information)

        # Check if there is no need for callback, the current thread allows replacement and the agent allows cloning
        elif no_callback and current_agent.can_be_replaced and requested_agent.can_be_cloned:

            # Raise an exception to handle the take over process
            raise VirtualAgentRequested(  
                        from_agent= current_agent.name,
                        to_agent= requested_agent.name,
                        user_message= self.action.user_message,
                        information = information,
                        just_say_hi= just_say_hi,
            )

        else:
            # Create a request for the agent and await the response as if calling any other function
            agent_response = await requested_agent.attend_request(
                    message= information,
                    from_agent= requested_agent,
                    from_user_id= self.action.user_id,
                    from_conversation_id= self.action.conversation_id,
                    session_data= self.action.user,
                    # Negate the callback parameter, seems to work better this way.
                    callback= True,
                )
            
            # Return the response inside the current thread
            return agent_response

    # List all accesible nodes from current node   
    def list_virtual_agents(self) ->str:

        """
        List all accesible nodes from current node   


        """
        # SUMM: List all the current available virtual agents this node can connect to and their characteristics. 
        # SUMM: Use it to retrieve the virtual agent name that better fits the user requirements.
        # SUMM: OUTPUT {'callback_required': 'True Next assistant takes over conversation with the user. False: Await results from the virtual agent.}
        # SUMM: OUTPUT {'can_take_over': 'Specifies whether the agent can take over the conversation. If True, the agent has the capability to assume control.'}

        # Retrieve the current agent, by default the root assistant
        context_agent_name = self.action.virtual_agent_name or LEXI_ALIAS.lower()

        # Get the reference to the agent object by its name
        current_agent = self.by_name(context_agent_name) 

        response = []
        # Security: Filter the list of available agents according to the paths allowed
        for next_agent in current_agent.get_neighbors():
            
            # Check the current hidden status of the agent
            if not next_agent.hidden:
                

                # Create a record for the agent easy enough for the ai model to understand 
                agent_record = {
                    'name': next_agent.name,
                    'description': next_agent.description,
                    'instructions given': next_agent.instructions,
                    'callback_type': {
                        # Specify the type of callback the agent requires / enables at this moment
                        'callback_required': not next_agent.can_be_cloned,
                        'can_take_over': next_agent.can_be_cloned,
                    },
                    }
                
                if not any (agent.get('name') == next_agent.name for agent in response):

                    # Attach the record to the response
                    response.append(agent_record)
        
        # Send response to the current agent         
        return response

    
    async def after_execution_event(self, action: TrustedAction):
        """
        Implementation for the after_execution_event for AgentsRouter

        It checks whether the Virtual Agent requires a callback and manages
        both sync or async calls.

        Parameters:
        - action : TrustedAction 

        Raises:
        - LexiException: If there are problems delivering the callback response to the source agent.
        """
        try:
            # Execute event 'at_close_event' for the previously loaded agent
              
            if (action.prev_agent 
                # Check also the name of the function
                and (action.transaction_name.lower() == self.route_to_virtual_agent.__name__.lower() or
                     action.transaction_name.lower() == self.route_to_main_assistant.__name__.lower())
            ):    
                prev_agent : VirtualAgent
                # Retrieve the agent by its name
                prev_agent = self.by_name(self, action.prev_agent.lower())

                if prev_agent:
                    # Verify the agent has a callback defined and that is in fact callable
                    await execute_event(
                        executor= prev_agent,
                        event_name= AgentEvent.close,
                        input= action
                    )

        except Exception as e:
            LexiException(f"At executing after_closing_event for agent {prev_agent.name}. {e}")

        try:
            # Execute event 'at_open_event' for the agent to be loaded 

            if (action.next_agent and 
                # Check also the name of the function, signal only when the agent is direclty requested
                action.transaction_name.lower() == self.route_to_virtual_agent.__name__.lower()):
                
                agent : VirtualAgent
                # Retrieve the next_agent by its name
                next_agent = self.by_name(self, action.next_agent.lower())

                if next_agent:

                    # Verify the next_agent has a callback defined and that is in fact callable
                    await execute_event(
                        executor= next_agent,
                        event_name= AgentEvent.open,
                        input= action
                    )

        except Exception as e:
            LexiException(f"At executing callback_event for next_agent {next_agent.name}. {e}")




if __name__ == "__main__":

    command = LexiExternalCommand(AgentsRouter.route_to_virtual_agent)

    print(command)