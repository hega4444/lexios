# plugin.py

import asyncio
from abc import ABC, abstractmethod

from lexios.core.common_tools import LexiException, LEXI_SIGNED_TRX_PASSWORD
from lexios.integration.trustedActions import TrustedAction

class PluginTemplate():

    def __init__(
            self, 
            plugin_name: str, 
            signature : str = None,
            action : TrustedAction = None, 

    ) -> None:
        # Implementation of the PluinTemplate interface

        from lexios.integration.manager import IntegrationsManager    

        # Set a label identifier
        self.identifier = plugin_name

         # Connect to the integrations manager
        self.manager = IntegrationsManager()

        # Call the inegrations manager to append this plugin
        self.manager.add_plugin(self)

        # Signature (password for the ext command) otherwise the transactions will be signed by Lexi itself.
        self.signature = signature or LEXI_SIGNED_TRX_PASSWORD

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
    async def before_request_event(self, action: TrustedAction):
        """
        Defines en entrypoint to act before a command (action) is executed.  

        Abstract method to be implemented by child classes.

        Parameters:
          - action (TrustedAction): Context of the execution.
        """
        pass

    @abstractmethod
    async def after_request_event(self, action: TrustedAction):
        """
        Defines en entrypoint to act after a command (action) is executed.  

        Abstract method to be implemented by child classes.

        Parameters:
        - action (TrustedAction): Context of the execution.
        """
        pass

