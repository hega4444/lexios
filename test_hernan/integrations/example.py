# test_hernan_example.py
from lexios.globals import GENERAL_VIRTUAL_AGENT
from lexios.integration.tools import external_command
from lexios.integration.tools import virtual_agent

"""
@external_command
def getCurrentWeather(location, unit: str = "c"):
# summ: Get the weather in location
# keys: location unit
# unit 'enum': ['c', 'f']
# unit 'enum': ['c', 'f']
# location 'description': 'some text'
  pass

# Use the VirtualAgent template and adjust its settings to get your desired result
Clarisa = VirtualAgent(
    name="Clarisa",
    instructions="You are a helpful math teacher.",
    description="Use this assistant to solve user's doubts about maths, logical problems and similar.",
    can_be_cloned=True,
    can_be_replaced=True,
    as_user_id=GENERAL_VIRTUAL_AGENT,
    retrieval=True,
    interpreter=True,
)
"""
