import openai

from lexios.settings.main import LEXI_GPT_MODEL

async def ai_completion_request(prompt: str, details: str = None, instructions: str = None) -> str:

    response = openai.chat.completions.create(
    model=LEXI_GPT_MODEL,
    messages=[
        {"role": "system", "content": "You are a helpful assistant. " + str(instructions)},
        {"role": "user", "content": prompt + str(details)},

    ]
    )

    return response

async def ai_assistant_request(user_id: int, request: str, instructions: str, conversation_id: str= None):
    
    from lexios.core.session_manager import LexiSessionManager

    session_manager = LexiSessionManager()

    # Create a new thread in background mode:

    thread =  session_manager.new_lexi_thread(
        user_id= user_id,
        conversation_id= conversation_id,
        args= {
            'user_id': user_id,
            'toolbox': session_manager.lexi.toolbox,
            'instructions': instructions,
            'model': LEXI_GPT_MODEL,
            'lexi': session_manager.lexi,
            'run_in_background': True,
        }
        )

    await thread.process_input(request)

    # Retrieve output
    response = thread.response

    return response

