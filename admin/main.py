# admin/main.py

import os
import sys
import subprocess
from shutil import  copy2
from admin.settings import edit_constant_value_in_script


def __main__():
    if len(sys.argv) != 3:
        print("Usage: new_lexios_project <project_name>")
        sys.exit(1)
    
    project_name = sys.argv[2]

    if sys.argv[1] == "create":

        create_project(project_name)
    
    elif  sys.argv[1] == "run":

        run_project(project_name)


# Create a new project
def create_project(project_name):
    
    try:

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        project_dir = os.path.join(base_dir, project_name)


        # Create project directory
        try:
            os.makedirs(project_dir)
        except FileExistsError:
            print(f"Project folder {project_name} already exists. Please try with another identifier.")

        # Create __init__.py files
        open(os.path.join(project_dir, "__init__.py"), "a").close()

        # Create backend_logs folder
        os.makedirs(os.path.join(project_dir, "backlogs"))

        # Create integrations directory
        integrations_dir = os.path.join(project_dir, "integrations")
        os.makedirs(integrations_dir)
        open(os.path.join(integrations_dir, "__init__.py"), "a").close()

        # Create temporal uploads directory
        os.makedirs(os.path.join(project_dir, "temp", "uploads"))

        # Create temporal downloads directory
        os.makedirs(os.path.join(project_dir, "temp", "downloads"))

        # SSL certificate
        os.makedirs(os.path.join(project_dir, "ssl"))

        # Copy certificate files
        copy2(os.path.join(base_dir, "lexios", "settings", "ssl", "cert.pem"), os.path.join(project_dir, "ssl", "cert.pem"))
        copy2(os.path.join(base_dir, "lexios", "settings", "ssl", "key.pem"), os.path.join(project_dir, "ssl", "key.pem"))

        # Create main.py file
        main_file_path = os.path.join(project_dir, "main.py")
        with open(main_file_path, "w") as main_file:
            main_file.write(
                f'# my_async_script.py\n'
                f'from lexios import lexiOS\n\n'
                f'def main():\n'
                f'    server = lexiOS()\n\n'
                f'if __name__ == "__main__":\n'
                f'    main()\n'
            )

        # Create example.py in integrations directory
        example_file_path = os.path.join(integrations_dir, "example.py")
        with open(example_file_path, "w") as example_file:
            example_file.write(
                f'from lexios.integrations.tools import external_command\n'
                f'\n'
                f'"""\n'
                f'@external_command\n'
                f'def getCurrentWeather(location, unit: str = "c"):\n'
                f'# summ: Get the weather in location\n'
                f'# keys: location unit\n'
                f"# unit 'enum': ['c', 'f']\n"
                f"# unit 'enum': ['c', 'f']\n"
                f"# location 'description': 'some text'\n"
                f'  pass\n'
                f'"""\n'
            )
        
        # Copy the template settings file into the new project folder
        copy2(os.path.join(base_dir, "lexios", "settings", "settings_template.py"), os.path.join(project_dir, "settings.py"))

        # Custom values for new project
        edit_constant_value_in_script(os.path.join(project_dir, "settings.py"), "LOG_FOLDER", f"'{project_name}/backlogs'")
        edit_constant_value_in_script(os.path.join(project_dir, "settings.py"), "UPLOAD_FOLDER", f"'{project_name}/temp_uploads'")
        edit_constant_value_in_script(os.path.join(project_dir, "settings.py"), "DOWNLOAD_FOLDER", f"'{project_name}/temp_downloads'")
        edit_constant_value_in_script(os.path.join(project_dir, "settings.py"), "LEXI_DATABASE_NAME", f"'{project_name}_database'")
        edit_constant_value_in_script(os.path.join(project_dir, "settings.py"), "SSL_KEYFILE", f"'{project_name}/ssl/key.pem'")
        edit_constant_value_in_script(os.path.join(project_dir, "settings.py"), "SSL_CERTFILE", f"'{project_name}/ssl/cert.pem'")
        
        # Setup database
        try:
            from lexios.database.models import initial_database_setup

            initial_database_setup()
            print(f"Database for '{project_name}' was created.")
        except Exception as e:
            print(f"Could not create database models for {project_name}. Details: {e}")

        # Create data folder
        os.makedirs(os.path.join(project_dir, "data"))

        print(f"Lexios project '{project_name}' created successfully!")

    except Exception as e:
        print(f"Error: {e}")

# Run a project
def run_project(project_name):

    try:

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        project_dir = os.path.join(base_dir, project_name)
        path_main_file = os.path.join(project_dir, "main.py")

        if os.path.exists(path_main_file):
            # Change to the project directory
            os.chdir(project_dir)
            
        try:
            print(f"Starting '{project_name}'...")

            subprocess.run(["python", os.path.join(project_dir, "main.py")], cwd=base_dir)
        except KeyboardInterrupt:
            print(f"'{project_name}' finished.")

        else:
            print(f"Error: {path_main_file} does not exist.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    
    run_project("new_lexi_project")
