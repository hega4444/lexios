# executor.py

import inspect
from typing import Any, Coroutine

from lexios.integration.plugin import PluginTemplate
from lexios.core.exceptions import LexiWarning

async def execute_event(
        executor: PluginTemplate,
        event_name: str,
        input: any,

) -> any:
    
    """
    Encapsulates the logic for calling PluginTemplate entry points available 
    in the framework.

    Parameters:
    - `executor`(PluginTemplate): The object instance that is being called. 
    - `method_name`(str): The method to be called.
    - `input`(any): What the executor receives as input parameter.

    Returs:
    - An updated version of the input object class it received.
    """  

    # Capture the method by its name
    event_method_to_call = getattr(executor, event_name, None)

    # If not found return the input as output
    if not event_method_to_call:
        return input
    
    # Check if the method remains an abstract method or has been implemented
    implemented = not getattr(event_method_to_call, '__isabstractmethod__', False)

    if not implemented:
        # If not implemented just return the same input
        return input

    # Verify the kind of call the method requires
    is_coroutine = inspect.iscoroutinefunction(event_method_to_call)

    try:
        
        # Execute the agent event method
        if is_coroutine:

            # async call
            output = await event_method_to_call(input)
        else:
            # sync call
            output = event_method_to_call(input)

        # Return the output from the call
        return output
    
    except Exception as e:
        LexiWarning(f"Agent {executor.name} at {event_name}() :{e}")

        # When errors happen, return the input as output by default.
        return input

  


if __name__ == "__main__":

    import asyncio
    from lexios.integration.virtual_agents import VirtualAgent
    from lexios.integration.tools import UserMessage, AgentEvent

    async def main():
        class TestAgent(VirtualAgent):
            def at_user_message_event(self, user_message: UserMessage) -> Coroutine[Any, Any, UserMessage]:
                
                user_message.content += " and some extra data from the agent."
                
                return user_message

        Fry = TestAgent(name="Fry")

        message = UserMessage(
            user_id=10,
            conversation_id="0013",
            content="hello there"
        )

        # Schedule the asynchronous function in the event loop
        output = await asyncio.create_task(
            execute_event(
                executor=Fry,
                event_name=AgentEvent.user_message,
                input=message,
            )
        )

        print(output.content)

    # Run the event loop
    asyncio.run(main())
