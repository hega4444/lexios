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
    This class serves as a point of truth for saving the context of an external command.
    Whenever the Ai model decides to execute a command on behalf of a user, a TrustedAction
    is created. It first captures the context of the thread in that moment and shares a copy
    with the external command executing the class method before_execution_event(). 
    It creates a template to store all relevant data used in making the next decision. 
    Additionally, after execution it attaches a Token response to itself, which contains a more detailed 
    dictionary including the transaction name, its result, and datetime data. This class 
    can also be utilized for submitting POST requests outside Lexi while also being capable
    of signing transactions, providing an extra layer of security and data encapsulation."
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
        self.secret_signature: str = kwargs.get("secret_signature", None)

        # Variables for storing execution result, messages, and exceptions
        self.execution_result = None
        self.messages = []
        self.exceptions = []

        # JWT configuration
        self.jwt_secret = self.secret_signature or LEXI_SIGNED_TRX_PASSWORD 
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
        """
        Adds a custom message to the action.
        """
        self.messages.append(message)

    def _add_exception(self, exception: Exception):
        """
        Attaches an exception to the action. In case the execution raised an exception.
        """
        self.exceptions.append(exception)

    def _add_execution_result(self, result: any):
        """
        Submitt the output of the transaction.
        """
        if not (self.output_submitted and self.signed):
            self.execution_result = result
            self.output_submitted = True
        else:
             raise LexiException("Output for this action has already been submitted.")
        
    def _generate_jwt_token(self):
        """
        After the action is executed and the output submitted, this method encrypts the 
        the output, transaction id, datetime data and user name into a token 
        signed either by:
        - The command itself: By setting the field `signature`. This will be the secret of the encryption.
        - Lexi: By default using as secret the global setting LEXI_SIGNED_TRX_PASSWORD. 

        Returns:
        - The signed JWT token.
        """
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
        """
        Adds the execution result and signs the action.
        Once signed the result cannot be modified.
        """
        try:
            # Add the result to the action
            self._add_execution_result(result=result)

            # Sign the action with a self-generated token
            self.signed = self._generate_jwt_token()

            # Return the signed action as TrustedAction -> or transaction 
            return self
        
        except Exception as e:
            raise LexiException(f"TrustedAction cannot be signed...{e}")

if __name__ == '__main__':

    action = TrustedAction(transaction_name = "executed_command")

    token = action._sign_results(result="Great success!")

    decoded_payload = jwt.decode(token, action.jwt_secret , algorithms=[action.jwt_algorithm])

    print("Decoded JWT Payload:")
    print(json.dumps(decoded_payload, indent=2))
