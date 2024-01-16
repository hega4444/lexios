from lexios.integration.manager import IntegrationsManager
from lexios.integration.database_plugin import DatabaseConnection
from lexios.integration.virtual_agents import VirtualAgent

# Instantiate a Manager for managing integrations (internally)
collector = IntegrationsManager()

# Define a decorator for appending functions to Lexi
def external_command(func: callable):
    return collector.add_command(func)


# Check if this script is the main module
if __name__ == "__main__":

    # Usage
    # Load external commands from the specified folder
    integrations_folder = "new_lexi_project/integrations"
    collector.load_external_commands(integrations_folder)

    print("Collected:")
    for command in collector.commands:
        print(command)