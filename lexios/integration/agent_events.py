# integration/events.py

from lexios.integration.virtual_agents import VirtualAgent

class AgentEvent():
    """
    - Referenes to the Virtual Agents / AgentsRouter event methods.
    """
    open = VirtualAgent.at_open_event.__name__
    agent_message = VirtualAgent.at_agent_message_event.__name__
    user_message = VirtualAgent.at_user_message_event.__name__
    before_execution = VirtualAgent.before_execution_event.__name__
    after_execution = VirtualAgent.after_execution_event.__name__
    close = VirtualAgent.at_close_event.__name__