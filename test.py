class VirtualAgent:
    def __init__(self, name):
        self.name = name

# Example list of Virtual Agent objects
virtual_agents = [
    VirtualAgent("Agent1"),
    VirtualAgent("Clarisa"),
    VirtualAgent("Lexi"),
]



# The first element of the sorted list will be the one with name 'Lexi' if it exists
first_agent = sorted_agents[0] if sorted_agents else None

for agent in sorted_agents:
    print(agent.name)
