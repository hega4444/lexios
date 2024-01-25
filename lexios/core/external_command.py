
import re
import json
import asyncio
import inspect
from uuid import uuid4
from abc import abstractmethod

from typing import List, Any, Union, Optional
from collections import OrderedDict

from lexios.core.common_tools import *
from lexios.core.logger import CustomLogger
from lexios.integration.plugin import PluginTemplate
from lexios.integration.trusted_actions import TrustedAction

class LexiExternalCommand(PluginTemplate):
    """This class encapsulates the details for connecting an external command to Lexi.

    Parameters:
    - `func` (callable): The external command function to be executed.
    - `requires_object` (PluginTemplate): An optional external command plugin that is required for executing the command.
    - `requires_dynamic_object` (PluginTemplate): Similar to `requires_object` but in this case the instance of the class is created at the 
    moment of executing the command.
    - `show_return_to_user` (bool): A flag indicating whether the command result should be shown to the user.
    - `if_error` (str): A text to be shown if an error occurs during command execution.
    - `before` (str): A text to be shown before executing the command.
    - `after` (str): A text to be shown after executing the command.
    - `roles_required` (List[str]): A list of roles required to execute the command.
    - `scopes` (List[str]): A list of scopes of consent required to execute the command.
    - `session_data_check` (str): str with the field name on user profile settings checkboxes, if given Lexi will verify this value is active on the user profile.
    - `allowed_in_background` (bool): A flag indicating whether the command is allowed to execute in the background.

    Note: This class extends PluginTemplate and inherits its properties and methods.
    """

    def __init__(
        self,
        func: callable,
        requires_object: PluginTemplate = None,
        requires_dynamic_object: PluginTemplate = None,
        show_return_to_user: bool = False,
        if_error: str = None,
        before: str = None,
        after: str = None,
        roles_required: List[str] = None,
        scopes: List[str] = None,
        session_data_check: str = None,
        allowed_in_background: bool = False,
    ):
        # Tool settings
        self.func = func
        self.name = func.__name__

        # Specify the object that will receive the method call
        self.static_object = requires_object

        # Specify if the object needs to be initialized at execution time
        self.dynamic_object = requires_dynamic_object

        self.json_string = None
        self.specs = None
    
        # Custom parameters validation
        self._custom_validation = None

        # Protocol settings
        self.custom_messages = {}
        self.custom_messages["before"] = {'text' : before }
        self.custom_messages["after"] = {'text' : after }
        self.custom_messages["if_error"] = {'text' : if_error }

        self.custom_messages["show_return_to_user"] = show_return_to_user
        self.keys = ["error", "before", "after", "next"]

        # Security obj: code to register object and later access control
        self.roles_required = roles_required

        # Scopes are specific confirmations the action may need i.e "Im about to send an email. Do you want me to proceed...?"
        self.scopes = scopes 
        self.session_data_check = session_data_check

        # Define if the command can be executed by assistants running in background mode
        self.allowed_in_background = allowed_in_background

        # Additional key specifications
        self.aditional_key_specs = []

        # Complete the specs
        self.generate_specs()  # This will populate self.json_string

        super().__init__(plugin_name="External_Command_Interface")

    def generate_specs(self):
        """
        Generates automatic JSON structures with the function definition
        to share with the AI model. 
        """
        try:
            sig = inspect.signature(self.func)
            det_annotation = self.func.__annotations__

            params = OrderedDict()
            required_params = []

            for name, param in sig.parameters.items():
                # Dont include self in parameters:
                if name == "self":
                    continue
                # If the variable type cannot be determined, becomes 'string' by default:
                new_param = OrderedDict(
                    [
                        (
                            "type",
                            self.stringify_types(str(det_annotation.get(name, "string"))),
                        )
                    ]
                )
                if param.default == inspect.Parameter.empty:
                    required_params.append(name)
                params[name] = new_param

            source_lines = inspect.getsource(self.func).split("\n")
            comment_sections = self.parse_header_comments(source_lines)
            description = self.ensure_period(comment_sections.get("SUMM", ""))
            keys = comment_sections.get("KEYS", None)
            if keys:
                description += (
                    " Keys/words related to this function: " + self.ensure_period(keys)
                )

            properties_dict = OrderedDict()
            for param_name, param_info in params.items():
                properties_dict[param_name] = param_info

            # Process custom docstring tags
            custom_tags = self.parse_custom_tags(source_lines)
            for param_name, tags_info in custom_tags.items():
                if param_name in properties_dict:
                    for pair_value in tags_info:
                        properties_dict[param_name].update(pair_value)
            
            # Additional custom specifications
            for custom_spec in self.aditional_key_specs:
                    properties_dict[custom_spec[0]].update([custom_spec[1:]])

            func_specs = OrderedDict(
                [
                    ("type", "function"),
                    (
                        "function",
                        OrderedDict(
                            [
                                ("name", self.name),
                                ("description", description),
                                (
                                    "parameters",
                                    OrderedDict(
                                        [
                                            ("type", "object"),
                                            ("properties", properties_dict),
                                        ]
                                    ),
                                ),
                                ("required", required_params),
                            ]
                        ),
                    ),
                ]
            )

            # Manually construct the JSON string to ensure proper formatting
            self.json_string = json.dumps(func_specs, separators=(",", ":"))
            self.json_string = self.json_string.replace("}", " }")  # Remove white space

            # Save the specs
            self.specs = func_specs

        except Exception as e:
            with CustomLogger("lexios") as log:
                log.error(f"Could not parse the specs for function '{self.name}'. {e}")

    def parse_header_comments(self, source_lines):
        keys_pattern = re.compile(r"#\s*KEYS\s*:?\s*(.*)", re.IGNORECASE)
        sum_pattern = re.compile(r"#\s*SUMM\s*:?\s*(.*)", re.IGNORECASE)

        comment_sections = OrderedDict([("KEYS", None), ("SUMM", None)])

        for line in source_lines:
            keys_match = keys_pattern.search(line)
            sum_match = sum_pattern.search(line)

            if keys_match:
                keys_text = keys_match.group(1)
                keys = re.split(r"[,\s]+", keys_text)  # Split by commas and spaces
                keys_list = re.split(r"[,\s]+", keys_text)  # Split by commas and spaces
                keys = ", ".join(
                    f'"{key}"' for key in [k for k in keys_list if k != ""]
                )  # Wrap each key in double quotes
                comment_sections["KEYS"] = keys
            elif sum_match:
                comment_sections["SUMM"] = " ".join((comment_sections["SUMM"] or '' , sum_match.group(1)))

        return comment_sections

    def parse_custom_tags(self, source_lines):
        custom_tags = {}
        in_docstring = False

        for line in source_lines:
            if '"""' in line:
                continue
            elif not line.strip().upper().startswith(
                ('"""', "# KEYS", "# SUMM")
            ) and line.strip().startswith("# "):
                parts = line.split()
                if len(parts) >= 2:
                    tag_name = parts[1].strip('"')
                    tag_parts = " ".join(parts[2:])
                    try:
                        tag_key = (
                            tag_parts.split(":")[0]
                            .strip()
                            .replace('"', "")
                            .replace("'", "")
                        )
                        tag_value = tag_parts.split(":", 1)[1]
                        try:
                            tag_value = json.loads(tag_value)
                        except Exception:
                            pass
                        if isinstance(tag_value, str):
                            tag_value = tag_value.lstrip()
                            if (
                                tag_value.startswith("'") and tag_value.endswith("'")
                            ) or (
                                tag_value.startswith('"') and tag_value.endswith('"')
                            ):
                                tag_value = tag_value[1:-1]
                        tag_dict = {tag_key: tag_value}
                        if custom_tags.get(tag_name):
                            custom_tags[tag_name].append(tag_dict)
                        else:
                            custom_tags[tag_name] = [tag_dict]

                    except Exception:
                        pass

        return custom_tags

    def ensure_period(self, text):
        # Ensure there is a period at the end of the text
        if not text.endswith("."):
            return text + "."
        else:
            return text

    def stringify_types(self, text):
        if "int" in text:
            return "integer"
        elif "str" in text:
            return "string"
        elif "float" in text:
            return "float"
        elif "bool" in text:
            return "boolean"
        else:
            return "string"

    def __str__(self) -> str:
        # Manually construct the JSON string
        json_string = "{\n"
        json_string += '  "type": "function",\n'
        json_string += '  "function": {\n'
        json_string += '    "name": "' + self.specs["function"]["name"] + '",\n'
        json_string += (
            '    "description": "' + self.specs["function"]["description"] + '",\n'
        )
        json_string += '    "parameters": {\n'

        # Add location parameter
        json_string += '      "type": "object",\n'
        json_string += '      "properties": {\n'
        properties = self.specs["function"]["parameters"]["properties"]
        for prop_name, prop_info in properties.items():
            json_string += (
                '        "' + prop_name + '": ' + json.dumps(prop_info) + ",\n"
            )

        # Remove the trailing comma and newline for the last property
        json_string = json_string.rstrip(",\n")

        json_string += "\n"
        json_string += "      }\n"

        # Add required field
        json_string += "    },\n"
        json_string += (
            '    "required": ' + json.dumps(self.specs["function"]["required"]) + "\n"
        )

        # Complete the JSON string
        json_string += "  }\n"
        json_string += "}\n"

        return json_string

    def update_custom_messages(
        self, event_type: str, text = None, images = None
    ):
        """
        Method to update custom content to share with the user while the command is being executed
        
        Recognized event types: 
        'BEFORE', 'AFTER', 'IF_ERROR'.
        """

        if event_type.lower() not in self.keys:
            raise ValueError("Key is not valid. Check class definition.")

        msg_bundle = {}

        if text is not None:
            msg_bundle["text"] = text
        if images is not None:
            msg_bundle["images"] = images

        # Update messages in dictionary
        self.custom_messages[event_type.lower()] = msg_bundle

    @abstractmethod
    def format_user_response(self, data: any, action: TrustedAction) -> str:
        """ Format external commands outpus to show to the user, as a tailored output solution
        """
        return data
    
    @abstractmethod
    def custom_input_validation(self, action: TrustedAction, **params) -> Union[dict, None]:
        """
        Defines a custom validation over the input parameters of the external command.
        In this entrypoint is possible to raise an exception and stop the execution of the 
        external command..

        OR 

        return a new dict with the adjusted values for the parameters.

        Parameters:
        - `params`: A dict with the arguments selected by the Ai Model to execute the command.
        - `action`: A `TrustedAction` with context metadata about the action.

        """
        pass

    async def _execute_plugin_event(self, event_name: str, action: TrustedAction = None) ->TrustedAction:
        """ 
        Executes the external command plugin events before and after execution
        
        """
        try:
            # Check if the function requires an associated object
            if self.static_object:
                event_method_to_call = getattr(self.static_object, event_name)
                
            # Check if the function requires an object to be created right in the moment
            # of execution (thus dynamic) calling its contructor and passing an instance 
            # the TrustedAction object containing the aggregated execution context.
                    
            elif self.dynamic_object:
                
                # create an instance of the dynamic object that handles the tool call
                required_object = self.dynamic_object(action=action)
                event_method_to_call = getattr(required_object, event_name)
            
            else:
                return action

            # Check if the method remains an abstract method or has been implemented
            implemented = not getattr(event_method_to_call, '__isabstractmethod__', False)

            if not implemented:
                return action

            # Check whether the function needs a sync or async call
            if asyncio.iscoroutinefunction(event_method_to_call):

                result = await event_method_to_call(action = action)
            else:
                result = event_method_to_call(action = action)
        
            return result
        
        except Exception as e:
            raise # for now..

    async def _execute_external_command(self, action: TrustedAction = None, **kwargs) ->TrustedAction:
        # Executes the external command 

        parameters = kwargs

        # Check for the existance of an external command custom input validation
        if hasattr(self, self.custom_input_validation.__name__) and callable(self.custom_input_validation):
            alter_params = None
            try:
                alter_params = self.custom_input_validation(action=action, params= kwargs)

            except Exception:
                alter_params = None

            if alter_params:
                # Adjust the execution parameters
                parameters = alter_params
                    
        # Check if the function requires an associated object
        if self.static_object:
            method_to_call = getattr(self.static_object, self.name)

            
            # Check whether the function needs a sync or async call
            if asyncio.iscoroutinefunction(method_to_call):

                result = await method_to_call(**parameters)
            else:
                result = method_to_call(**parameters)
        

        # Check if the function requires an object to be created right in the moment
        # of execution (thus dynamic) calling its contructor and passing an instance 
        # the TrustedAction object containing the aggregated execution context.
                 
        elif self.dynamic_object:
            
            # create an instance of the dynamic object that handles the tool call
            required_object = self.dynamic_object(action=action)
            method_to_call = getattr(required_object, self.name)

            # Check whether the function needs a sync or async call
            if asyncio.iscoroutinefunction(method_to_call):

                result = await method_to_call(**parameters)
            else:
                result = method_to_call(**parameters)

        else:
            # Execute static function otherwise
            result = self.func(**parameters)
        
        return result
    
    def add_key_spec(self, param: str, tag: str, value: str):
        # Add a specif tag to a parameter in the tool specs definition

        if not self.aditional_key_specs:
            self.aditional_key_specs = []

        self.aditional_key_specs.append([param, tag, value])
        
        # Regenerate the specs
        self.generate_specs()
    
    def add_consent_scope(self, scope_name: str, template: str, vars: List[str] = None):
        # Customize an external command with a consent screen scope that uses parameters to form the string to show to the user

        # Available vars: names of the arguments described in the external command 
        # Validate Vars

        for var in vars:
            if not self.is_valid_parameter(var):
                raise ValueError(f"{var} is not a valid parameter for {self.name}. Check your entry.")

        if self.scopes is None:
            self.scopes = {}

        self.scopes[scope_name] = {
                'template' : template, 
                'args' : vars,
                }
        
    def is_valid_parameter(self, variable_name):
        # Check if variable_name is a valid parameter in func_specs structure
        if (
            isinstance(variable_name, str) and
            "function" in self.specs and
            isinstance(self.specs["function"], dict) and
            "parameters" in self.specs["function"] and
            isinstance(self.specs["function"]["parameters"], dict) and
            variable_name in self.specs["function"]["parameters"]["properties"]
        ):
            return True
        else:
            return False
        

if __name__ == "__main__":
    # Example usage:
    def getCurrentWeather(location, unit: str = "c"):
        """
        # summ: Get the weather in location
        # keys: location unit
        # unit 'enum': ["c", "f"]
        # location 'description': "some text"
        """
        pass

    command = LexiExternalCommand(getCurrentWeather)

    print(command)