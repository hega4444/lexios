import os
from typing import List, Callable, Union

from lexios.core.external_command import LexiExternalCommand
from lexios.core.lexios_main import LexiOS_Backend
from lexios.core.setup import set_up_db_integration, set_up_virtual_agents_and_routing
from lexios.integrations.plugin import PluginTemplate

class IntegrationsManager:

    # Class Integrationsmanager checks in the current active project folder Integrations/ for .py files with functions declared
    # with @external_command decorator. 

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IntegrationsManager, cls).__new__(cls)
            cls._instance.commands = []
            cls._instance.databases = []
            cls._instance.virtual_agents = []

        return cls._instance

    def add_command(self, *commands: Union[Callable, None]):
        # Append commands for integration
        try:
            for command in commands:
                if command is not None:
                    self.commands.append(command)
        except Exception as e:
            print("Integrations: ", e)

    def add_plugin(self, plugin: PluginTemplate):
        # Add a plugin to the integrations setup

        # Databases 
        if plugin.identifier == "DatabaseConnection":
            self.databases.append(plugin)

        if plugin.identifier == "VirtualAgent":
            self.virtual_agents.append(plugin)

    def make_lexi(self, **kwargs):
        
        # Append the virtual agents
        if self.virtual_agents:
            kwargs['virtual_agents'] = self.virtual_agents

        # Append databases 
        if self.databases:
            kwargs['databases'] = self.databases

        # Create an instance of Lexi Backend 
        lexi = LexiOS_Backend(**kwargs)

        # Append the external commands
        for command in self.commands:
            new_command = LexiExternalCommand(command)
            lexi.append_command(new_command)

        return lexi
    
    def load_external_commands(self, folder_path):
        # Load external commands from Python files in the specified folder
        for filename in os.listdir(folder_path):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]  # Remove ".py" extension
                module_path = f"{folder_path.replace('/', '.')}.{module_name}"

                try:
                    module = __import__(module_path)

                except Exception as e:
                    print(f"Integrations Manager - Error importing {module_name}: {e}")
                    continue



