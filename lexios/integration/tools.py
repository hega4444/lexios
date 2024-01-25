# tools.py

from lexios.integration.manager import IntegrationsManager
from lexios.integration.database_connection import DatabaseConnection
from lexios.integration.virtual_agents import VirtualAgent
from lexios.integration.messages import AgentMessage, UserMessage
from lexios.integration.trusted_actions import TrustedAction
from lexios.integration.agent_events import AgentEvent

# Instantiate a Manager for managing integrations (internally)

collector = IntegrationsManager()

# Define a decorator for appending functions to Lexi
def external_command(func: callable):
    """ @external_command decorator helps to signal Lexi that a particular standalone function is 
    to be included as tool for the AI model. External commands are public in the sense that are
    not attached to a particular plugin or Virtual Agent, but at the moment of loading 
    a new conversation all commands undergo a security roles verification.

    Accepts:
    - A standalone callable.

    """
    # Filter by checking the parameter 'self' is not included in the function:

    return collector._add_command(func)
    
# Define a decorator for appending functions to Lexi
def agent_command(method: callable):
    """ @agent_command decorator helps to signal Lexi that a particular method defined in a 
    child class of VirtualAgent is to be included as a tool for the AI model. Therefore the command
    is integrated as another option for the assistant loaded with the Virtual Agent.

    Accepts:
    - A method belonging to a Virtual Agent child class.

    """
    # Filter by checking the parameter 'self' is not included in the function:

    method.__agent_command__ = True
    return method

def virtual_agent(cls):
    """ @virtual_agent class decorator is needed when an agent command was defined in a child class of
    VirtualAgent, so it reads the methods from the class only after the latter is fully loaded into 
    the script. 
    """

    for name, attr in cls.__dict__.items():
        if hasattr(attr, '__agent_command__'):
            collector._add_method(attr)
    return cls


# Check if this script is the main module
if __name__ == "__main__":

    # Usage
    # Load external commands from the specified folder
    integrations_folder = "new_lexi_project/integrations"
    collector.load_project_integrations(integrations_folder)

    print("Collected:")
    for command in collector.commands:
        print(command)