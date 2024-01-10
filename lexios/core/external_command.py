
import re
import json
import asyncio
import inspect

from typing import List
from collections import OrderedDict

from lexios.core.lexi_base_tools import *
from lexios.core.logger import CustomLogger

class LexiExternalCommand(LexiBaseTools):
    # This class encapsulates the details for connecting an external process to the chat model, making it available to the user through NLP.

    def __init__(
        self,
        func: callable,
        requires_object = None,
        requires_dynamic_object = None,
        show_return_to_user: bool = False,
        if_error: str = None,
        before: str = None,
        after: str = None,
        printer: callable = None,
        roles_required: List[str] = None,
        scopes: List[str] = None,
        session_data_check: str = None,
        allowed_in_background = False,
    ):
        # Tool settings
        self.func = func
        self.name = func.__name__
        # Specify the object that has to call that method (if any)
        self.requires_object = requires_object
        # Specify if the object needs to be instantiated in the moment
        self.requires_dynamic_object = requires_dynamic_object

        self.json_string = None
        self.specs = None
        # Complete the specs
        self.generate_specs()  # This will populate self.json_string
        self.printer = printer

        # Custom parameters validation
        self.custom_validation = None

        # Protocol settings
        self.custom_messages = {}
        self.custom_messages["before"] = {'text' : before }
        self.custom_messages["after"] = {'text' : after }
        self.custom_messages["if_error"] = {'text' : if_error }

        self.custom_messages["show_return_to_user"] = show_return_to_user
        self.keys = ["error", "before", "after", "next"]

        # Security obj: code to register object and later access control
        self.roles_required = roles_required

        # Scopes are specific confirmations the action may need. I.E. "Im about to send an email. Do you want me to proceed...?"
        self.scopes = scopes 
        self.session_data_check = session_data_check

        # Define if the command can be executed by assistants running in background mode
        self.allowed_in_background = allowed_in_background

    def generate_specs(self):
        
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
                comment_sections["SUMM"] = sum_match.group(1)

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
            return "bool"

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
        # Method to update custom content to share with the user while the command is being executed
        # Recognized event types: 'BEFORE', 'AFTER', 'IF_ERROR'.

        if event_type.lower() not in self.keys:
            raise ValueError("Key is not valid. Check class definition.")

        msg_bundle = {}

        if text is not None:
            msg_bundle["text"] = text
        if images is not None:
            msg_bundle["images"] = images

        # Update messages in dictionary
        self.custom_messages[event_type.lower()] = msg_bundle

    def format_user_response(self, data) -> str:
        # Format external commands return values to show to user, can be used as a tailored output solution

        # If no special printer is assigned:
        if self.printer == None:
            try:
                # Check if data is a string that can be loaded as JSON
                if isinstance(data, str):
                    json_object = json.loads(data)
                elif isinstance(data, dict):
                    # It's already a dictionary
                    json_object = data
                else:
                    # If formatting does not work, show data dump:
                    return data

                # If data is a valid JSON object, pretty-print it with default json printer included in Lexi Class:
                return self.build_pretty_json_string(json_object)

            # If formatting does not work, show data dump:
            except Exception as e:
                return data
        else:
            # The command has a defined printer to format the output of the process
            printer = self.printer
            try:
                return printer(data)

            # If formatting does not work, show data dump:
            except Exception as e:
                return data

    def define_custom_validation(self, val_function):
        # Defines a custom validations over the input parameters of the external command
        # <val_function> must return None or a Str with error details.
        # Use for example to restrict the access of users to resources,
        # or prevent issues caused by wrong input data.

        self.custom_validation = val_function

    def __custom_params_validation(self, context, **params) -> bool:
        # Defines a custom validations over the input parameters of the external command
        # <val_function> must return None or a Str with error details.
        # <context> is a dict with user_id metadata about the action 
      
        if self.custom_validation:
            check = None
            try:
                if callable(self.custom_validation):
                    check = self.custom_validation(context, **params)
                    return check
            except Exception:
                return None
        return check

    async def execute_command(self, context = None, **kwargs):
        # Executes the external command 

        # Check for custom external command validation
        if self.custom_validation:
            check = None
            try:
                check = self.__custom_params_validation(context, **kwargs)
            except Exception:
                pass
            if check:
                    raise ValueError("Error: {check}")

        # Check if the function requires an associated object
        if self.requires_object:
            method_to_call = getattr(self.requires_object, self.name)
            result = method_to_call(**kwargs)
        
        # Check if the function requires an object to be instantiated
        elif self.requires_dynamic_object:
            
            # recover the values needed for the dynamic object
            dynamic_context = context.get("dynamic_context")
            required_object = self.requires_dynamic_object(**dynamic_context)
            method_to_call = getattr(required_object, self.name)

            if asyncio.iscoroutinefunction(method_to_call):

                result = await method_to_call(**kwargs)
            else:
                result = method_to_call(**kwargs)

        else:
            # Execute static function otherwise
            result = self.func(**kwargs)
        
        return result
    
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