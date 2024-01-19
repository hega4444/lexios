# greetings.py

import random

def greetings(agent_name=None, user_name=None) -> str:
    
    """ Simple function to create dynamic salutations
    """

    # Probability distribution weights
    weights = [0.6, 0.1, 0.1]     # For 1st, 2nd and 3rd lists below..

    # Salutations when both agent and user names are available
    salutations_both_names = [
        f"Hello, {user_name}! I'm {agent_name}. How can I assist you today?",
        f"Hi, {user_name}! This is {agent_name}. {user_name}, how may I help you?",
        f"Hey there! It's {agent_name}. {user_name}, what brings you here?",
        f"Welcome, {user_name}! I'm {agent_name}, your virtual assistant.",
        f"{user_name}, this is {agent_name}. How can I make your day better?",
        f"{user_name}, meet {agent_name}. What can I do for you?",
        f"Hello {user_name}, I'm {agent_name}. How can I be of service?",
        f"{user_name}, this is {agent_name}. How can I assist you today?",
        f"Greetings {user_name}! I'm {agent_name}. What can I do for you?",
        f"Good to see you, {user_name}! I'm {agent_name}. How may I help?",
    ]

    # Salutations when only the agent name is available
    salutations_agent_only = [
        f"Hello, I'm {agent_name}. What can I do for you?",
        f"Hi, it's {agent_name}. How can I assist you today?",
        "Greetings! I'm your personal assistant. What can I help you with?",
        f"Hey there! This is {agent_name}. How can I assist you?",
        f"Hello! I'm {agent_name}. How can I assist you today?",
        f"Hi! This is {agent_name}. How may I help you?",
        "Greetings! I'm {agent_name}. What can I do for you?",
        "Hey there! It's {agent_name}. What can I do for you?",
        f"This is {agent_name}. How can I assist you today?",
        f"{agent_name} here. What brings you here?",
        f"Good day! I'm {agent_name}. How may I assist you?",
        f"Hi! I'm {agent_name}. How can I help?",
        f"Welcome! I'm {agent_name}, your virtual assistant.",
        f"This is {agent_name}. How can I make your day better?",
        f"Meet {agent_name}. What can I do for you?",
        f"Hello! I'm {agent_name}. How can I be of service?",
        f"This is {agent_name}. How can I assist you today?",
        f"Greetings! I'm {agent_name}. What can I do for you?",
        f"Good to see you! I'm {agent_name}. How may I help?",
        f"This is {agent_name}. How can I assist you?",
        f"Hi! I'm {agent_name}. What brings you here?",
        f"Meet {agent_name}. How can I assist you today?",
        f"Welcome! I'm {agent_name}. How may I help?",
    ]

    # Salutations when only the user name is available
    salutations_user_only = [
        f"Hello, {user_name}! How can I assist you today?",
        f"Greetings, {user_name}. What brings you here?",
        "Hey there! What can I do for you today?",
        f"Hi, {user_name}. What can I help you with?",
        "Hi there! How may I help you?",
        "Greetings! What can I do for you?",
        "Hey there! What can I do for you?",
        "This is Lexi. How can I assist you today?",
        "Lexi here. What brings you here?",
        "Good day! How may I assist you?",
        "Hi! How can I help?",
        "Welcome! I'm your personal assistant.",
        "This is Lexi. How can I make your day better?",
        "Meet Lexi. What can I do for you?",
        "Hello! How can I be of service?",
        "This is Lexi. How can I assist you today?",
        "Greetings! What can I do for you?",
        "Good to see you! How may I help?",
        "This is Lexi. How can I assist you?",
        "Hi! What brings you here?",
    ]

    # Combine all lists
    all_salutations = (
        salutations_both_names,
        salutations_agent_only,
        salutations_user_only
    )


    # Randomly select a salutation based on the availability of agent and user names
    if agent_name and user_name:
        selected_salutation = random.choices(all_salutations, weights=weights, k=1)[0][0]
    elif agent_name:
        selected_salutation = random.choice(salutations_agent_only)
    elif user_name:
        selected_salutation = random.choice(salutations_user_only)
    else:
        # If neither agent nor user names are available, provide a generic greeting
        selected_salutation = "Hello! How can I assist you today?"

    return selected_salutation

if __name__ == "__main__":

    # Example usage:
    agent_name = "Lexi"
    user_name = "John"
    specific_request = "solving a problem"
    greeting_message = greetings(agent_name=agent_name, user_name=user_name)
    print(greeting_message)