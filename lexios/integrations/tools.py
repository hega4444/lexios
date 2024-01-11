from lexios.integrations.manager import IntegrationsManager
from lexios.integrations.database_plugin import DatabaseConnection
from lexios.integrations.virtual_agent import VirtualAgent

# Instantiate a Manager for managing integrations (internally)
collector = IntegrationsManager()

# Define a decorator for appending functions to Lexi
def external_command(func):
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