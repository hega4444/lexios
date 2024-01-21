# trusted_actions.py

import jwt
import json
from uuid import uuid4

from datetime import datetime, timedelta
from typing import List

from lexios.settings.main import LEXI_SIGNED_TRX_PASSWORD
from lexios.core.common_tools import LexiException, WARNING
from lexios.frontend.session_data import LexiSessionData

class TrustedAction():
    """
     This class defines a point of truth to save the context of an external command.
     It creates a template to save all the relevant data that is used to make the next
     decision. It attaches to itself a Token response with a more detailed dictionary
     containing the transaction name, its result and datetime data.
     It can be used for submitting POSTs requests outside Lexi and at the same time "
     be able to sign documents and add an extra layer of security and data encapsullation.
    """

    def __init__(self, **kwargs):
        self.lexi = kwargs.get("lexi")
        self.user_id: int = kwargs.get("user_id")
        self.user: LexiSessionData = kwargs.get("user")
        self.transaction_name: str = kwargs.get("transaction_name")
        self.conversation_id: str = kwargs.get("conversation_id")
        self.user_message: str = kwargs.get("user_message")
        self.virtual_agent_name: str = kwargs.get("virtual_agent_name")
        self.can_be_replaced: bool = kwargs.get("can_be_replaced", False)
        self.timestamp: datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.signature: str = kwargs.get("signature", None)

        # Variables for storing execution result, messages, and exceptions
        self.execution_result = None
        self.messages = []
        self.exceptions = []

        # JWT configuration
        self.jwt_secret = self.signature or LEXI_SIGNED_TRX_PASSWORD 
        self.jwt_algorithm = "HS256"
        self.jwt_expiration = timedelta(days=1)

        # Keep a signature of the execution
        self.signed = None
        self.transaction_id = None

        # Routing metadata
        self.next_agent = None
        self.prev_agent = None

        # Keep an internal status as a security mechanism to not allow changing the result afterwards
        self.output_submitted = False

    def _add_routing_metadata(self, prev_agent_name: str, next_agent_name: str):
        """
            Attach the details of from / to agents when switching context
        """
        self.prev_agent = prev_agent_name
        self.next_agent = next_agent_name

    def _add_message(self, message):
        self.messages.append(message)

    def _add_exception(self, exception):
        self.exceptions.append(exception)

    def _add_execution_result(self, result: any):
        
        if not (self.output_submitted and self.signed):
            self.execution_result = result
        else:
             raise LexiException("Output for this action has already been signed.")
        
    def _generate_jwt_token(self):
        # Security #

        # Generate an unique action id, convert to str for JSON
        self.transaction_id = str(uuid4())

        try:
        # Load the result dictionary
            payload = {
                'transaction_id' : self.transaction_id,
                'transaction_name': self.transaction_name,
                'timestamp': self.timestamp,
                'execution_result': self.execution_result,
                'exp': datetime.utcnow() + self.jwt_expiration
            }
            
            # Generate a signed token for validating the transaction
            jwt_token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

            return jwt_token
        
        except Exception as e:
            raise LexiException(f"TrustedAction, generate_jwt_token(), {e}")

    def _sign_results(self, result: any):

        try:
            # Add the result to the action
            self._add_execution_result(result=result)

            # Sign the action with a self-generated token
            self.signed = self._generate_jwt_token()

            # Update the status
            self.output_submitted = True

            # Return the signed action as TrustedAction -> or transaction 
            return self
        
        except Exception as e:
            raise LexiException(f"TrustedAction sign_with_results()... {e}")

if __name__ == '__main__':

    action = TrustedAction(transaction_name = "executed_command")

    token = action._sign_results(result="Great success!")

    decoded_payload = jwt.decode(token, action.jwt_secret , algorithms=[action.jwt_algorithm])

    print("Decoded JWT Payload:")
    print(json.dumps(decoded_payload, indent=2))
