# consent.py
import uuid
import json
from datetime import datetime, timedelta


from lexios.core.common_tools import frontend_output, LexiException

_consent_backend = {}

class ConsentScreen():
    """
    The ConsentScreen is a component that allows to verify directly with the user if a specif permission is to 
    to be granted. External commands can define scopes of access required to execute the command. Whenever the
    command is chosen by the Ai model to be executed, if a scope is required a message will be shown to the user
    asking for permission to take the action. 

    """

    def __init__(self, **kwargs):
        
        try:
            from lexios.core.function_calling import ToolCall

            self.status = "created"

            # expires_at, for now defined as number of seconds the consent screen remains valid
            if "timer" in kwargs:
                self.timer = kwargs.get("timer")
            else:
                self.timer = 60

            self.stated_at = None
            self.expires_at = None

            # lexi
            if "lexi" in kwargs:
                self.lexi = kwargs.get("lexi")

            # user_id
            if "user_id" in kwargs:
                self.user_id = kwargs.get("user_id")

            # conversation_id
            if "conversation_id" in kwargs:
                self.conversation_id = kwargs.get("conversation_id")

            # Retrieve additional scopes for this particular verification
            self.scopes = {}
            if "additional_scopes" in kwargs:
                self.scopes["additional_scopes"] = kwargs.get("additional_scopes")

            # Retrieve the defined scopes for each external command, if any
            if "calls" in kwargs:
                self.calls = kwargs.get("calls")

                call : ToolCall
                for call in self.calls:
                    if call.external_cmd.scopes:

                        self.scopes[call.function_name] = {}
                        self.scopes[call.function_name]["cmd_scopes"] = call.external_cmd.scopes
                        self.scopes[call.function_name]['arg_values'] = call.function_arguments
                          
                    else:
                        raise ValueError("Please enter a list of 'scopes'.")

            # Default prompt to user
            self.text_content = "The following actions require an explicit authorization from you..."

            # Generate token for the consent screen
            self.token = str(uuid.uuid4())

            # Store choices from user
            self.choices = {}

        except Exception as e:
            LexiException(f"Problems at generating consent screen for user_id {self.user_id}. {e}")

    async def show_to_user(self) -> bool:
        # Perform the verification

        # Send the details for the consent screen to the frontend
        await frontend_output(
            content = self.text_content,
            
            user_id = self.user_id,
            conversation_id = self.conversation_id,

            msg_type = "consent_screen",
            metadata={
                'scopes': self.generate_dynamic_scopes(),
                'token': self.token,
                'timer': self.timer,
            },
            spell = False,

        )

        # Return the token as a proof of stake
        return self.token
    
    def generate_dynamic_scopes(self):
        # Generate a list of strings ready to be displayed on the consent screen

        scopes_generated = []

        id = 1
        for command, command_scopes in self.scopes.items():

            for scope_name, scope in command_scopes.get("cmd_scopes").items():
                
                # Base message
                text = scope.get('template')
                # Get the arguments used for calling this command
                arg_values = json.loads(command_scopes.get('arg_values', {}))

                # Parse the arguments into the text
                for arg in scope.get('args', []):

                    if arg in arg_values:
                        text = text.replace("{" + arg + "}", str(arg_values[arg]))

                # Create an identifier for the scope
                formatted_id = str(id).zfill(3)
                id += 1
                
                # Append item to the output
                scopes_generated.append({
                       'id': formatted_id,
                       'text': text,
                    }   
                )
                
                # Save internal reference
                self.scopes[command]["cmd_scopes"][scope_name]["id"] = formatted_id

        # Record the time the dialog started
        self.stated_at = datetime.now() 

        # Calculate the expiration time
        self.expires_at = self.stated_at + timedelta(seconds=self.timer)                

        return scopes_generated
    
    def validate_call(self, call)-> str:

        # First check if the call has scopes required
        # Retrieve the scopes stores in this dialog for this call
        scopes = self.scopes.get(call.function_name).get("cmd_scopes")
        if not scopes:
            return "granted"

        # Check if there is a submitted result:
        result = _consent_backend.get(self.token)

        if result:

            # Recover the status
            status = result.get("status")

            # Retrieve the choices
            choices = result.get("choices")
            
            # In case the dialog expired update the self status
            if status in ("expired", "cancelled"):
                
                self.status = status
                
                return status
            
            elif status == "submitted":

                for scope in scopes:
                    
                    # Look for the linked id
                    call_id = self.scopes.get(call.function_name).get("cmd_scopes").get(scope).get("id")

                    # Validate the call id
                    permitted = any(choice["id"] == call_id and choice["checked"] == True for choice in choices)

                    if not permitted:
                        return "denied"
                
                # If all scopes were ok, grant tool call execution
                return "granted"

        # Validate if there is still time for the user to submit their answer   
        elif not self.expires_at or datetime.now() < self.expires_at:

            return "pending"

        else:
            # Mark as expired 

            self.status = "expired"
            return self.status
        
    def clear(self):
        
        # Clear the value from the cache
        #_consent_backend.pop(self.token)
        pass
    
