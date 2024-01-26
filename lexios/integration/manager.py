import os
import inspect
from typing import List, Callable, Union

from lexios.core.external_command import LexiExternalCommand
from lexios.core.lexios_main import LexiOS_Backend
from lexios.core.exceptions import IntegrationsManagerException, LexiWarning
from lexios.integration.plugin import PluginTemplate
from lexios.integration.virtual_agents import VirtualAgent
from lexios.integration.database_connection import DatabaseConnection

class IntegrationsManager():
    """
     Class Integrationsmanager checks in the current active project folder Integrations/ for .py files with functions declared
    with special decorators @external_command and @agent_command. It also checks for other plugins such as Databases connections
    or any child class of PluginTemplate, though for implementing such the logic of how to integrate into Lexi's setup 
    should be included here.

    After collecting all the components defined at framework level, it initiates the backend instance of Lexi.

    """
    _instance = None

    # Define a singleton pattern for the manager not to be wrongly loaded twice
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IntegrationsManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self.commands: List[Callable] = []
            self.databases: List[PluginTemplate] = []
            self.virtual_agents: List[PluginTemplate] = []
            self.unnasigned_methods = {}
  

    def _add_command(self, *commands: Union[Callable, None]):
        """ 
        Appends commands (standalone functions) for AI integration.

        Parameters:
        - `commands`(callable): A callable or list of callable objects.
        """
        try:
            for command in commands:
                if command is not None:

                    parameters = inspect.signature(command).parameters
                    # Verify is a standalone function
                    if not 'self' in parameters: 
                        self.commands.append(command)
                    else:
                        raise LexiWarning("Methods defined in virtual agents should use @agent_command decorator.")

        except Exception as e:
            raise IntegrationsManagerException(f"Integrations Manager add_command: {e}")

    def _add_method(self, *methods: Union[Callable, None]):
        """ 
        Appends Virtual Agents methods for AI integration.


        Parameters:
        - `methods`(callable): A callable or list of callable objects.
        """
        try:
            for method in methods:
                # Try to retrieve the name of the class it belongs
                class_name = method.__qualname__.replace(method.__name__, '').replace('.','')
                
                # Update the internal dictionary to compare against with when loading the virtual
                # agents
                if class_name not in self.unnasigned_methods:

                    self.unnasigned_methods[class_name] = [method]
                else:
                    self.unnasigned_methods[class_name].append(method)

        except Exception as e:
            raise IntegrationsManagerException(f"Integrations Manager add_method: {e}")

    def _add_plugin(self, plugin: PluginTemplate):
        """ 
        Adds a plugin to the integrations setup
        
        Parameters:
        - `plugin`(PluginTemplate): The plugin to be added to the project.
        
        """

        # Databases 
        if plugin.identifier == DatabaseConnection.__name__:
            self.databases.append(plugin)

        # Virtual Agents
        if plugin.identifier == VirtualAgent.__name__:
            self.virtual_agents.append(plugin)
            
            # Load unnasigned methods to the agent

            # Identify the class name
            try:
                agent_custom_class_name = type(plugin).__name__.split('.')[-1]
            
            except Exception as e:
                agent_custom_class_name = None
            
            # Check the custom class has unnasigned methods
            if agent_custom_class_name and agent_custom_class_name in self.unnasigned_methods:

                for method in self.unnasigned_methods[agent_custom_class_name]:
    
                    # Create a LexiExternalCommand Object 
                    new_command = LexiExternalCommand(
                        func=method,
                        requires_object=plugin,
                        allowed_in_background=True,
                        roles_required=['virtual_agent'],
                    )
                
                    # Append the command to that particular plugin / virtual agent
                    plugin.append_command(new_command)

            
    def make_lexi(self, **kwargs)-> LexiOS_Backend:
        """
        Creates an instance of the backend wuth all the integrations found.

        Parameters:
        - All the parameters that LexiOS_Backend can accept.

        Returns:
        An instance to the backend (LexiOS_Backend).
        """

        
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
    
    def load_project_integrations(self, folder_path):
        """ 
        Loads the declared integrations (functions, agents, databases, etc.) from files in the specified folder.
        
        Parameters:
        - `folder_path`(str): The path of the running Lexi's project root folder.

        """
        for filename in os.listdir(folder_path):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]  # Remove ".py" extension
                module_path = f"{folder_path.replace('/', '.')}.{module_name}"

                try:
                    module = __import__(module_path)

                except Exception as e:
                    print(f"Integrations Manager - Error importing {module_name}: {e}")
                    continue



