#lexios.settings.main.py 
#-----------------------------------------------------------------------------------#
# Try to gather the local settings from the current working project
import sys

try:

    import os
    from admin.verify_folder import find_project_folder
    from importlib.machinery import SourceFileLoader
    
    # Build custom settings file path
    project_folder = find_project_folder()
    
    module_name = "settings" 
    module_path = os.path.join(project_folder, "settings.py")

    try:
        module = SourceFileLoader(module_name, module_path).load_module()
        # Update the local namespace with names from the module
        locals().update(vars(module))
    except ImportError:
        print(f"Failed to import {module_name}")

except Exception as e:

    # Import the baseline settings as safety net
    from lexios.settings.settings_template import *

