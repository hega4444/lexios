# plugin.py

class PluginTemplate():

    def __init__(self, plugin_name: str) -> None:

        from lexios.integrations.manager import IntegrationsManager    

        # Set an identifier
        self.identifier = plugin_name

         # Connect to the integrations manager
        self.manager = IntegrationsManager()

        # Call the inegrations manager to append this plugin
        self.manager.add_plugin(self)


