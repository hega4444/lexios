# plugin.py

from abc import abstractmethod

from lexios.core.common_tools import LexiException, LEXI_SIGNED_TRX_PASSWORD
from lexios.integration.trusted_actions import TrustedAction

class PluginTemplate():
    """
    PluginTemplate acts as an interface for the different components and commands that can be integrated to Lexi:

    - External commands
    - Database connetion
    - Virtual Agents
    - Agent commands

    It includes two abstract methods that can be implemented:

    - before_execution_event() This method is called just before the command is executed. Here the plugin 
    receives an TrustedAction with details about the action to be performed. The plugin can then run any logic
    and attach new data to the action if needed. 

    - after_execution_event() This method is called just after the command is executed. Again it receives a 
    TrustedAction but this time the action is signed (token already generated) and the command output 
    submitted. This token can then be used to exchange data or services with other systems. 

    Parameters: 
    - `plugin_name` str: Label identifier for the plugin category. It is used by the Integrations Manager 
    to know how to handle the different kinds of plugin Lexi accepts.
    - `secret_signature` str : Secret to use for token generation when a external command associated to the
    plugin is executed.
    - `action` TrustedAction : Contains execution context. The plugin is called to its constructor with an action as parameter
    every time an external command related to the plugin is executed.

    """

    def __init__(
            self, 
            plugin_name: str, 
            secret_signature : str = None,
            action : TrustedAction = None, 

    ) -> None:
        # Implementation of the PluinTemplate interface

        from lexios.integration.manager import IntegrationsManager    

        # Set a label identifier
        self.identifier = plugin_name

         # Connect to the integrations manager
        self.manager = IntegrationsManager()

        # Call the inegrations manager to append this plugin
        self.manager._add_plugin(self)

        # Signature (password for the ext command) otherwise the transactions will be signed by Lexi itself.
        self.secret_signature = secret_signature or LEXI_SIGNED_TRX_PASSWORD

        # Keep a stack of confirmed transactions
        self.recorded_actions : [TrustedAction] = []
    
    def _append_action(self, action: TrustedAction):
        """ Append a new transaction

            Validate is a TrustedAction object.
        """
        
        if isinstance(action, TrustedAction):
            self.recorded_actions.append(action)
        else:
            raise LexiException(f"Trying to append an action. Expected TrustedAction class, got {str(type(action))}.")

    @abstractmethod
    async def before_execution_event(self, action: TrustedAction):
        """
        Defines en entrypoint to act before a command (action) is executed.  

        Abstract method to be implemented by child classes.

        Parameters:
          - action (TrustedAction): Context of the execution.
        """
        pass

    @abstractmethod
    async def after_execution_event(self, action: TrustedAction):
        """
        Defines en entrypoint to act after a command (action) is executed.  

        Abstract method to be implemented by child classes.

        Parameters:
        - action (TrustedAction): Context of the execution.
        """
        pass


