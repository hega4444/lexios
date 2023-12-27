import os
import sys
from lexios.integrations.manager import IntegrationsManager
from admin.verify_folder import find_project_folder

# Dynamically fetch functions with @external_command decorator and integrate to Lexi
def get_lexi_backend_instance(**kwargs):
    try:
        # Find project folder
        project_folder = find_project_folder()

        # Build new path
        integrations_folder = os.path.join(project_folder, "integrations")

        # Collect all functions marked with @external_command decorator
        collector = IntegrationsManager()
        collector.load_external_commands(integrations_folder)

        # Make Lexi with integrations
        lexi = collector.make_lexi(**kwargs)

        return lexi
    except Exception as e:
        print(f"Could not create Lexi backend instance with integrations. Details: {e}")

        return IntegrationsManager().make_lexi(**kwargs)