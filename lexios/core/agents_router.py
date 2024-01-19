# virtual_agent.py

import inspect
from uuid import uuid4
from abc import abstractmethod

from lexios.core.common_tools import frontend_output, CustomLogger, DEBUG
from lexios.settings.main import LEXI_ALIAS
from lexios.core.external_command import LexiExternalCommand
from lexios.core.exceptions import VirtualAgentRequested, MainAssistantRequested, LexiException

from lexios.integration.plugin import PluginTemplate
from lexios.integration.trustedActions import TrustedAction
from lexios.integration.virtual_agents import VirtualAgent


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
        super().__init__(plugin_name="VirtualAgentsRouter")
        
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

        for agent in self._virtual_agents:
            if agent.name.lower() == agent_name.lower():

                return agent
        
        return _default
    
    def register_callback_response(self, confirmation: TrustedAction):
        # Keeps an internal cache to filter processes witn undesires echoes.

        try:
            # Add response to in-memory
            self.attended_callbacks[confirmation.token] = confirmation

        except Exception as e:
            LexiException(f"At register_callback_response. {e}")
    
    def respose_already_emmited(response) -> bool:

        pass


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
    async def route_to_virtual_agent(self, virtual_agent_name: str, information: str= None, no_callback: bool = True):

        # SUMM: Forward the user input to another virtual assistant listed on the available options.
        # viertual_agent_name  'description' : Virtual assistant name that will receive the message.
        # information 'description' : A brief comment for the next agent to gain context on how to help the user.
        # no_callback 'description' : <default>True: Next assistant takes over conversation with user. False: await results from virtual agent.

        # Find the agent by its alias       
        agent = self.by_name(virtual_agent_name)
        if not agent:
            
            # Return Information about the current routes available from this node.   
            return (f"Virtual agent {virtual_agent_name} not found. These are the valid agent names: {self._agent_names}"
                    f"\n Root assistant alias is '{LEXI_ALIAS}'.")
        
                    
        # Check is not already root or if it can be replaced
        if self.action.virtual_agent_name and self.action.virtual_agent_name.lower() == LEXI_ALIAS.lower():
            return f"You are at root level. Your alias is '{LEXI_ALIAS}'."
        

        # Check the requested agent is not already loaded
        elif self.action.virtual_agent_name and self.action.virtual_agent_name.lower() == virtual_agent_name.lower():
            return f"You already are '{virtual_agent_name}'. List of valid agent names: {self._agent_names}." 
        

        # Or cannot be replaced (settings on virtual agents)
        elif not self.action.can_be_replaced:
            return "You are currently set as the permanent assistant in this conversation. Routing service is Disabled."
        
        
        # If requested for the root assistant, relay the message.
        elif virtual_agent_name.lower() == LEXI_ALIAS.lower():
            self.route_to_main_assistant(information=information)


        # Check if there is no need for callback, the current thread allows replacement and the agent allows cloning
        elif no_callback and self.action.can_be_replaced and agent.can_be_cloned:

            # Raise an exception to handle the take over process
            raise VirtualAgentRequested(  
                        from_agent= self.action.virtual_agent_name or LEXI_ALIAS,
                        to_agent= agent.name,
                        user_message= self.action.user_message,
                        information = information,
            )

        else:
            # Create a request for the agent and await the response as if calling any other function
            agent_response = await self.attend_request(
                    message= information,
                    from_agent= agent,
                    from_user_id= self.action.user_id,
                    from_conversation_id= self.action.conversation_id,
                    session_data= self.action.user,
                    # Negate the callback parameter, seems to work better this way.
                    callback= not no_callback,
                )
            
            # Return the response inside the current thread
            return agent_response
        
    def list_virtual_agents(self) ->str:
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
                # Attach the record to the response
                response.append(agent_record)
        
        # Send response to the current agent         
        return response
    
    async def after_request_event(self, transaction: TrustedAction):
        """
        Callback implementation for the Virtual Agents Router

        It checks whether the Virtual Agent requires a callback and manages
        both sync or async calls.

        Check if the agent has a callback implementation
        This is not the same callback as when routing a conversation. This is an aftermath receipt that 
        gets generated after the transaction finishes executing, signed by Lexi.
        Then the Virtual Agent can decide if they want to trigger an action at that event by implementing
        "at_callback_event" method.

        Parameters:
        - transaction : SignedTransaction 

        Raises:
        - LexiException: If there are problems delivering the callback response to the source agent.
        """
        try:
            # Check the context of the transaction to see if there is a virtual agent involved        
            if (transaction.virtual_agent_name and 
                # Check also the name of the function, signal only when the agent is direclty requested
                transaction.transaction_name.lower() == self.route_to_virtual_agent.__name__.lower()):
                
                # Retrieve the agent by its name
                agent = self.by_name(self, transaction.virtual_agent_name.lower())

                if agent:

                    # Verify the agent has a callback defined and that is in fact callable
                    if hasattr(agent, "at_callback_event") and callable(getattr(agent, 
                    "at_callback_event")):
                        
                        # Check the execution runtime the function needs
                        is_async = inspect.iscoroutinefunction(agent.after_request_event)

                        if is_async:
                            # If it's asynchronous, call it asynchronously
                            await agent.after_request_event(action=transaction)
                        else:
                            # If it's synchronous, call it without await
                            agent.after_request_event(action=transaction)

        except Exception as e:
                        LexiException(f"At executing callback_event for agent {agent.name}. {e}")




if __name__ == "__main__":

    command = LexiExternalCommand(AgentsRouter.list_virtual_agents)

    print(command)