# plugin.py

from uuid import uuid4

class PluginTemplate():

    def __init__(self, plugin_name: str, id: uuid4 = uuid4()) -> None:

        from lexios.integrations.manager import IntegrationsManager    

        # Set a unique identifier
        self.id = id

        # Set a label identifier
        self.identifier = plugin_name

         # Connect to the integrations manager
        self.manager = IntegrationsManager()

        # Call the inegrations manager to append this plugin
        self.manager.add_plugin(self)


