import os
import sys

def find_project_folder(filename="main.py"):
    """
    This is an admin function that helps finding the current executing project folder.

    Parameters:
    - `filename`: str , by default maiin.py which is the standard starting point of any Lexi project.
    
    """
    try:
        # Get the path of the script that was executed
        script_path = os.path.abspath(sys.argv[0])

        # Get the directory of the executed script
        current_directory = os.path.dirname(script_path)

        while True:
            # Check if the filename exists in the current directory
            main_file_path = os.path.join(current_directory, filename)
            if os.path.isfile(main_file_path):
                # Found the main.py file, return the project folder
                return os.path.basename(current_directory)

            # Move up one directory
            parent_directory = os.path.dirname(current_directory)

            # Check if we have reached the root directory
            if current_directory == parent_directory:
                break

            current_directory = parent_directory

        # Couldn't find the main.py file, check if it about the installation setup
        if len(sys.argv) == 2:
            project_name = sys.argv[1]
            return project_name
        
        else:
            return None

    except Exception as e:
        print(f"Could not find the project {current_directory}. Details: {e}")