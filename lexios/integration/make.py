# make.py

import os
from lexios.integration.manager import IntegrationsManager, LexiOS_Backend
from admin.verify_folder import find_project_folder

# Dynamically fetch functions with @external_command decorator and integrate to Lexi
def get_lexi_backend_instance(**kwargs) -> LexiOS_Backend:
    """
    Creates the backend instance using the settings and files specific to the loaded project.
    If the integration with other components fails, it creates a more basic variant without
    integrations.

    Parameters:
    - **kwargs: All the parameters to be directly passed to the backend instance at __init__().
    
    Returns:
    - The backend instance.
    """
    try:
        # Find project folder
        project_folder = find_project_folder()

        # Build new path
        integrations_folder = os.path.join(project_folder, "integrations")

        # Collect all components in project's folder to be inegrated
        collector = IntegrationsManager()
        collector.load_project_integrations(folder_path=integrations_folder)

        # Make Lexi with integrations
        lexi = collector.make_lexi(**kwargs)

        return lexi
    except Exception as e:
        print(f"Could not create Lexi backend instance with integrations. Details: {e}")

        return IntegrationsManager().make_lexi(**kwargs)